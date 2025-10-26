from workflows.Workflow import Workflow



class MartingaleTradingWorkflow(Workflow):
    def __init__(self, strategy, logger):
        super().__init__(logger, strategy)

    def execute(self, symbol, pos_side, ema_interval, automatic_mode):
        try:
            self.logger.info(
                "Starting workflow",
                extra={
                    "symbol": symbol,
                    "json": {
                        "strategy": "MartinGale",
                        "pos_side": pos_side,
                        "ema_interval": ema_interval,
                        "automatic_mode": automatic_mode
                    }
                }
            )

            # Step 1: Prepare the strategy
            self.strategy.prepare_strategy(symbol, pos_side)

            # Step 2: Retrieve required information
            current_price, ema_200, ema_50, position, total_balance = self.strategy.retrieve_information(
                ema_interval, symbol, pos_side
            )

            # Step 3: Determine and execute actions based on strategy
            if self.strategy.is_valid_position(position=position, current_price=current_price, ema_200=ema_200, pos_side=pos_side):
                conclusion = self.strategy.manage_position(
                    symbol=symbol, current_price=current_price,
                    ema_200=ema_200, ema_50=ema_50, position=position, total_balance=total_balance,
                    pos_side=pos_side, automatic_mode=automatic_mode
                )
                self.logger.info(
                    "Position managed",
                    extra={
                        "symbol": symbol,
                        "json": {
                            "pos_side": pos_side,
                            "conclusion": conclusion
                        }
                    })
            else:
                # Determine the specific reason for skipping
                if not position:
                    if pos_side == "Long":
                        reason = f"No position - waiting for price > EMA200 (current: {current_price}, EMA200: {ema_200})"
                    else:
                        reason = f"No position - waiting for price < EMA200 (current: {current_price}, EMA200: {ema_200})"
                    margin_level = None
                else:
                    margin_level = position.get('margin_level', 0)
                    if pos_side == "Long" and current_price <= ema_200:
                        reason = f"Long position with price <= EMA200 (margin level: {margin_level:.2f}, safe - no action needed)"
                    elif pos_side == "Short" and current_price >= ema_200:
                        reason = f"Short position with price >= EMA200 (margin level: {margin_level:.2f}, safe - no action needed)"
                    else:
                        reason = f"Position exists with safe margin level ({margin_level:.2f} >= 2.0)"

                self.logger.info(
                    "Skipping position management",
                    extra={
                        "symbol": symbol,
                        "json": {
                            "reason": reason,
                            "current_price": current_price,
                            "ema_200": ema_200,
                            "margin_level": margin_level,
                            "pos_side": pos_side
                        }
                    }
                )

        except Exception as e:
            self.logger.error(f"Error in workflow execution for {symbol}: {e}")
