from _decimal import ROUND_DOWN, Decimal

import TradingClient


# from BybitClient import BybitClient


class MartingaleTradingStrategy:
    def __init__(self, client: TradingClient, leverage, profit_threshold, profit_pnl, proportion_of_balance,
                 buy_until_limit, logger):
        self.client = client
        self.leverage = leverage
        self.profit_threshold = profit_threshold
        self.profit_pnl = profit_pnl
        self.proportion_of_balance = proportion_of_balance
        self.buy_until_limit = buy_until_limit
        self.logger = logger

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

    def execute_strategy(self, symbol, strategy_filter, buy_below_percentage, leverage, ema_interval=5):
        self.client.cancel_all_open_orders(symbol)
        self.client.set_leverage(symbol, leverage)
        position = self.client.get_position_for_symbol(symbol)
        current_price, _ = self.client.get_ticker_info(symbol)
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

        if position:
            # Extract necessary values from the position
            pos_size = float(position['contracts']) / leverage  # Position size in contracts
            contract_size = float(position.get('contractSize', 1))  # Default to 1 if not provided
            avg_entry_price = float(position['entryPrice'])
            mark_price = float(position['markPrice'])
            margin = float(position['initialMargin'])

            # Calculate Unrealized PnL based on the provided formula
            unrealized_pnl = (pos_size * contract_size) / avg_entry_price - (pos_size * contract_size) / mark_price

            # Calculate the position value based on the average entry price
            position_value = (pos_size * contract_size) / avg_entry_price

            # Calculate PnL percentage
            unpl_percentage = unrealized_pnl / position_value * leverage
            unpl_absolute = margin * unpl_percentage

            position_value_percentage_of_total_balance = position_value / total_balance * 100


            self.logger.info(
                "Position info",
                extra={
                    "symbol": symbol,
                    "json": {
                        "position_value": position_value,
                        "unrealized_pnl": unrealized_pnl,
                        "position_value_percentage_of_total_balance": position_value_percentage_of_total_balance,
                        "TP": self.profit_threshold,
                        "TP%": self.profit_pnl
                    }
                })

        if strategy_filter != 'EMA' or current_price > ema_200:

            if position and unrealized_pnl > 0:

                if position_value_percentage_of_total_balance > 40:
                    return self.client.close_position(symbol, position['size'] * 0.5)
                elif position_value_percentage_of_total_balance > 30:
                    self.client.close_position(symbol, position['size'] * 0.4)
                elif position_value_percentage_of_total_balance > 20:
                    self.client.close_position(symbol, position['size'] * 0.3)
                elif position_value_percentage_of_total_balance > 10:
                    self.client.close_position(symbol, position['size'] * 0.2)
                elif unpl_percentage < buy_below_percentage or (
                        position_value < self.buy_until_limit and current_price > ema_50):
                    order_qty = self.calculate_order_quantity(symbol, total_balance, position_value, current_price,
                                                              unpl_percentage)
                    self.client.place_order(symbol, order_qty, current_price)
                else:
                    # Existing logic to close the entire position if profit targets are reached
                    if unpl_percentage > self.profit_pnl and unrealized_pnl > self.profit_threshold:
                        self.client.close_position(symbol, position['size'])

            else:
                order_qty = self.calculate_order_quantity(symbol, total_balance, 0, current_price, 0)
                self.client.place_order(symbol, order_qty, current_price)
        else:
            self.logger.info(
                "Skip buying below EMA",
                extra={
                    "symbol": symbol,
                    "json": {
                        "current_price": current_price,
                        "ema": ema_200,
                    }
                })

    def calculate_order_quantity(self, symbol, total_balance, position_value, current_price, pnl_percentage):
        min_qty, max_qty, qty_step = self.client.define_instrument_info(symbol)

        self.logger.info(
            "Calculating order quantity",
            extra={
                "symbol": symbol,
                "json": {
                    "total_balance": total_balance,
                    "position_value": position_value,
                    "current_price": current_price,
                    "pnl_percentage": pnl_percentage
                }
            })

        if position_value == 0:  # No open position 100 * 0,05 / 20
            qty = (total_balance * self.proportion_of_balance) / current_price
        else:
            qty = (position_value * (-pnl_percentage)) / current_price

        return self.custom_round(qty, min_qty, max_qty, qty_step)
