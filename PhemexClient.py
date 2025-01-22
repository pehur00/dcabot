import hashlib
import hmac
import json
import logging
import time
from math import trunc

import pandas as pd
import requests

from TradingClient import TradingClient


class PhemexAPIException(TradingClient, Exception):
    def __init__(self, response):
        self.code = 0
        try:
            json_res = response.json()
        except ValueError:
            self.message = f'Invalid error message: {response.text}'
        else:
            if 'code' in json_res:
                self.code = json_res['code']
                self.message = json_res['msg']
            else:
                self.code = json_res['error']['code']
                self.message = json_res['error']['message']
        self.status_code = response.status_code
        self.response = response
        self.request = getattr(response, 'request', None)

    def __str__(self):
        return f'HTTP(code={self.status_code}), API(errorcode={self.code}): {self.message}'


class PhemexClient():
    MAIN_NET_API_URL = 'https://api.phemex.com'
    TEST_NET_API_URL = 'https://testnet-api.phemex.com'

    def __init__(self, api_key, api_secret, testnet=False):
        self.api_key = api_key
        self.api_secret = api_secret
        self.api_URL = self.TEST_NET_API_URL if testnet else self.MAIN_NET_API_URL
        self.session = requests.session()

    def _send_request(self, method, endpoint, params=None, body=None):
        if params is None:
            params = {}
        if body is None:
            body = {}
        expiry = str(trunc(time.time()) + 60)
        query_string = '&'.join([f'{k}={v}' for k, v in params.items()])
        message = endpoint + query_string + expiry
        body_str = ""
        if body:
            body_str = json.dumps(body, separators=(',', ':'))
            message += body_str
        signature = hmac.new(self.api_secret.encode('utf-8'), message.encode('utf-8'), hashlib.sha256)
        self.session.headers.update({
            'x-phemex-request-signature': signature.hexdigest(),
            'x-phemex-request-expiry': expiry,
            'x-phemex-access-token': self.api_key,
            'Content-Type': 'application/json'
        })

        url = self.api_URL + endpoint
        if query_string:
            url += '?' + query_string
        response = self.session.request(method, url, data=body_str.encode())
        if not str(response.status_code).startswith('2'):
            raise PhemexAPIException(response)
        try:
            res_json = response.json()
        except ValueError:
            raise PhemexAPIException(f'Invalid Response: {response.text}')
        if "code" in res_json and res_json["code"] != 0:
            raise PhemexAPIException(response)
        if "error" in res_json and res_json["error"]:
            raise PhemexAPIException(response)
        return res_json

    def get_account_balance(self):
        try:
            response = self._send_request("GET", "/g-accounts/accountPositions", {'currency': 'USDT'})
            balance_info = response['data']['account']
            usdt_balance = balance_info.get('accountBalanceRv', 0)
            return float(usdt_balance)
        except PhemexAPIException as e:
            logging.error(f"Failed to get account balance: {e}")
            return None

    def get_ticker_info(self, symbol):
        try:
            response = self._send_request("GET", "/md/v3/ticker/24hr", {'symbol': symbol})
            logging.debug(f"response from ticker info: {response}")
            ticker = response['result']
            highest_bid = float(ticker['bidRp'])
            highest_ask = float(ticker['askRp'])
            return highest_bid, highest_ask
        except PhemexAPIException as e:
            logging.error(f"Failed to fetch ticker info for {symbol}: {e}")
            return None, None

    def get_position_for_symbol(self, symbol):
        try:
            response = self._send_request("GET", "/g-accounts/accountPositions", {'currency': 'USDT'})
            positions = response['data']['positions']
            position = next((p for p in positions if p['symbol'] == symbol), None)
            if position:
                position_value = float(position.get('positionMarginRv', 0))
                unrealised_pnl = float(position.get('curTermRealisedPnlRv', 0))
                size = float(position.get('size', 0))

                if size == 0:
                    return None

                return {
                    'positionValue': position_value,
                    'unrealisedPnl': unrealised_pnl,
                    'size': size
                }
            else:
                logging.info(f"No position found for symbol: {symbol}")
                return None
        except PhemexAPIException as e:
            logging.error(f"Failed to get position for {symbol}: {e}")
            return None

    def define_instrument_info(self, symbol):
        # Send request to Phemex API to retrieve all product information

        product_info = self.get_product_info(symbol)
        if product_info:
            # Extract relevant information for perpetual contracts
            qty_step_size = float(product_info.get('qtyStepSize', 0))
            max_order_qty_rq = float(product_info.get('maxOrderQtyRq', 0))
            min_order_qty = qty_step_size  # Assuming min_order_qty is the same as qty_step_size
            logging.info(
                f"Instrument info for {symbol}: min_order_qty={min_order_qty}, max_order_qty={max_order_qty_rq}, qty_step={qty_step_size}")
            return min_order_qty, max_order_qty_rq, qty_step_size
        else:
            logging.error(f"Symbol {symbol} not found in product list.")
            return None, None, None

    def get_product_info(self, symbol):
        try:
            response = self._send_request("GET", "/public/products")

            if response['code'] == 0:
                products = response['data']['perpProductsV2']
                # Find the product matching the specified symbol
                product_info = next((item for item in products if item['symbol'] == symbol), None)
                return product_info
            else:
                logging.error(f"Failed to retrieve products: {response['msg']}")
                return None, None, None
        except Exception as e:
            logging.error(f"ERROR: Unable to determine lot size for symbol {symbol}: {e}")
            return None, None, None

    def set_leverage(self, symbol, leverage):
        try:
            # Determine the appropriate parameter based on the leverage value
            if leverage > 0:
                # Isolated margin mode
                params = {
                    'symbol': symbol,
                    'leverageRr': str(leverage)
                }
            else:
                # Cross margin mode
                params = {
                    'symbol': symbol,
                    'leverageRr': '0'
                }

            # Send the request to set leverage

            # TODO Disabled because of ERROR:root:Failed to set leverage for {symbol}: HTTP(code=200), API(errorcode=20004):
            # TODO TE_ERR_INCONSISTENT_POS_MODE
            logging.info("Leverage should be altered manually in Phemex because of known error. ")
            # response = self._send_request("PUT", "/g-positions/leverage", params=params)

            # Check if the response indicates success
            # if response.get('code') == 0:
            #     logging.info(f"Leverage set to {leverage}x for {symbol}")
            # else:
            #     logging.error(f"Failed to set leverage for {symbol}: {response.get('msg')}")
        except PhemexAPIException as e:
            logging.error(f"Failed to set leverage for {symbol}: {e}")

    def fetch_historical_data(self, symbol, interval, period):
        """
        Fetch historical kline data for a given symbol and interval, returning the most recent 'period' data points.

        :param symbol: Trading pair symbol, e.g., 'BTCUSDT'.
        :param interval: Interval in minutes, e.g., 1, 5, 15.
        :param period: Number of data points to retrieve.
        :return: DataFrame containing the most recent 'period' data points.
        """
        try:
            # Define the resolution mapping based on Phemex API documentation
            resolution_mapping = {
                1: 60,
                5: 300,
                15: 900,
                30: 1800,
                60: 3600,
                240: 14400,
                1440: 86400,
                10080: 604800,
                43200: 2592000,
                129600: 7776000,
                518400: 31104000
            }

            if interval not in resolution_mapping:
                logging.error(f"Unsupported interval: {interval} minutes")
                return pd.DataFrame()

            resolution = resolution_mapping[interval]

            # Define the available limits as per Phemex API documentation
            available_limits = [5, 10, 50, 100, 500, 1000]

            # Determine the appropriate limit to request
            request_limit = next((l for l in available_limits if l >= period), available_limits[-1])

            # Send request to Phemex API
            response = self._send_request(
                "GET",
                "/exchange/public/md/v2/kline/last",
                params={
                    'symbol': symbol,
                    'resolution': resolution,
                    'limit': request_limit
                }
            )

            logging.debug(f"Kline data from API: {response}")

            if response['code'] == 0:
                rows = response['data']['rows']
                # Create DataFrame from the retrieved data
                data = pd.DataFrame(rows, columns=[
                    'timestamp', 'interval', 'last_close', 'open', 'high', 'low', 'close', 'volume', 'turnover',
                    'symbol'
                ])

                # Convert 'timestamp' to datetime and set as index
                data['timestamp'] = pd.to_datetime(data['timestamp'], unit='ms')
                data.set_index('timestamp', inplace=True)

                # Select relevant columns and ensure correct data types
                data = data[['open', 'high', 'low', 'close', 'volume', 'turnover']].astype(float)

                # Sort data by timestamp to ensure chronological order
                data.sort_index(inplace=True)

                # Trim the DataFrame to the most recent 'period' entries
                if len(data) > period:
                    data = data.tail(period)

                return data
            else:
                logging.error(f"Failed to fetch historical data: {response['msg']}")
                return pd.DataFrame()
        except Exception as e:
            logging.error(f"Error fetching historical data for {symbol}: {e}")
            return pd.DataFrame()

    def get_ema(self, symbol, interval=5, period=200):
        historical_data = self.fetch_historical_data(symbol, interval, period)
        if not historical_data.empty:
            ema = historical_data['close'].ewm(span=period, adjust=False).mean()
            return ema.iloc[-1]
        else:
            return None

    def place_order(self, symbol, qty, price, side="Buy", order_type="Limit", time_in_force="GoodTillCancel",
                    posSide="Long", reduceOnly=False):
        logging.info(f"Ordering symbol={symbol}, qty={qty}, price={price}")

        try:
            # Generate a unique client order ID
            cl_ord_id = f"order_{int(time.time() * 1000)}"

            # Retrieve instrument information to get the price scale
            min_order_qty, max_order_qty, qty_step = self.define_instrument_info(symbol)
            if min_order_qty is None:
                logging.error(f"Failed to retrieve instrument info for {symbol}")
                return

            order = {
                "symbol": symbol,
                "clOrdID": cl_ord_id,
                "side": side,
                "orderQtyRq": f"{qty}",
                "priceRp": f"{price}",
                "ordType": order_type,
                "timeInForce": time_in_force,
                "posSide": posSide,
                "reduceOnly": reduceOnly
            }

            # Send the order request
            response = self._send_request("POST", "/g-orders", body=order)
            logging.info(f"Placed order: {response}")

        except PhemexAPIException as e:
            logging.error(f"Failed to place order for {symbol}: {e}")

    def close_position(self, symbol, qty):
        try:
            position = self.get_position_for_symbol(symbol)
            if position and position['size'] >= qty:
                self.place_order(symbol=symbol, qty=qty, order_type="Market", reduceOnly=True)  # Market close position
                logging.info(f"Closed position for {symbol}: {position}")
        except PhemexAPIException as e:
            logging.error(f"Failed to close position for {symbol}: {e}")

    def cancel_all_open_orders(self, symbol):
        try:
            # Cancel active orders, including triggered conditional orders
            self._send_request("DELETE", "/g-orders/all", params={"symbol": symbol, "untriggered": "false"})
            logging.info(f"All active orders for {symbol} have been cancelled.")

            # Cancel untriggered conditional orders
            self._send_request("DELETE", "/g-orders/all", params={"symbol": symbol, "untriggered": "true"})
            logging.info(f"All untriggered conditional orders for {symbol} have been cancelled.")
        except PhemexAPIException as e:
            logging.error(f"Failed to cancel all open orders for {symbol}: {e}")
