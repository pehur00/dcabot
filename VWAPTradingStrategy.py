import logging
import time

import numpy as np
import pandas as pd

import ConfigHelper
from BybitClient import BybitClient

# Untested and unverified
class VWAPScalpingStrategy:
    def __init__(self, client, symbol, leverage, backcandles=200, bbands_length=14, bbands_std=2.0,
                 atr_length=7, sl_atr_multiplier=1.2, tp_sl_ratio=1.5):
        self.client = client
        self.symbol = symbol
        self.leverage = leverage
        self.backcandles = backcandles
        self.bbands_length = bbands_length
        self.bbands_std = bbands_std
        self.atr_length = atr_length
        self.sl_atr_multiplier = sl_atr_multiplier
        self.tp_sl_ratio = tp_sl_ratio

    def fetch_market_data(self):
        # Fetch recent market data for the symbol
        # You may need to implement this method in BybitClient or adjust as per available methods
        data = self.client.fetch_historical_data(self.symbol, interval=5, period=self.backcandles)
        return data

    def calculate_signals(self, data):
        # Ensure column names are accessed correctly
        data['Signal'] = 'Hold'  # Initialize the signal column

        # Ensure calculations are vectorized where possible
        # Define conditions for Buy and Sell signals
        close_ = data['close']
        # print(close_)
        data = self.client.fetch_historical_data(self.symbol, interval=5, period=self.backcandles)

        data['high'] = pd.to_numeric(data['high'], errors='coerce')
        data['low'] = pd.to_numeric(data['low'], errors='coerce')
        data['close'] = pd.to_numeric(data['close'], errors='coerce')
        data['volume'] = pd.to_numeric(data['volume'], errors='coerce')

        vwap = self.client.calculate_vwap_last(data)
        rsi = self.client.calculate_rsi_last(data)
        bbl_last, bbm_last, bbu_last = self.client.calculate_bbands_last(data)
        atr_last = self.client.calculate_atr_last(data)

        print(f'VWAP: {vwap} \n RSI: {rsi} \n BB: {bbl_last}, {bbm_last}, {bbu_last} \n ATR: {atr_last}')

        buy_condition = (close_ <= vwap) & (close_ <= bbl_last) & (rsi < 45)
        sell_condition = (close_ >= vwap) & (close_ >= bbu_last) & (rsi > 55)

        # Apply conditions to set signals
        data.loc[buy_condition, 'Signal'] = 'Buy'
        data.loc[sell_condition, 'Signal'] = 'Sell'

        # Note: The initial periods where indicators cannot be calculated (due to rolling window) should be considered
        # You might want to explicitly mark these periods as 'Hold' or simply leave them as such since 'Signal' was initialized to 'Hold'

        return data

    def generate_signals(self, data):
        # Generate trading signals based on VWAP, RSI, and Bollinger Bands
        # Placeholder for signal generation logic based on the notebook's strategy
        data = self.calculate_signals(data)
        return data

    def execute_trades(self, data):
        for index, row in data.iterrows():
            if row['Signal'] == 'Buy':
                stop_loss = row['close'] - (row['ATR'] * self.sl_atr_multiplier)
                take_profit = row['close'] + (row['ATR'] * self.sl_atr_multiplier * self.tp_sl_ratio)
                print(f"Buying at {row['close']}, SL: {stop_loss}, TP: {take_profit}")
                # Add code to execute buy order with SL and TP
            elif row['Signal'] == 'Sell':
                stop_loss = row['close'] + (row['ATR'] * self.sl_atr_multiplier)
                take_profit = row['close'] - (row['ATR'] * self.sl_atr_multiplier * self.tp_sl_ratio)
                print(f"Selling at {row['close']}, SL: {stop_loss}, TP: {take_profit}")
                # Add code to execute sell order with SL and TP

    def run(self, interval_seconds=300):
        """
        Run the strategy in a continuous loop.

        :param interval_seconds: Number of seconds to wait between iterations. Default is 300 seconds (5 minutes),
                                 matching the assumed time frame for market data fetching.
        """
        try:
            while True:
                print(f"Fetching new market data and evaluating strategy for {self.symbol}...")
                data = self.fetch_market_data()
                data = self.generate_signals(data)
                self.execute_trades(data)

                print(f"Strategy iteration completed. Waiting for next iteration in {interval_seconds} seconds...")
                time.sleep(interval_seconds)
        except KeyboardInterrupt:
            print("Strategy execution manually terminated.")


# Example usage
api_key, api_secret, testnet = ConfigHelper.get_api_credentials()
client = BybitClient(api_key, api_secret, testnet)

strategy = VWAPScalpingStrategy(client, 'SOLUSDT', leverage=5)
strategy.run(20)
