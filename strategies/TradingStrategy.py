from abc import ABC, abstractmethod

class TradingStrategy(ABC):
    @abstractmethod
    def check_entry_criteria(self, symbol, pos_side, ema_interval):
        pass

    @abstractmethod
    def open_position(self, symbol, side):
        pass

    @abstractmethod
    def check_exit_criteria(self, symbol, side):
        pass

    @abstractmethod
    def close_position(self, symbol, side):
        pass
