from abc import ABC, abstractmethod

class TradingClient(ABC):
    @abstractmethod
    def get_account_balance(self):
        pass

    @abstractmethod
    def get_ticker_info(self, symbol):
        pass

    @abstractmethod
    def get_position_for_symbol(self, symbol):
        pass

    @abstractmethod
    def set_leverage(self, symbol, leverage):
        pass

    @abstractmethod
    def fetch_historical_data(self, symbol, interval, period):
        pass

    @abstractmethod
    def get_ema(self, symbol, interval, period):
        pass

    @abstractmethod
    def place_order(self, symbol, qty, price):
        pass

    @abstractmethod
    def close_position(self, symbol, qty):
        pass

    @abstractmethod
    def cancel_all_open_orders(self, symbol):
        pass
