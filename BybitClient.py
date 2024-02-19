import logging
import time
from decimal import Decimal, ROUND_DOWN

import numpy as np
import pandas as pd
from pybit.unified_trading import HTTP


class BybitClient:
    def __init__(self, api_key, api_secret, testnet):
        self.client = HTTP(testnet=testnet, api_key=api_key, api_secret=api_secret)

    def get_account_balance(self):
        try:
            balance_info = self.client.get_wallet_balance(accountType='UNIFIED', coin='USDT')['result']['list'][0]
            return float(balance_info['totalAvailableBalance'])
        except Exception as e:
            logging.error(f'Error on retrieving balance: {e}')
            return None

    def get_ticker_info(self, symbol):
        ticker_info = self.client.get_tickers(category='inverse', symbol=symbol)
        highest_ask = float(ticker_info['result']['list'][0]['ask1Price'])
        highest_bid = float(ticker_info['result']['list'][0]['bid1Price'])
        return highest_bid, highest_ask

    def get_open_positions(self):
        return self.client.get_positions(category='linear', settleCoin='USDT')['result']['list']

    def get_position_for_symbol(self, symbol):
        open_positions = {pos['symbol']: pos for pos in self.get_open_positions()}
        position = open_positions.get(symbol)
        return position

    def set_leverage(self, symbol, leverage):
        try:
            leverage_string = str(leverage)
            response = self.client.set_leverage(symbol=symbol, buyLeverage=leverage_string,
                                                sellLeverage=leverage_string,
                                                category='linear')
            if response['ret_code'] == 0:
                logging.info(f"Leverage set to {leverage}x for {symbol}")
            else:
                logging.debug(f"Couldn't sett leverage for {symbol}, perhaps already correct")
        except Exception as e:
            logging.debug(f"Couldn't sett leverage for {symbol}: {e}")

    def get_ema(self, symbol, interval=5, period=200):
        historical_data = self.fetch_historical_data(symbol, interval, period)
        if not historical_data.empty:
            # Calculate the EMA on the 'close' column of the DataFrame
            ema = historical_data['close'].ewm(span=period, adjust=False).mean()
            return ema.iloc[-1]
        else:
            return None

    def calculate_vwap_last(self, data):
        """Calculate the last VWAP value."""
        data['TypicalPrice'] = (data['high'] + data['low'] + data['close']) / 3
        data['TPxVolume'] = data['TypicalPrice'] * data['volume']
        data['CumulativeTPxVolume'] = data['TPxVolume'].cumsum()
        data['CumulativeVolume'] = data['volume'].cumsum()
        vwap = data['CumulativeTPxVolume'] / data['CumulativeVolume']
        return vwap.iloc[-1]

    def calculate_rsi_last(self, data, length=14):
        """Calculate the last RSI value."""
        delta = data['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=length).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=length).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1]

    def calculate_bbands_last(self, data, length=20, std=2):
        """Calculate the last Bollinger Bands values."""
        mb = data['close'].rolling(window=length).mean()
        sd = data['close'].rolling(window=length).std()
        bbu = mb + (sd * std)
        bbl = mb - (sd * std)
        return bbl.iloc[-1], mb.iloc[-1], bbu.iloc[-1]

    def calculate_atr_last(self, data, length=14):
        """Calculate the last ATR value."""
        high_low = data['high'] - data['low']
        high_close = np.abs(data['high'] - data['close'].shift())
        low_close = np.abs(data['low'] - data['close'].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(window=length).mean()
        return atr.iloc[-1]

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

    def cancel_all_open_orders(self, symbol):
        try:
            if symbol is None:
                self.client.cancel_all_orders(category="linear", settleCoin="USDT")
            else:
                self.client.cancel_all_orders(category="linear", symbol=symbol)

            logging.info("All open orders cancelled successfully.")
        except Exception as e:
            logging.info(f"Error cancelling orders: {e}")

    def fetch_historical_data(self, symbol, interval, period):
        # Initialize HTTP session

        # Define the end time for the data as the current time
        end_time = int(pd.Timestamp.now().timestamp() * 1000)

        # Define the start time for the data based on the period
        start_time = end_time - (
                period * interval * 60 * 1000)  # period * interval (in minutes) * 60 (seconds) * 1000 (milliseconds)

        # Fetch historical klines from Bybit
        response = self.client.get_kline(
            category="linear",
            symbol=symbol,
            interval=interval,
            start=start_time,
            end=end_time,
        )

        # Check if the API call was successful
        if response['retCode'] == 0:
            # Convert the kline data to a pandas DataFrame
            columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover']
            data = pd.DataFrame(response['result']['list'], columns=columns)

            # Convert timestamps to numeric type before converting to datetime
            data['timestamp'] = pd.to_numeric(data['timestamp'])
            data['timestamp'] = pd.to_datetime(data['timestamp'], unit='ms')
            data.set_index('timestamp', inplace=True)

            # Convert the 'close' column to numeric values (float)
            data['close'] = data['close'].astype(float)
            return data
        else:
            logging.error(f"Error fetching historical data: {response['retMsg']}")
            return pd.DataFrame()  # Return an empty DataFrame on error

    def close_position(self, symbol, qty):
        try:
            while True:
                # Fetch current highest bid and lowest ask prices
                highest_bid, lowest_ask = self.get_ticker_info(symbol)

                # Place a limit order at the lowest ask price to increase the chance of execution
                self.client.place_order(symbol=symbol, category='linear', isLeverage='1', side="Sell",
                                        price=lowest_ask, order_type="Limit", qty=qty, reduceOnly=True)
                logging.info(f"Limit sell order placed at lowest ask {lowest_ask} for {qty} of {symbol}.")

                time.sleep(10)  # Wait for 10 seconds

                # Check if the position is closed
                if self.is_position_closed(symbol, qty):
                    logging.info(f"Position closed for {qty} of {symbol}.")
                    break

                # Fetch the current lowest ask price again
                _, new_lowest_ask = self.get_ticker_info(symbol)

                # If the new lowest ask price is lower than our order price, cancel the previous order and place a new one
                if new_lowest_ask < lowest_ask:
                    self.cancel_all_open_orders(symbol)
                    logging.info(f"Cancelled previous order. New lowest ask is lower at {new_lowest_ask}.")
                else:
                    logging.info(
                        "Current lowest ask is not lower than the order price. Checking again after 10 seconds.")

        except Exception as e:
            logging.error(f"Failed to close position for {symbol}: {e}")

    def is_position_closed(self, symbol, qty):
        position = self.get_position_for_symbol(symbol)
        if position:
            # Assuming 'size' is the key that holds the position's quantity. Adjust as per your API response.
            current_qty = float(position.get('size', 0))
            # Position is considered closed if its current quantity is less than or equal to the desired quantity.
            # This logic may need adjustment based on how you define a position being 'closed'.
            return current_qty <= qty
        else:
            # If there's no position found for the symbol, consider it closed.
            return True

    def get_account_balance(self):
        try:
            balance_info = self.client.get_wallet_balance(accountType='UNIFIED', coin='USDT')['result']['list'][0]
            return float(balance_info['totalAvailableBalance'])
        except Exception as e:
            logging.error(f'Error on retrieving balance: {e}')

    def define_instrument_info(self, symbol):
        try:
            instrument_infos = self.client.get_instruments_info(category='linear', symbol=symbol)['result']['list']
            info = instrument_infos[0]['lotSizeFilter']
            logging.info(f"Instrument info: {info}")

            return float(info['minOrderQty']), float(info['maxOrderQty']), float(info['qtyStep'])
        except Exception as e:
            logging.error(f"ERROR: Unable to determine lotSize for symbol {symbol}: {e}")
            return None, None, None

    def place_order(self, symbol, qty, price):
        try:
            self.client.place_order(symbol=symbol, category='linear', isLeverage='1', side="Buy", order_type="Limit",
                                    qty=qty, price=price)
            logging.info(f"Placed limit buy order for {qty} of {symbol} at {price}")
        except Exception as e:
            logging.info(f"Failed to place order for {symbol}: {e}")
