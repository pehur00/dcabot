class MartingaleStrategy(TradingStrategy):
    def __init__(self, trading_client, logger):
        self.trading_client = trading_client
        self.logger = logger

    def check_entry_criteria(self, symbol, pos_side, ema_interval):
        current_price, ema_200, ema_50, position, total_balance = self.retrieve_information(ema_interval, symbol, pos_side)


        # Check if we should buy based off EMA
        current_bid, current_ask = self.trading_client.get_ticker_info(symbol)
        current_price = current_bid if pos_side == "Long" else current_ask
        ema_200 = self.trading_client.get_ema(symbol, ema_interval, 200)

        if pos_side == "Long":
            return current_price < ema_200
        else:
            return current_price > ema_200

    def open_position(self, symbol, side):
        # Open position logic
        try:
            qty = 1  # Example qty
            price = None  # Market price
            self.trading_client.place_order(symbol, qty, price, side)
            return True
        except Exception as e:
            self.logger.error(f"Failed to open position for {symbol}: {e}")
            return False

    def check_exit_criteria(self, symbol, side):
        # Example logic for checking exit
        position = self.trading_client.get_position_for_symbol(symbol, side)
        if position and position["unrealisedPnl"] > 0.1:
            return True
        return False

    def close_position(self, symbol, side):
        # Close position logic
        try:
            self.trading_client.cancel_all_open_orders(symbol)
            return True
        except Exception as e:
            self.logger.error(f"Failed to close position for {symbol}: {e}")
            return False




    def __retrieve_information(self, ema_interval, symbol, pos_side):
        position = self.client.get_position_for_symbol(symbol, pos_side)
        current_bid, current_ask = self.client.get_ticker_info(symbol)
        total_balance, used_balance = self.client.get_account_balance()


        self.logger.info(
            "Balance info",
            extra={
                "json": {
                    "total_balance": total_balance,
                    "used_balance": used_balance
                }
            })
        ema_50 = self.client.get_ema(symbol=symbol, interval=ema_interval, period=50)
        ema_200 = self.client.get_ema(symbol=symbol, interval=ema_interval, period=200)
        self.logger.info(
            "EMA info",
            extra={
                "symbol": symbol,
                "json": {
                    "ema_interval": ema_interval,
                    "ema_50": ema_50,
                    "ema_200": ema_200
                }
            })

        current_price = current_bid if pos_side == 'Long' else current_ask

        return current_price, ema_200, ema_50, position, total_balance
