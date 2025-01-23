import logging
import os
from _decimal import ROUND_DOWN, Decimal

from pythonjsonlogger import json

import TradingClient
# from BybitClient import BybitClient
from PhemexClient import PhemexClient


class MartingaleTradingStrategy:
    def __init__(self, client: TradingClient, leverage, profit_threshold, profit_pnl, proportion_of_balance,
                 buy_until_limit, logger):
        self.client = client
        self.leverage = leverage
        self.profit_threshold = profit_threshold
        self.profit_pnl = profit_pnl
        self.proportion_of_balance = proportion_of_balance
        self.buy_until_limit = buy_until_limit
        self.logger = logger

    def custom_round(self, number, min_qty, max_qty, qty_step):
        # Convert all inputs to Decimal for precise arithmetic
        number = Decimal(str(number))
        min_qty = Decimal(str(min_qty))
        max_qty = Decimal(str(max_qty))
        qty_step = Decimal(str(qty_step))

        # Determine the number of decimal places in qty_step
        decimal_places = max(len(str(qty_step).split('.')[-1]), 2)  # Ensure at least 2 decimal places

        # Apply floor rounding directly using the Decimal quantize method
        quantize_step = Decimal('1').scaleb(-decimal_places)  # Equivalent to 10**-decimal_places
        rounded_qty = (number / qty_step).quantize(Decimal('1'), rounding=ROUND_DOWN) * qty_step

        # Ensure the quantity is within the min and max bounds
        rounded_qty = max(min(rounded_qty, max_qty), min_qty)

        return rounded_qty

    def execute_strategy(self, symbol, strategy_filter, buy_below_percentage, leverage, ema_interval=5):
        self.client.cancel_all_open_orders(symbol)
        self.client.set_leverage(symbol, leverage)
        position = self.client.get_position_for_symbol(symbol)
        current_price, _ = self.client.get_ticker_info(symbol)
        total_balance = self.client.get_account_balance()

        ema_50 = self.client.get_ema(symbol=symbol, interval=ema_interval, period=50)
        ema_200 = self.client.get_ema(symbol=symbol, interval=ema_interval, period=200)

        self.logger.info(
            "Current EMA info",
            extra={
                "symbol": symbol,
                "json": {
                    "ema_interval": ema_interval,
                    "ema_50": ema_50,
                    "ema_200": ema_200
                }
            })

        if strategy_filter != 'EMA' or current_price > ema_200:
            if position:
                position_value = float(position['positionValue'])
                unrealized_pnl = float(position['unrealisedPnl'])
                pnl_percentage = unrealized_pnl / position_value * self.leverage
                position_value_percentage_of_total_balance = position_value / total_balance * 100

                self.logger.info(
                    "Current position state",
                    extra={
                        "symbol": symbol,
                        "json": {
                            "balance": total_balance,
                            "position_value": position_value,
                            "unrealized_pnl": unrealized_pnl,
                            "position_value_percentage_of_total_balance": position_value_percentage_of_total_balance,
                            "TP": self.profit_threshold,
                            "TP%": self.profit_pnl
                        }
                    })

                if unrealized_pnl > 0:
                    if position_value_percentage_of_total_balance > 40:
                        self.client.close_position(symbol, position['size'] * 0.5)
                    elif position_value_percentage_of_total_balance > 30:
                        self.client.close_position(symbol, position['size'] * 0.4)
                    elif position_value_percentage_of_total_balance > 20:
                        self.client.close_position(symbol, position['size'] * 0.3)
                    elif position_value_percentage_of_total_balance > 10:
                        self.client.close_position(symbol, position['size'] * 0.2)
                    else:
                        # Existing logic to close the entire position if profit targets are reached
                        if pnl_percentage > self.profit_pnl and unrealized_pnl > self.profit_threshold:
                            self.client.close_position(symbol, position['size'])
                elif pnl_percentage < buy_below_percentage or (
                        position_value < self.buy_until_limit and current_price > ema_50):
                    order_qty = self.calculate_order_quantity(symbol, total_balance, position_value, current_price,
                                                              pnl_percentage)
                    self.client.place_order(symbol, order_qty, current_price)

            else:
                order_qty = self.calculate_order_quantity(symbol, total_balance, 0, current_price, 0)
                self.client.place_order(symbol, order_qty, current_price)
        else:
            self.logger.info(
                "Skip buying below EMA",
                extra={
                    "symbol": symbol,
                    "json": {
                        "current_price": current_price,
                        "ema": ema_200,
                    }
                })

    def calculate_order_quantity(self, symbol, total_balance, position_value, current_price, pnl_percentage):
        min_qty, max_qty, qty_step = self.client.define_instrument_info(symbol)

        self.logger.info(
            "Calculating order quantity",
            extra={
                "symbol": symbol,
                "json": {
                    "total_balance": total_balance,
                    "position_value": position_value,
                    "current_price": current_price,
                    "pnl_percentage": pnl_percentage
                }
            })

        if position_value == 0:  # No open position 100 * 0,05 / 20
            qty = (total_balance * self.proportion_of_balance) / current_price
        else:
            qty = (position_value * (-pnl_percentage)) / current_price

        return self.custom_round(qty, min_qty, max_qty, qty_step)

# Configuration parameters
CONFIG = {
    'buy_until_limit': 5,
    'profit_threshold': 0.5,
    'profit_pnl': 0.05,
    'leverage': 10,
    'begin_size_of_balance': 0.001,
    'strategy_filter': 'EMA',  # Currently, only 'EMA' is supported
    'buy_below_percentage': 0.02,
    'logging_level': logging.INFO

}


def main():
    # Configure logging
    # Configure the logger to output structured JSON logs
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    logHandler = logging.StreamHandler()

    # Define a JSON log formatter
    formatter = json.JsonFormatter(
        '%(asctime)s %(levelname)s %(message)s %(symbol)s %(action)s %(json)s'
    )

    logHandler.setFormatter(formatter)
    logger.addHandler(logHandler)

    # Retrieve environment variables
    api_key = os.getenv('API_KEY')
    api_secret = os.getenv('API_SECRET')
    symbol = os.getenv('SYMBOL')
    ema_interval = int(os.getenv('EMA_INTERVAL', 5))  # Provide a default value (e.g., 200) if the variable isn't set
    testnet = os.getenv('TESTNET', 'False').lower() in ('true', '1', 't')

    # Validate required environment variables
    if not all([api_key, api_secret, symbol]):
        raise ValueError("API_KEY, API_SECRET, and SYMBOL environment variables must be set.")

    # Initialize Phemex client
    client = PhemexClient(api_key, api_secret, logger, testnet)

    # Initialize trading strategy with configuration parameters
    strategy = MartingaleTradingStrategy(
        client=client,
        leverage=CONFIG['leverage'],
        profit_threshold=CONFIG['profit_threshold'],
        profit_pnl=CONFIG['profit_pnl'],
        proportion_of_balance=CONFIG['begin_size_of_balance'],
        buy_until_limit=CONFIG['buy_until_limit'],
        logger=logger
    )

    try:
        # Execute the trading strategy for the specified symbol
        strategy.execute_strategy(
            symbol=symbol,
            strategy_filter=CONFIG['strategy_filter'],
            ema_interval=ema_interval,
            buy_below_percentage=CONFIG['buy_below_percentage'],
            leverage=CONFIG['leverage']
        )
    except Exception as e:
        logging.error(f'Error executing strategy for {symbol}: {e}')


if __name__ == "__main__":
    main()
