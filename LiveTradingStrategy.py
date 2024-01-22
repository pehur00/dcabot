import logging
import math


class LiveTradingStrategy:
    def __init__(self, client, leverage, profit_threshold, proportion_of_balance, buy_until_limit):
        self.client = client
        self.leverage = leverage
        self.profit_threshold = profit_threshold
        self.proportion_of_balance = proportion_of_balance
        self.buy_until_limit = buy_until_limit


    def custom_round(self, number, min_qty, max_qty, qty_step):
        logging.debug(f'rounding: number={number} min_qty={min_qty}, max_qty={max_qty}, qty_step={qty_step} ')

        # Determine the number of decimal places in qty_step
        decimal_places = max(len(str(qty_step).split('.')[-1]), 2)  # At least 2 decimal places

        # Round the number to match the precision of qty_step
        number = round(number, decimal_places)

        # Apply floor rounding
        rounded_qty = math.floor(number / qty_step) * qty_step

        # Ensure the quantity is within the min and max bounds
        return max(min(rounded_qty, max_qty), min_qty)

    def cancel_all_open_orders(self, symbol):
        try:
            if symbol is None:
                self.client.cancel_all_orders(category="linear", settleCoin="USDT")
            else:
                self.client.cancel_all_orders(category="linear", symbol=symbol)

            logging.info("All open orders cancelled successfully.")
        except Exception as e:
            logging.info(f"Error cancelling orders: {e}")

    def close_position(self, symbol, qty):
        try:
            self.client.place_order(symbol=symbol, category='linear', isLeverage='1', side="Sell", order_type="Market",
                                    qty=qty)
            self.cancel_all_open_orders(symbol)
            logging.info(f"Closed positions and orders for {qty} of {symbol}.")
        except Exception as e:
            logging.info(f"Failed to close position for {symbol}: {e}")

    def define_instrument_info(self, symbol):
        try:
            instrument_infos = self.client.get_instruments_info(category='linear', symbol=symbol)['result']['list']
            info = instrument_infos[0]['lotSizeFilter']
            return float(info['minOrderQty']), float(info['maxOrderQty']), float(info['qtyStep'])
        except Exception as e:
            logging.error(f"ERROR: Unable to determine lotSize for symbol {symbol}: {e}")
            return None, None, None

    def get_ticker_info(self, symbol):
        ticker_info = self.client.get_tickers(category='inverse', symbol=symbol)
        highest_ask = float(ticker_info['result']['list'][0]['ask1Price'])
        highest_bid = float(ticker_info['result']['list'][0]['bid1Price'])
        return highest_bid, highest_ask

    def place_order(self, symbol, qty, price):
        try:
            self.client.place_order(symbol=symbol, category='linear', isLeverage='1', side="Buy", order_type="Limit",
                             qty=qty, price=price)
            logging.info(f"Placed limit buy order for {qty} of {symbol} at {price}")
        except Exception as e:
            logging.info(f"Failed to place order for {symbol}: {e}")

    def execute_strategy(self, symbol, total_balance, open_positions):
        position = open_positions.get(symbol)
        current_price, _ = self.get_ticker_info(symbol)

        if position:
            position_size = float(position['size'])
            position_value = float(position['positionValue'])
            pnl_absolute = float(position['unrealisedPnl'])
            pnl_percentage = pnl_absolute / position_value

            if pnl_percentage > self.profit_threshold and pnl_absolute > 3.00:
                self.close_position(self.client, symbol, position_size)
            elif pnl_percentage < 0 or position_value < self.buy_until_limit:
                order_qty = self.calculate_order_quantity(symbol, total_balance, position_value, current_price,
                                                          pnl_percentage)
                self.place_order(symbol, order_qty, current_price)
        else:
            order_qty = self.calculate_order_quantity(symbol, total_balance, 0, current_price, 0)
            self.place_order(symbol, order_qty, current_price)

    def calculate_order_quantity(self, symbol, total_balance, position_value, current_price, pnl_percentage):
        min_qty, max_qty, qty_step = self.define_instrument_info(symbol)
        logging.debug(f'Calculating order quantity: symbol {symbol}, '
                      f'total_balance={total_balance}, '
                      f'position_value={position_value}, '
                      f'current_price={current_price}, '
                      f'pnl_percentage={pnl_percentage}')

        if position_value == 0:  # No open position
            qty = (total_balance * self.proportion_of_balance) / current_price
        else:
            qty = (position_value * (-pnl_percentage)) / current_price

        return self.custom_round(qty, min_qty, max_qty, qty_step)
