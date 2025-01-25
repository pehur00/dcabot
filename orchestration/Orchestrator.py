from WorkflowState import WorkflowState


class StrategyOrchestrator:
    def __init__(self, trading_client, logger):
        self.trading_client = trading_client
        self.logger = logger
        self.state = WorkflowState.INITIAL

    def execute(self, symbol, side, strategy, ema_interval):
        """
        Orchestrate the workflow for a trading strategies.
        """
        self.logger.info(f"Starting workflow for {symbol} with side {side}")

        while True:
            self.logger.info(f"Current state: {self.state}")

            if self.state == WorkflowState.INITIAL:
                self.state = WorkflowState.CHECK_ENTRY

            elif self.state == WorkflowState.CHECK_ENTRY:
                if strategy.check_entry_criteria(symbol, side, ema_interval):
                    self.logger.info(f"Entry criteria met for {symbol} ({side}).")
                    self.state = WorkflowState.OPEN_POSITION
                else:
                    self.logger.info(f"Entry criteria not met for {symbol} ({side}).")
                    break

            elif self.state == WorkflowState.OPEN_POSITION:
                if strategy.open_position(symbol, side):
                    self.logger.info(f"Position opened for {symbol} ({side}).")
                    self.state = WorkflowState.MONITOR_POSITION
                else:
                    self.logger.error(f"Failed to open position for {symbol} ({side}).")
                    break

            elif self.state == WorkflowState.MONITOR_POSITION:
                if strategy.check_exit_criteria(symbol, side):
                    self.logger.info(f"Exit criteria met for {symbol} ({side}).")
                    self.state = WorkflowState.CLOSE_POSITION
                else:
                    self.logger.info(f"Monitoring position for {symbol} ({side}).")
                    continue  # Keep monitoring

            elif self.state == WorkflowState.CLOSE_POSITION:
                if strategy.close_position(symbol, side):
                    self.logger.info(f"Position closed for {symbol} ({side}).")
                    break
                else:
                    self.logger.error(f"Failed to close position for {symbol} ({side}).")
                    break
