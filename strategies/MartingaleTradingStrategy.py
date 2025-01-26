from _decimal import ROUND_DOWN, Decimal

from clients import TradingClient
from strategies.TradingStrategy import TradingStrategy


class MartingaleTradingStrategy(TradingStrategy):
    def __init__(self, client: TradingClient, leverage, profit_threshold, profit_pnl, proportion_of_balance,
                 buy_until_limit, logger):
        super().__init__(client, logger)

        self.leverage = leverage
        self.profit_threshold = profit_threshold
        self.profit_pnl = profit_pnl
        self.proportion_of_balance = proportion_of_balance
        self.buy_until_limit = buy_until_limit

    def custom_round(self, number, min_qty, max_qty, qty_step):
        number = Decimal(str(number))
        min_qty = Decimal(str(min_qty))
        max_qty = Decimal(str(max_qty))
        qty_step = Decimal(str(qty_step))

        # Perform floor rounding
        rounded_qty = (number / qty_step).quantize(Decimal('1'), rounding=ROUND_DOWN) * qty_step

        # Clamp the result within the min and max bounds
        return max(min(rounded_qty, max_qty), min_qty)

    def is_valid_position(self, current_price, ema_200, pos_side):
        return (pos_side == 'Long' and current_price > ema_200) or (pos_side == 'Short' and current_price < ema_200)

    def manage_position(self, symbol, current_price, ema_200, ema_50, position, total_balance,
                        buy_below_percentage, pos_side):

        conclusion = "Nothing changed"

        if position:
            position_value = float(position['positionValue'])
            unrealized_pnl = float(position['unrealisedPnl'])
            size = float(position['size'])
            upnl_percentage = unrealized_pnl / position_value
            position_value_percentage_of_total_balance = round(position_value / total_balance * 100, 2)

            self.logger.info(
                "Position info",
                extra={
                    "symbol": symbol,
                    "json": {
                        "position_size": size,
                        "position_value": position_value,
                        "unrealized_pnl": unrealized_pnl,
                        "upnl_percentage": upnl_percentage,
                        "position_value_percentage_of_total_balance": position_value_percentage_of_total_balance,
                    }
                })

            side = "Buy" if pos_side == "Long" else "Sell"

            if unrealized_pnl > self.profit_threshold:
                conclusion = self.manage_profitable_position(symbol, position, upnl_percentage,
                                                             position_value_percentage_of_total_balance, pos_side)
            elif position_value < self.buy_until_limit or (unrealized_pnl < 0 and self.is_valid_position(current_price, ema_50, pos_side)):
                conclusion = self.add_to_position(symbol, current_price, total_balance, position_value, upnl_percentage,
                                              side,
                                              pos_side)
        else:
            conclusion = self.open_new_position(symbol, current_price, total_balance, pos_side)

        return conclusion

    def manage_profitable_position(self, symbol, position, pnl_percentage, position_value_percentage_of_total_balance,
                                   pos_side):
        size = float(position['size'])

        un_pln = float(position['unrealisedPnl'])
        if position_value_percentage_of_total_balance > 30:
            self.client.close_position(symbol, size * 0.3, pos_side)
            return f"Requested closing 30% of positon because of position size vs balance > " \
                   f"{position_value_percentage_of_total_balance}%"
        elif position_value_percentage_of_total_balance > 20:
            self.client.close_position(symbol, size * 0.2, pos_side)
            return f"Requested closing 20% of positon because of position size vs balance > " \
                   f"{position_value_percentage_of_total_balance}%"
        elif position_value_percentage_of_total_balance > 15:
            self.client.close_position(symbol, size * 0.1, pos_side)
            return f"Requested closing 10% of positon because of position size vs balance > " \
                   f"{position_value_percentage_of_total_balance}%"
        elif pnl_percentage > self.profit_pnl:
            self.client.close_position(symbol, size, pos_side)
            return f"Requested closing position, target reached"

        return f"Position above EMA but need no change: unrealised={un_pln} vs min target={self.profit_threshold}," \
               f" pnl_percentage={pnl_percentage} vs target={self.profit_pnl}" \
               f" and position size = {position_value_percentage_of_total_balance}% of balance"

    def add_to_position(self, symbol, current_price, total_balance, position_value, pnl_percentage, side, pos_side):
        order_qty = self.calculate_order_quantity(symbol, total_balance, position_value, current_price, pnl_percentage)
        self.client.place_order(symbol=symbol, qty=order_qty, price=current_price, pos_side=pos_side, side=side)
        return "Added to position"

    def open_new_position(self, symbol, current_price, total_balance, pos_side):
        side = "Buy" if pos_side == "Long" else "Sell"
        order_qty = self.calculate_order_quantity(symbol, total_balance, 0, current_price, 0)
        self.client.place_order(symbol=symbol, qty=order_qty, price=current_price, pos_side=pos_side, side=side)
        return "Opened new position"

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
                    "position_value": position_value,
                    "current_price": current_price,
                    "pnl_percentage": pnl_percentage
                }
            })

        if position_value == 0:
            qty = (total_balance * self.proportion_of_balance) / current_price
        else:
            qty = (position_value * (-pnl_percentage)) / current_price

        return self.custom_round(qty, min_qty, max_qty, qty_step)
