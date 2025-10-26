from _decimal import ROUND_DOWN, Decimal

from clients import TradingClient
from strategies.TradingStrategy import TradingStrategy


CONFIG = {
    'buy_until_limit': 0.02,
    'profit_threshold': 0.003, # Percentage of total as min profit, 0,002 = 0,2 % of total balance = 40 cent
    'profit_pnl': 0.1,
    'leverage': 6,
    'begin_size_of_balance': 0.006,
    'strategy_filter': 'EMA',  # Currently, only 'EMA' is supported
    'buy_below_percentage': 0.04,
}


class MartingaleTradingStrategy(TradingStrategy):
    def __init__(self, client: TradingClient, logger, notifier=None):
        super().__init__(client, logger)

        self.leverage = CONFIG['leverage']
        self.profit_threshold = CONFIG['profit_threshold']
        self.profit_pnl = CONFIG['profit_pnl']
        self.proportion_of_balance = CONFIG['begin_size_of_balance']
        self.buy_until_limit = CONFIG['buy_until_limit']
        self.notifier = notifier

    def custom_round(self, number, min_qty, max_qty, qty_step):
        number = Decimal(str(number))
        min_qty = Decimal(str(min_qty))
        max_qty = Decimal(str(max_qty))
        qty_step = Decimal(str(qty_step))

        # Perform floor rounding
        rounded_qty = (number / qty_step).quantize(Decimal('1'), rounding=ROUND_DOWN) * qty_step

        # Clamp the result within the min and max bounds
        return max(min(rounded_qty, max_qty), min_qty)

    def is_valid_position(self, position, current_price, ema_200, pos_side):
        return (position and position['margin_level'] < 2) \
            or (pos_side == 'Long' and current_price > ema_200) \
            or (pos_side == 'Short' and current_price < ema_200)

    def manage_position(self, symbol, current_price, ema_200_1h, ema_200, ema_50, position, total_balance, pos_side, automatic_mode):
        """
        Manage the current position based on profit, margin level, EMA conditions, and volatility.
        """

        conclusion = "Nothing changed"

        # Check volatility
        is_high_volatility, vol_metrics = self.client.check_volatility(symbol)

        if position:
            # Extract position details
            position_value = float(position['positionValue'])
            unrealised_pnl = float(position['unrealisedPnl'])
            upnl_percentage = float(position['upnlPercentage'])
            position_size_percentage = float(position['position_size_percentage'])
            side = "Buy" if pos_side == "Long" else "Sell"
            position_factor = position_value / total_balance
            margin_level = float(position.get('margin_level', 0))

            # Send margin warning if level is concerning (< 1.5 means close to liquidation)
            if margin_level < 1.5 and self.notifier:
                self.notifier.notify_margin_warning(
                    symbol=symbol,
                    pos_side=pos_side,
                    margin_level=margin_level,
                    position_value=position_value,
                    unrealized_pnl=unrealised_pnl
                )

            # Send high volatility alert if detected
            if is_high_volatility and self.notifier:
                trigger = vol_metrics.get('trigger', 'unknown')
                metric_value = vol_metrics.get(trigger, 0)
                threshold_key = f"{trigger}_threshold" if trigger != 'unknown' else 'threshold'
                threshold = vol_metrics.get(threshold_key, 0)

                action = "Pausing new entries" if margin_level >= 2 else "Only adding to maintain margin"

                self.notifier.notify_high_volatility(
                    symbol=symbol,
                    volatility_metric=trigger,
                    value=metric_value,
                    threshold=threshold,
                    action=action
                )

            # Validate if adding to position is allowed
            valid_position = self.is_valid_position(position, current_price, ema_50, pos_side)

            # ✅ 1. Manage profitable positions
            if (
                    unrealised_pnl/total_balance > self.profit_threshold  # If we reached our min profit amount
                    and position_factor >= self.buy_until_limit  # And we bought the minimum amount
            ):
                conclusion = self.manage_profitable_position(symbol, position, upnl_percentage,
                                                             position_size_percentage, pos_side)

            # ✅ 2. Check conditions to add to the position
            # During high volatility, only add if margin level is critical (< 2)
            elif (
                    margin_level < 2  # Critical: margin level requires maintenance
                    or (not is_high_volatility and (  # Only add during normal volatility if:
                        position_factor < self.buy_until_limit  # Position size is within limits
                        or (unrealised_pnl < 0 and upnl_percentage < -0.05  # Buy at a dip, but only if down more than 5%
                            and valid_position)  # Only on right side of EMA's
                    ))
            ):
                conclusion = self.add_to_position(symbol, current_price, total_balance, position_value,
                                                  upnl_percentage, side, pos_side)

            elif is_high_volatility:
                conclusion = f"High volatility detected ({vol_metrics.get('trigger')}), pausing new entries"

        # ✅ 3. Open a new position in automatic mode if conditions match
        # Don't open new positions during high volatility
        elif automatic_mode and not is_high_volatility and (
                (pos_side == "Long" and current_price > ema_200_1h) or
                (pos_side == "Short" and current_price < ema_200_1h)
        ):
            conclusion = self.open_new_position(symbol, current_price, total_balance, pos_side)

        elif automatic_mode and is_high_volatility:
            conclusion = f"High volatility detected ({vol_metrics.get('trigger')}), not opening new position"

        return conclusion

    def manage_profitable_position(self, symbol, position, pnl_percentage, position_value_percentage_of_total_balance,
                                   pos_side):
        """
        Manage the profitable position by partially or fully closing it based on thresholds.
        """
        size = float(position['size'])
        unrealised_pnl = float(position['unrealisedPnl'])
        position_value = float(position['positionValue'])

        # Define thresholds and corresponding actions
        thresholds = [
            (7.50, 0.33, "Closing 33% of position due to balance > 7.5%"),
            (10, 0.5, "Closing 50% of position due to balance > 10%")
        ]

        # Check thresholds and execute actions
        for threshold, close_fraction, message in thresholds:
            if position_value_percentage_of_total_balance > threshold:
                min_qty, max_qty, qty_step = self.client.define_instrument_info(symbol)
                qty = self.custom_round(size * close_fraction, min_qty, max_qty, qty_step)
                _, ask_price = self.client.get_ticker_info(symbol)
                self.client.close_position(symbol, qty, pos_side)

                # Send Telegram notification
                if self.notifier:
                    self.notifier.notify_position_closed(
                        symbol=symbol,
                        pos_side=pos_side,
                        qty=float(qty),
                        price=ask_price,
                        pnl=unrealised_pnl * close_fraction,
                        pnl_pct=pnl_percentage * 100,
                        reason=message
                    )

                return f"{message} (Current: {position_value_percentage_of_total_balance}%)"

        # Leave only min amount if profit target is reached
        if pnl_percentage > self.profit_pnl:
            _, ask_price = self.client.get_ticker_info(symbol)
            self.client.close_position(symbol, size, pos_side)

            # Send Telegram notification
            if self.notifier:
                self.notifier.notify_position_closed(
                    symbol=symbol,
                    pos_side=pos_side,
                    qty=size,
                    price=ask_price,
                    pnl=unrealised_pnl,
                    pnl_pct=pnl_percentage * 100,
                    reason="Target profit reached"
                )

            return "Closing full position, target profit reached"

        # No action needed
        return (
            f"Position above EMA but no change: unrealised={unrealised_pnl} vs target={self.profit_threshold}, "
            f"pnl_percentage={pnl_percentage} vs target={self.profit_pnl}, "
            f"position size={position_value_percentage_of_total_balance}% of balance"
        )

    def add_to_position(self, symbol, current_price, total_balance, position_value, pnl_percentage, side, pos_side):
        order_qty = self.calculate_order_quantity(symbol, total_balance, position_value, current_price, pnl_percentage)
        self.client.place_order(symbol=symbol, qty=order_qty, price=current_price, pos_side=pos_side, side=side)

        # Send Telegram notification
        if self.notifier:
            position_size_pct = (position_value / total_balance) * 100 if total_balance > 0 else 0
            self.notifier.notify_position_opened(
                symbol=symbol,
                side=side,
                pos_side=pos_side,
                qty=float(order_qty),
                price=current_price,
                balance=total_balance,
                position_size_pct=position_size_pct
            )

        return "Added to position"

    def open_new_position(self, symbol, current_price, total_balance, pos_side):
        side = "Buy" if pos_side == "Long" else "Sell"
        order_qty = self.calculate_order_quantity(symbol, total_balance, 0, current_price, 0)
        self.client.place_order(symbol=symbol, qty=order_qty, price=current_price, pos_side=pos_side, side=side)

        # Send Telegram notification
        if self.notifier:
            position_size_pct = (self.proportion_of_balance * 100)
            self.notifier.notify_position_opened(
                symbol=symbol,
                side=side,
                pos_side=pos_side,
                qty=float(order_qty),
                price=current_price,
                balance=total_balance,
                position_size_pct=position_size_pct
            )

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
        ema_200_1h = self.client.get_ema(symbol=symbol, interval=60,
                                         period=200)  # 1H EMA is leading to identify Long or Short Bias
        self.logger.info(
            "EMA info",
            extra={
                "symbol": symbol,
                "json": {
                    "ema_interval": ema_interval,
                    "ema_50": ema_50,
                    "ema_200": ema_200,
                    "ema_200_1h": ema_200_1h
                }
            })

        current_price = current_bid if pos_side == 'Long' else current_ask

        if position:
            position_value_percentage_of_total_balance = round(float(position['positionValue']) / total_balance * 100,
                                                               2)
            position['position_size_percentage'] = position_value_percentage_of_total_balance

            self.logger.info(
                "Position info",
                extra={
                    "symbol": symbol,
                    "json": {
                        "position": position
                    }
                })

        return current_price, ema_200_1h, ema_200, ema_50, position, total_balance

    def prepare_strategy(self, symbol, pos_side):
        self.client.cancel_all_open_orders(symbol, pos_side)
        self.client.set_leverage(symbol, self.leverage)

    def calculate_order_quantity(self, symbol, total_balance, position_value, current_price, pnl_percentage):
        min_qty, max_qty, qty_step = self.client.define_instrument_info(symbol)

        if position_value == 0:
            qty = (total_balance * self.proportion_of_balance) * self.leverage / current_price
        else:
            qty = (position_value * self.leverage * (-pnl_percentage)) / current_price

        qty = self.custom_round(qty, min_qty, max_qty, qty_step)

        self.logger.info(
            "Calculating order quantity",
            extra={
                "symbol": symbol,
                "json": {
                    "current_price": current_price,
                    "pnl_percentage": pnl_percentage,
                    "calculated_qty": qty
                }
            })

        return qty
