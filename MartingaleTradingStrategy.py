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

    def execute_strategy(self, symbol, strategy_filter, buy_below_percentage, leverage, pos_side, ema_interval=5):
        self.prepare_strategy(leverage, symbol)

        current_price, ema_200, ema_50, position, total_balance = self.retrieve_information(ema_interval, symbol, pos_side)

        if position:
            position_value = float(position['positionValue'])
            unrealized_pnl = float(position['unrealisedPnl'])
            position_pos_side = position['posSide']
            size = float(position['size'])
            pnl_percentage = unrealized_pnl / position_value
            position_value_percentage_of_total_balance = position_value / total_balance * 100

            self.logger.info(
                "Position info",
                extra={
                    "symbol": symbol,
                    "json": {
                        "position_pos_side": pos_side,
                        "position_size": size,
                        "position_value": position_value,
                        "unrealized_pnl": unrealized_pnl,
                        "position_value_percentage_of_total_balance": position_value_percentage_of_total_balance,
                        "TP": self.profit_threshold,
                        "TP%": self.profit_pnl
                    }
                })

        if strategy_filter != 'EMA' or (
                (pos_side == 'Long' and current_price > ema_200) or
                (pos_side == 'Short' and current_price < ema_200)
        ):

            side = "Buy" if pos_side == "Long" else "Sell"

            if position and unrealized_pnl > 0:
                if position_value_percentage_of_total_balance > 40:
                    return self.client.close_position(symbol, position['size'] * 0.5, pos_side)
                elif position_value_percentage_of_total_balance > 30:
                    self.client.close_position(symbol, position['size'] * 0.4, pos_side)
                elif position_value_percentage_of_total_balance > 20:
                    self.client.close_position(symbol, position['size'] * 0.3, pos_side)
                elif position_value_percentage_of_total_balance > 10:
                    self.client.close_position(symbol, position['size'] * 0.2, pos_side)
                elif pnl_percentage < buy_below_percentage or (
                        position_value < self.buy_until_limit and ((pos_side == 'Long' and current_price > ema_50) or
                                                                   (pos_side == 'Short' and current_price < ema_50))):
                    order_qty = self.calculate_order_quantity(symbol, total_balance, position_value, current_price,
                                                              pnl_percentage)
                    self.client.place_order(symbol=symbol, qty=order_qty, price=current_price, pos_side=pos_side, side=side)
                else:
                    # Existing logic to close the entire position if profit targets are reached
                    if pnl_percentage > self.profit_pnl and unrealized_pnl > self.profit_threshold:
                        self.client.close_position(symbol, position['size'])

            else:
                order_qty = self.calculate_order_quantity(symbol, total_balance, 0, current_price, 0)
                self.client.place_order(symbol=symbol, qty=order_qty, price=current_price, pos_side=pos_side, side=side)
        else:
            self.logger.info(
                "Skip ordering on wrong side of EMA",
                extra={
                    "symbol": symbol,
                    "json": {
                        "current_price": current_price,
                        "ema": ema_200,
                    }
                })

    def retrieve_information(self, ema_interval, symbol, pos_side):
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

    def prepare_strategy(self, leverage, symbol):
        self.client.cancel_all_open_orders(symbol)
        self.client.set_leverage(symbol, leverage)

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
