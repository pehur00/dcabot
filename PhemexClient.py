import ccxt
import logging
import pandas as pd
from TradingClient import TradingClient


class PhemexClient(TradingClient):
    def __init__(self, api_key, api_secret, logger, testnet=False):
        self.logger = logger

        exchange_class = ccxt.phemex
        self.exchange = exchange_class({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'swap',  # For perpetual contracts
            },
        })

        if testnet:
            self.exchange.set_sandbox_mode(True)

    def get_account_balance(self):
        try:
            balance = self.exchange.fetch_balance(params={"type": "swap"})
            usdt_balance = balance.get('USDT', {}).get('free', 0)
            used_balance = balance.get('USDT', {}).get('used', 0)
            return float(usdt_balance), float(used_balance)
        except Exception as e:
            self.logger.error(
                "Failed to get account balance",
                extra={"error_details": str(e)}
            )
            return None

    def get_ticker_info(self, symbol):
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            highest_bid = ticker.get("bid", None)
            highest_ask = ticker.get('ask', None)
            # Todo: bid and ask return None, seems to be related to CCXT using v2 (which has no bid/ask)
            # https://phemex-docs.github.io/#query-24-ticker
            # self.v2GetMdV2Ticker24hr(self.extend(request, params))
            # which links to
            #   - v2_get_md_v2_ticker_24hr = v2GetMdV2Ticker24hr = Entry('md/v2/ticker/24hr', 'v2', 'GET', {'cost': 5})
            return highest_bid, highest_ask
        except Exception as e:
            self.logger.error(
                "Failed to fetch ticker info",
                extra={
                    "symbol": symbol,
                    "json": {"error_description": str(e)}
                }
            )
            return None, None

    def fetch_historical_data(self, symbol, interval, period):
        try:
            timeframe_mapping = {
                1: '1m',
                5: '5m',
                15: '15m',
                30: '30m',
                60: '1h',
                240: '4h',
                1440: '1d',
            }

            if interval not in timeframe_mapping:
                self.logger.error(
                    "Unsupported interval",
                    extra={
                        "symbol": symbol,
                        "json": {"error_description": f"Interval {interval} is not supported."}
                    }
                )
                return pd.DataFrame()

            timeframe = timeframe_mapping[interval]
            candles = self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=period)

            data = pd.DataFrame(candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            # Select relevant columns and ensure correct data types
            data = data[['open', 'high', 'low', 'close', 'volume']].astype(float)

            # Sort data by timestamp to ensure chronological order
            data.sort_index(inplace=True)

            # Trim the DataFrame to the most recent 'period' entries
            if len(data) > period:
                data = data.tail(period)

            return data

        except Exception as e:
            self.logger.error(
                "Error fetching historical data",
                extra={
                    "symbol": symbol,
                    "json": {"error_description": str(e)}
                }
            )
            return pd.DataFrame()

    def place_order(self, symbol, qty, price=None, side="buy", order_type="limit"):
        try:
            order_params = {
                'symbol': symbol,
                'side': side,
                'amount': qty,
                'price': price,
                'type': order_type,
            }

            order = self.exchange.create_order(
                symbol=symbol,
                type=order_type,
                side=side,
                amount=qty,
                price=price,
            )

            self.logger.info(
                "Placed order",
                extra={
                    "symbol": symbol,
                    "json": {"order": order}
                }
            )

        except Exception as e:
            self.logger.error(
                "Failed to place order",
                extra={
                    "symbol": symbol,
                    "json": {"error_description": str(e)}
                }
            )

    def cancel_all_open_orders(self, symbol):
        try:
            canceled_orders = self.exchange.cancel_all_orders(symbol=symbol)
            self.logger.info(
                "Cancelled all open orders",
                extra={"symbol": symbol, "json": {"orders": canceled_orders}}
            )
        except Exception as e:
            self.logger.error(
                "Failed to cancel all open orders",
                extra={
                    "symbol": symbol,
                    "json": {"error_description": str(e)}
                }
            )

    def get_ema(self, symbol, interval=5, period=200):
        """
        Calculate the EMA for a given symbol, interval, and period.

        Args:
            symbol (str): The trading symbol (e.g., 'BTC/USDT').
            interval (int): The interval in minutes (e.g., 5 for 5-minute candles).
            period (int): The number of periods for the EMA calculation.

        Returns:
            float: The latest EMA value, or None if the data is unavailable.
        """
        try:
            return self.calculate_ema(symbol, interval, period)
        except Exception as e:
            self.logger.error(
                "Error calculating EMA",
                extra={
                    "symbol": symbol,
                    "json": {"error_description": str(e), "interval": interval, "period": period}
                }
            )
            return None

    def calculate_ema(self, symbol, interval, period):
        """
        Calculate the EMA for the given symbol, interval, and period.
        """
        # Define the available limits as per Phemex API documentation
        available_periods = [5, 10, 50, 100, 500, 1000]

        # Determine the appropriate limit to request
        request_period = next((l for l in available_periods if l >= period), available_periods[-1])

        historical_data = self.fetch_historical_data(symbol, interval, request_period)
        if not historical_data.empty:
            ema = historical_data['close'].ewm(span=period, adjust=False).mean()
            latest_ema = ema.iloc[-1]
            self.logger.info(
                "Calculated EMA",
                extra={
                    "symbol": symbol,
                    "action": "calculate_ema",
                    "json": {
                        "ema_value": latest_ema,
                        "interval": interval,
                        "period": period,
                    }
                }
            )
            return latest_ema
        else:
            self.logger.warning(
                "No historical data available to calculate EMA",
                extra={"symbol": symbol, "json": {"interval": interval, "period": period}}
            )
            return None

    def close_position(self, symbol):
        """
        Close the position for the given symbol.
        """
        try:
            position = self.get_position_for_symbol(symbol)
            if position and position['size'] > 0:
                side = 'sell' if position['side'] == 'buy' else 'buy'
                self.place_order(symbol, abs(position['size']), side=side, order_type="market")
                self.logger.info(
                    "Closed position",
                    extra={
                        "symbol": symbol,
                        "action": "close_position",
                        "json": {"size": position['size'], "side": position['side']}
                    }
                )
            else:
                self.logger.info(
                    "No open position to close",
                    extra={"symbol": symbol, "action": "close_position"}
                )
        except Exception as e:
            self.logger.error(
                "Failed to close position",
                extra={
                    "symbol": symbol,
                    "json": {"error_description": str(e)}
                }
            )

    def get_position_for_symbol(self, symbol):
        """
        Get the position details for the given symbol.
        """
        try:
            positions = self.exchange.fetch_positions(symbols=[symbol],
                                  params={"code": "USDT"})
            for position in positions:
                if float(position.get('info', {}).get('size', 0)) > 0:
                    self.logger.info(
                        "Fetched position for symbol",
                        extra={"symbol": symbol, "json": position}
                    )

                    return position
            return None
        except Exception as e:
            self.logger.error(
                "Failed to fetch position for symbol",
                extra={
                    "symbol": symbol,
                    "json": {"error_description": str(e)}
                }
            )
            return None

    def set_leverage(self, symbol, leverage):
        """
        Set the leverage for the given symbol.
        """
        try:
            self.exchange.set_leverage(leverage, symbol)
            self.logger.info(
                "Set leverage",
                extra={
                    "symbol": symbol,
                    "action": "set_leverage",
                    "json": {"leverage": leverage}
                }
            )
        except Exception as e:
            self.logger.error(
                "Failed to set leverage",
                extra={
                    "symbol": symbol,
                    "json": {"error_description": str(e)}
                }
            )
