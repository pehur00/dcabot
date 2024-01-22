import datetime
import math

import backtrader as bt
import configparser
import pandas as pd
from backtrader.plot import plot
from pybit.unified_trading import HTTP


class BacktestStrategy(bt.Strategy):
    params = (
        ('leverage', 1),
        ('profit_threshold', 0.03),
        ('proportion_of_balance', 0.001),
        ('buy_until_limit', 10000),
        # Additional parameters
        ('min_qty', 0.1),
        ('max_qty', 10000),
        ('qty_step', 0.1)
    )

    def log(self, txt, dt=None):
        ''' Logging function for this strategy'''
        dt = dt or self.datas[0].datetime.date(0)
        print(f'{dt.isoformat()} {txt}')

    def __init__(self):
        # Initialize indicators, orders, etc.
        self.order = None  # To track pending orders

    def notify_order(self, order):
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(
                    f'BUY EXECUTED, Price: {order.executed.price}, Cost: {order.executed.value}, Comm {order.executed.comm}')
            elif order.issell():
                self.log(
                    f'SELL EXECUTED, Price: {order.executed.price}, Cost: {order.executed.value}, Comm {order.executed.comm}')

            self.bar_executed = len(self)

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('Order Canceled/Margin/Rejected')

        # Reset the order attribute
        self.order = None

    def custom_round(self, number):
        # Rounds down to the nearest multiple of step_size
        return math.floor(number / self.p.qty_step) * self.p.qty_step

    def calculate_order_quantity(self, position_value, current_price, pnl_percentage):
        # Calculate order quantity based on strategy logic
        if position_value == 0:  # No open position
            qty = (self.broker.get_value() * self.p.proportion_of_balance) / current_price
        else:
            qty = (position_value * (-pnl_percentage)) / current_price
        return self.custom_round(qty)

    def next(self):

        current_price = self.data.close[0]  # Current closing price

        if self.order:  # If an order is pending, do not send another
            return

        position = self.getposition()
        position_value = position.size * position.price
        pnl_percentage = position.size / position_value if position_value != 0 else 0

        if position:  # Check if we are in the market
            if pnl_percentage > self.p.profit_threshold:
                # Close position
                self.log(f'Close position for {self.data._name}')
                self.order = self.close()
        else:
            order_qty = self.calculate_order_quantity(0, current_price, pnl_percentage)
            if order_qty > 0:
                self.log(f'Buy order for {self.data._name}: Qty: {order_qty}')
                self.log(f'Total orders: {self.sizer.broker.orders}')
                self.log(f'Total positions: {self.positions}')
                self.order = self.buy(size=order_qty)

def fetch_historical_data(symbol, interval, api_key, api_secret):
    # Calculate the start and end dates for the last year
    today = datetime.date.today()
    start_date = datetime.datetime(today.year - 1, 1, 1)
    end_date = datetime.datetime(today.year - 1, 12, 31)

    # Convert dates to timestamps in milliseconds
    start_timestamp = int(start_date.timestamp() * 1000)
    end_timestamp = int(end_date.timestamp() * 1000)

    session = HTTP(testnet=True, api_key=api_key, api_secret=api_secret)
    response = session.get_kline(category="linear", symbol=symbol, limit=1000, interval=interval, start=start_timestamp, end=end_timestamp)

    # Convert to DataFrame
    data = pd.DataFrame(response['result']['list'], columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover'])
    data['timestamp'] = pd.to_datetime(data['timestamp'], unit='ms')

    data['open'] = pd.to_numeric(data['open'])
    data['high'] = pd.to_numeric(data['high'])
    data['low'] = pd.to_numeric(data['low'])
    data['close'] = pd.to_numeric(data['close'])
    data['volume'] = pd.to_numeric(data['volume'])

    data['timestamp'] = pd.to_datetime(data['timestamp'], unit='ms')
    data.set_index('timestamp', inplace=True)

    return data


# Read config for symbols
config = configparser.ConfigParser()
config.read('config.ini')
symbols = config.get('Symbols', 'symbols').split(',')
api_key, api_secret = config.get('Bybit', 'api_key'), config.get('Bybit', 'api_secret')
cerebro = bt.Cerebro()

cerebro.addstrategy(BacktestStrategy, leverage=4, profit_threshold=0.03, proportion_of_balance=0.001, buy_until_limit=10000)

# Fetch and add data for each symbol
for symbol in symbols:
    data = fetch_historical_data(symbol, 'D', api_key, api_secret)
    data_feed = bt.feeds.PandasData(dataname=data)
    cerebro.adddata(data_feed)

# Set initial capital
cerebro.broker.set_cash(100000)
cerebro.addwriter(bt.WriterFile, csv=True, out='my_backtest.csv')

# Run backtest
results = cerebro.run()


