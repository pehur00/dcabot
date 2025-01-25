from abc import ABC, abstractmethod


class TradingStrategy(ABC):
    def __init__(self, client, logger):
        self.client = client
        self.logger = logger

    @abstractmethod
    def prepare_strategy(self, leverage, symbol):
        """
        Prepare the strategy by setting leverage and canceling any open orders.
        """
        pass

    @abstractmethod
    def retrieve_information(self, ema_interval, symbol, pos_side):
        """
        Fetch all necessary information such as balance, position, and EMA values.
        """
        pass

    @abstractmethod
    def manage_position(self, symbol, current_price, ema_200, ema_50, position, total_balance, buy_below_percentage, pos_side):
        """
        Evaluate and manage the current position.
        """
        pass

    @abstractmethod
    def calculate_order_quantity(self, symbol, total_balance, position_value, current_price, pnl_percentage):
        """
        Calculate the order quantity based on strategy parameters and market conditions.
        """
        pass
