import logging
import time

import ConfigHelper
from BybitClient import BybitClient


class MartingaleTradingStrategy:
    def __init__(self, client: BybitClient, leverage, profit_threshold, profit_pnl, proportion_of_balance,
                 buy_until_limit):
        self.client = client
        self.leverage = leverage
        self.profit_threshold = profit_threshold
        self.profit_pnl = profit_pnl
        self.proportion_of_balance = proportion_of_balance
        self.buy_until_limit = buy_until_limit

    def execute_strategy(self, symbol, strategy_filter, ema_interval, ema_period, leverage):
        self.client.cancel_all_open_orders(symbol)
        self.client.set_leverage(symbol, leverage)
        position = self.client.get_position_for_symbol(symbol)
        current_price, _ = self.client.get_ticker_info(symbol)
        total_balance = self.client.get_account_balance()

        ema = self.client.get_ema(symbol=symbol, interval=ema_interval, period=ema_period)

        if strategy_filter != 'EMA' or current_price > ema:
            if position:
                position_value = float(position['positionValue'])
                pnl_absolute = float(position['unrealisedPnl'])
                pnl_percentage = pnl_absolute / position_value * self.leverage

                logging.info(
                    f"{symbol}: Position value={position_value}, Current UPNL={pnl_absolute} vs TP={self.profit_threshold}, PNL%={pnl_percentage} vs TP% {self.profit_pnl} ")

                if pnl_percentage > self.profit_pnl and pnl_absolute > self.profit_threshold:
                    self.client.close_position(symbol, position['size'])
                elif pnl_percentage < 0 or position_value < self.buy_until_limit:
                    order_qty = self.calculate_order_quantity(symbol, total_balance, position_value, current_price,
                                                              pnl_percentage)
                    self.client.place_order(symbol, order_qty, current_price)
            else:
                order_qty = self.calculate_order_quantity(symbol, total_balance, 0, current_price, 0)
                self.client.place_order(symbol, order_qty, current_price)
        else:
            logging.info(f'{symbol}: Price {current_price} below EMA {ema}')

    def calculate_order_quantity(self, symbol, total_balance, position_value, current_price, pnl_percentage):
        min_qty, max_qty, qty_step = self.client.define_instrument_info(symbol)
        logging.debug(f'Calculating order quantity: symbol {symbol}, '
                      f'total_balance={total_balance}, '
                      f'position_value={position_value}, '
                      f'current_price={current_price}, '
                      f'pnl_percentage={pnl_percentage}')

        if position_value == 0:  # No open position 100 * 0,05 / 20
            qty = (total_balance * self.proportion_of_balance) / current_price
        else:
            qty = (position_value * (-pnl_percentage)) / current_price

        return self.client.custom_round(qty, min_qty, max_qty, qty_step)


def main():
    api_key, api_secret, testnet = ConfigHelper.get_api_credentials()
    client = BybitClient(api_key, api_secret, testnet)
    config = ConfigHelper.get_config()

    # Set strategy parameters from config
    leverage = config.getint('Script', 'leverage')
    profit_pnl = config.getfloat('Script', 'profitPnL')
    profit_threshold = config.getfloat('Script', 'profitThreshold')
    proportion_of_balance = config.getfloat('Script', 'beginSizeOfBalance')
    buy_until_limit = config.getfloat('Script', 'buyUntilLimit')
    strategy_filter = config.get('Script', 'strategyFilter')
    ema_period = config.getfloat('Script', 'emaPeriod')
    ema_interval = config.getfloat('Script', 'emaInterval')

    strategy = MartingaleTradingStrategy(client, leverage, profit_threshold, profit_pnl, proportion_of_balance,
                                   buy_until_limit)

    symbols = ConfigHelper.get_symbols()

    while True:

        for symbol in symbols:
            strategy.execute_strategy(symbol, strategy_filter, ema_interval, ema_period, leverage)

        time.sleep(config.getint('Script', 'sleepTimer'))  # Sleep for 60 seconds


if __name__ == "__main__":
    main()
