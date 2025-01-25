from Workflow import Workflow


class MartingaleTradingWorkflow(Workflow):
    def __init__(self, strategy, logger):
        super().__init__(logger, strategy)

    def execute(self, symbol, buy_below_percentage, leverage, pos_side, ema_interval):
        try:
            self.logger.info(
                "Starting workflow",
                extra={
                    "symbol": symbol,
                    "json": {
                        "strategy": "MartinGale",
                        "buy_below_percentage": buy_below_percentage,
                        "leverage": leverage,
                        "pos_side": pos_side,
                        "ema_interval": ema_interval
                    }
                }
            )

            # Step 1: Prepare the strategy
            self.strategy.prepare_strategy(leverage, symbol)

            # Step 2: Retrieve required information
            current_price, ema_200, ema_50, position, total_balance = self.strategy.retrieve_information(
                ema_interval, symbol, pos_side
            )

            # Step 3: Determine and execute actions based on strategy
            if self.strategy.is_valid_position(current_price, ema_200, pos_side):
                conclusion = self.strategy.manage_position(
                    symbol, current_price, ema_200, ema_50, position, total_balance,
                    buy_below_percentage, pos_side
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
                self.logger.info(
                    "Skipping due to wrong EMA side",
                    extra={
                        "symbol": symbol,
                        "json": {
                            "current_price": current_price,
                            "ema": ema_200,
                        }
                    }
                )

        except Exception as e:
            self.logger.error(f"Error in workflow execution for {symbol}: {e}")
