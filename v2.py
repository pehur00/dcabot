import configparser
import logging
import time

from pybit.unified_trading import HTTP

# Set up logging
logging.basicConfig(filename='bot.log', level=logging.INFO)


def read_config(file_path):
    config = configparser.ConfigParser()
    config.read(file_path)
    return config


def get_api_credentials(config):
    return config.get('Bybit', 'api_key'), config.get('Bybit', 'api_secret')


def get_symbols(config):
    return config.get('Symbols', 'symbols').split(',')


def get_script_thresholds(config):
    return config.get('')


def setup_client(api_key, api_secret):
    return HTTP(testnet=True, api_key=api_key, api_secret=api_secret)


def get_account_balance(client):
    balance_info = client.get_wallet_balance(accountType='UNIFIED', coin='USDT')['result']['list'][0]
    return float(balance_info['totalAvailableBalance'])


def get_open_positions(client):
    return client.get_positions(category='linear', settleCoin='USDT')['result']['list']


def cancel_all_open_orders(client, symbol):
    try:
        if (symbol is None):
            client.cancel_all_orders(category="linear", settleCoin="USDT")
        else:
            client.cancel_all_orders(category="linear", symbol=symbol)

        logging.info("All open orders cancelled successfully.")
    except Exception as e:
        logging.error(f"Error cancelling orders: {e}")


def define_instrument_info(client, symbol):
    try:
        instrument_infos = client.get_instruments_info(category='linear', symbol=symbol)['result']['list']
        info = instrument_infos[0]['lotSizeFilter']
        return float(info['minOrderQty']), float(info['maxOrderQty']), float(info['qtyStep'])
    except Exception as e:
        logging.error(f"ERROR: Unable to determine lotSize for symbol {symbol}: {e}")
        return None, None, None


def get_ticker_info(client, symbol):
    ticker_info = client.get_tickers(category='inverse', symbol=symbol)
    highest_ask = float(ticker_info['result']['list'][0]['ask1Price'])
    highest_bid = float(ticker_info['result']['list'][0]['bid1Price'])
    return highest_bid, highest_ask


def place_order(client, symbol, qty, price):
    try:
        client.place_order(symbol=symbol, category='linear', isLeverage='1', side="Buy", order_type="Limit", qty=qty,
                           price=price)
        logging.info(f"Placed limit buy order for {qty} of {symbol} at {price}")
    except Exception as e:
        logging.error(f"Failed to place order for {symbol}: {e}")


def close_position(client, symbol, qty):
    try:
        client.place_order(symbol=symbol, category='linear', isLeverage='1', side="Sell", order_type="Market", qty=qty)
        cancel_all_open_orders(client, symbol)
        logging.info(f"Closed positions and orders for {qty} of {symbol}.")
    except Exception as e:
        logging.error(f"Failed to close position for {symbol}: {e}")


def set_leverage(client, symbol, leverage):
    try:
        leverage_string = str(leverage)
        response = client.set_leverage(symbol=symbol, buyLeverage=leverage_string, sellLeverage=leverage_string,
                                       category='linear')
        if response['ret_code'] == 0:
            logging.info(f"Leverage set to {leverage}x for {symbol}")
        else:
            logging.error(f"Failed to set leverage for {symbol}: {response['ret_msg']}")
    except Exception as e:
        logging.error(f"Error setting leverage for {symbol}: {e}")


def custom_round(number, step_size):
    # Rounds down to the nearest multiple of step_size
    return round(number / step_size) * step_size


def calculate_order_quantity(client, symbol, total_balance, proportion_of_balance, avgPrice, currentPrice):
    min_qty, max_qty, qty_step = define_instrument_info(client, symbol)

    # Basic order quantity based on a proportion of the total balance
    order_value = total_balance * proportion_of_balance
    basic_qty = order_value / currentPrice

    # Adjust quantity based on the percentage difference between avgPrice and currentPrice
    if avgPrice > currentPrice:
        price_percentage_difference = ((avgPrice / currentPrice - 1) * 100)
        logging.info(
            f'Diff between ask price {currentPrice} and average buy price {avgPrice}: {price_percentage_difference}')
        adjusted_qty = min_qty * price_percentage_difference
        adjusted_qty = max(basic_qty, adjusted_qty)  # Ensure at least the basic quantity is maintained
    else:
        adjusted_qty = basic_qty

    # Adjust the quantity to adhere to min, max, and step size constraints
    adjusted_qty = max(min(adjusted_qty, max_qty), min_qty)
    adjusted_qty = custom_round(adjusted_qty, qty_step)
    logging.info(f'Adjusted QTY from basic {basic_qty} to {adjusted_qty}.')

    if basic_qty != adjusted_qty:
        logging.info(f'min_qty={min_qty}, max_qty={max_qty}, qty_step={qty_step}')

    return adjusted_qty


def main():
    config = read_config('config.ini')
    api_key, api_secret = get_api_credentials(config)
    client = setup_client(api_key, api_secret)

    cancel_all_open_orders(client, None)
    symbols = get_symbols(config)  # Retrieve the list of symbols from the config

    profit_threshold = config.getfloat('Script', 'profitThreshold')  # Define the profit threshold for closing positions
    leverage_level = config.getint('Script', 'leverage')  # Define the desired leverage level
    proportion_of_balance = config.getfloat('Script', 'beginSizeOfBalance')  # 0.1% of total balance

    for symbol in symbols:
        set_leverage(client, symbol, leverage_level)

    while True:
        total_balance = get_account_balance(client)
        open_positions = get_open_positions(client)
        positions_by_symbol = {pos['symbol']: pos for pos in open_positions}

        for symbol in symbols:
            min_qty, _, _ = define_instrument_info(client, symbol)
            if not min_qty:
                continue

            position = positions_by_symbol.get(symbol)
            if position:
                print(f'Position: {position}')
                position_size = float(position['size'])
                position_value = float(position['positionValue'])
                pnl_absolute = float(position['unrealisedPnl'])
                pnl = pnl_absolute / position_value * 100  # Calculate P&L percentage
                avg_price = float(position['avgPrice'])
                logging.info(
                    f'Symbol={symbol}, PNL={pnl}/absolute={pnl_absolute}, Position Value={position_value}, profit_threshold={profit_threshold}')

                # Closing positions with profit over the threshold
                if pnl > profit_threshold and pnl_absolute > 3.00:
                    close_position(client, symbol, position_size)
                elif pnl < 0 or position_value < config.getfloat('Script',
                                                                 'buyUntilLimit'):  # only trade on negative PNL
                    logging.info(
                        f'PNL Negative or position value beneath threshold, sending order to catch up for symbol {symbol}')

                    # def calculate_order_quantity(client, symbol, total_balance, proportion_of_balance, avgPrice, currentPrice):
                    bid_price, _ = get_ticker_info(client, symbol)
                    order_qty = calculate_order_quantity(client, symbol, total_balance, proportion_of_balance,
                                                         avg_price, bid_price)
                    place_order(client, symbol, order_qty, bid_price)
            else:
                # Place regular order for symbols without open positions
                bid_price, _ = get_ticker_info(client, symbol)
                place_order(client, symbol, min_qty, bid_price)

        time.sleep(60)  # Sleep for 60 seconds or as needed


if __name__ == "__main__":
    main()
