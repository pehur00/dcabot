import configparser
import json
import logging
import multiprocessing
import os
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


def define_instrument_info(client, symbol):
    try:
        instrument_infos = client.get_instruments_info(category='linear', symbol=symbol)['result']['list']
        info = instrument_infos[0]['lotSizeFilter']
        return float(info['minOrderQty']), float(info['maxOrderQty']), float(info['qtyStep'])
    except Exception as e:
        logging.error(f"ERROR: Unable to determine lotSize for symbol {symbol}: {e}")
        return None, None, None


def is_tradeable(account_balance, min_qty, limit_price, max_percent_per_order=0.01):
    cost_per_order = min_qty * limit_price
    return cost_per_order <= account_balance * max_percent_per_order


def calculate_max_orders_per_range(account_balance, min_qty, limit_price):
    cost_per_order = min_qty * limit_price
    return int(account_balance / cost_per_order)


def calculate_average_entry_price(client, symbol):
    positions = client.get_positions(category='linear', symbol=symbol)['result']['list']
    total_size = sum(float(pos['size']) for pos in positions)
    if total_size == 0:
        return 0
    return sum(float(pos['avgPrice']) * float(pos['size']) for pos in positions) / total_size


def get_ticker_info(client, symbol):
    ticker_info = client.get_tickers(category='inverse', symbol=symbol)['result']['list'][0]
    return (float(ticker_info['ask1Price']) + float(ticker_info['bid1Price'])) / 2


def determine_ranges(symbol):
    filename = f'{symbol}_data.json'
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            data = json.load(f)
            return filename, data['orders_per_range'], data['ranges']
    return filename, [], []


def place_order(client, symbol, qty, price):
    try:
        order = client.place_order(symbol=symbol, category='linear', isLeverage='1', side="Buy", order_type="Limit",
                                   qty=qty, price=price)
        logging.info(f"Placed limit buy order for {qty} of {symbol} at {price}")
        return order['result']['orderId']
    except Exception as e:
        logging.error(f"Failed to place order: {e}")
        return None


def update_ranges_and_qty(ranges, orders_per_range, price, qty, qty_step, multiplier, max_orders_per_range):
    def round_to_step(q, step):
        return round(q / step) * step

    if not ranges or price < ranges[-1][1]:
        new_range_start = price
        new_range_end = price * (1 - 0.015)  # 1.5% drop
        new_qty = round_to_step(qty * multiplier, qty_step)
        ranges.append((new_range_start, new_range_end, new_qty))
        orders_per_range.append(1)
    else:
        for i, (start, end, q) in enumerate(ranges):
            if end < price <= start:
                if orders_per_range[i] < max_orders_per_range:
                    orders_per_range[i] += 1
                return round_to_step(q, qty_step)  # Return the qty rounded to the nearest step
    return None


def close_current_positions(client, open_positions, symbol):
    # Cancel all pending orders
    client.cancel_all_orders(category="linear", settleCoin="USDT")
    # Sell the position
    try:
        order = client.place_order(symbol=symbol, category='linear', isLeverage='1',
                                   side="Sell", order_type="Market", qty=open_positions
                                   )
        logging.info(f"Sold {open_positions} of {symbol} at market price")
    except Exception as e:
        logging.error(f"Failed to sell position: {e}")


def profit_target_reached(limit_price, open_positions, profit_target, ranges):
    return open_positions > 0 and limit_price >= (ranges[-1][1] if ranges else 0) * (1 + profit_target)


def place_dca_orders(client, symbol, multiplier, time_interval, profit_target, shared_data):
    filename, orders_per_range, ranges = determine_ranges(symbol)
    min_amount, max_amount, qty_step = define_instrument_info(client, symbol)

    if min_amount is None:
        logging.error(f"Skipping {symbol} due to error in fetching instrument info.")
        return

    while True:

        # Check open positions
        open_positions = float(client.get_positions(category='linear')['result']['list'][0]['size'])

        print(f'Open positions: {open_positions}')

        limit_price = get_ticker_info(client, symbol)
        total_balance = float(
            client.get_wallet_balance(accountType='UNIFIED', coin='BTC')['result']['list'][0]['totalAvailableBalance'])

        # Check if the profit target has been reached and if there are open positions
        if profit_target_reached(limit_price, open_positions, profit_target, ranges):
            close_current_positions(client, open_positions, symbol)
            break  # Exit the loop after selling the position

        # Update shared data without get_lock()
        average_entry_price = calculate_average_entry_price(client, symbol)
        position_size = sum(data['position_size'] for data in shared_data.values())

        # Check if the position size for this symbol exceeds 30% of the total balance
        if shared_data.get(symbol, {}).get('position_size', 0) > 0.3 * total_balance:
            logging.info(f"Symbol {symbol} already has a significant position. Waiting before increasing position.")
            time.sleep(time_interval)
            continue

        # Update the shared data for this symbol
        shared_data[symbol] = {
            'average_entry_price': average_entry_price,
            'position_size': position_size,
            # Add other relevant data here
        }

        # Calculate maximum order size as 1% of total balance
        max_order_size = 0.01 * total_balance
        if min_amount * limit_price > max_order_size:
            logging.info(f"Order size for {symbol} exceeds maximum allowed size. Skipping order.")
            time.sleep(time_interval)
            continue

        # Proceed with range order logic
        qty = update_ranges_and_qty(ranges, orders_per_range, limit_price, min_amount, qty_step, multiplier,
                                    calculate_max_orders_per_range(total_balance, min_amount, limit_price))

        if qty is not None:
            if total_balance >= qty * limit_price:
                place_order(client, symbol, qty, limit_price)
            else:
                logging.info(f"Insufficient balance to place new order for {symbol}.")

        write_ranges_to_file(filename, ranges, orders_per_range)
        time.sleep(time_interval)


def write_ranges_to_file(filename, ranges, orders_per_range):
    with open(filename, 'w') as f:
        json.dump({'ranges': ranges, 'orders_per_range': orders_per_range}, f)


def main():
    config = read_config('config.ini')
    api_key, api_secret = get_api_credentials(config)
    client = HTTP(testnet=True, api_key=api_key, api_secret=api_secret)
    symbols = get_symbols(config)

    # Shared data structure
    manager = multiprocessing.Manager()
    shared_data = manager.dict()

    processes = [multiprocessing.Process(target=place_dca_orders, args=(client, symbol + 'USDT', 1.4, 5, 0.02, shared_data)) for symbol in symbols]
    for p in processes:
        p.start()
    for p in processes:
        p.join()

if __name__ == "__main__":
    main()
