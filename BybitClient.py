import logging
from decimal import Decimal
from pybit.unified_trading import HTTP
import pandas as pd
import TradingClient


class BybitClient(TradingClient):
    def __init__(self, api_key, api_secret, testnet=False):
        self.client = HTTP(testnet=testnet, api_key=api_key, api_secret=api_secret)

    def get_account_balance(self):
        try:
            response = self.client.get_wallet_balance(accountType='UNIFIED', coin='USDT')
            balance_info = response['result']['list'][0]
            return float(balance_info['totalAvailableBalance'])
        except Exception as e:
            logging.error(f"Failed to retrieve account balance: {e}")
            return None

    def get_ticker_info(self, symbol):
        try:
            response = self.client.get_tickers(category='inverse', symbol=symbol)
            ticker = response['result']['list'][0]
            bid = float(ticker['bid1Price'])
            ask = float(ticker['ask1Price'])
            return bid, ask
        except Exception as e:
            logging.error(f"Failed to fetch ticker info for {symbol}: {e}")
            return None, None

    def get_position_for_symbol(self, symbol):
        try:
            response = self.client.get_positions(category="inverse", symbol=symbol)
            return response
        except Exception as e:
            logging.error(f"Failed to retrieve position for {symbol}: {e}")
            return None

    def set_leverage(self, symbol, leverage):
        try:
            leverage_str = str(leverage)
            self.client.set_leverage(
                symbol=symbol,
                buyLeverage=leverage_str,
                sellLeverage=leverage_str,
                category='inverse'
            )
            logging.info(f"Leverage set to {leverage}x for {symbol}")
        except Exception as e:
            logging.error(f"Failed to set leverage for {symbol}: {e}")

    def fetch_historical_data(self, symbol, interval, period):
        try:
            end_time = int(pd.Timestamp.now().timestamp() * 1000)
            start_time = end_time - (period * interval * 60 * 1000)

            response = self.client.get_kline(
                category="inverse",
                symbol=symbol,
                interval=interval,
                start=start_time,
                end=end_time,
            )
            if response['retCode'] == 0:
                data = pd.DataFrame(response['result']['list'], columns=[
                    'timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover'
                ])
                data['timestamp'] = pd.to_datetime(data['timestamp'], unit='ms')
                data.set_index('timestamp', inplace=True)
                data = data.astype(float)
                return data
            else:
                logging.error(f"Failed to fetch historical data: {response['retMsg']}")
                return pd.DataFrame()
        except Exception as e:
            logging.error(f"Error fetching historical data for {symbol}: {e}")
            return pd.DataFrame()

    def calculate_ema(self, symbol, interval, period):
        data = self.fetch_historical_data(symbol, interval, period)
        if not data.empty:
            return data['close'].ewm(span=period, adjust=False).mean().iloc[-1]
        return None

    def place_order(self, symbol, qty, price):
        try:
            self.client.place_order(
                symbol=symbol,
                category='spot',
                side="Buy",
                qty=qty,
                price=price,
                order_type="Limit"
            )
            logging.info(f"Placed limit order for {qty} of {symbol} at {price}")
        except Exception as e:
            logging.error(f"Failed to place order for {symbol}: {e}")

    def close_position(self, symbol, qty):
        try:
            while True:
                bid, ask = self.get_ticker_info(symbol)
                self.client.place_order(
                    symbol=symbol,
                    category='spot',
                    side="Sell",
                    qty=qty,
                    price=ask,
                    order_type="Limit",
                    reduceOnly=True
                )
                logging.info(f"Limit sell order placed at {ask} for {qty} of {symbol}")
                break
        except Exception as e:
            logging.error(f"Failed to close position for {symbol}: {e}")

    def cancel_all_open_orders(self, symbol):
        try:
            self.client.cancel_all_orders(category="inverse", symbol=symbol)
            logging.info("All open orders cancelled successfully.")
        except Exception as e:
            logging.error(f"Failed to cancel orders: {e}")
