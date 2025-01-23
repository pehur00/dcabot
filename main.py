# Configuration parameters
import logging
import os

from pythonjsonlogger import json

from MartingaleTradingStrategy import MartingaleTradingStrategy
from PhemexClient import PhemexClient

CONFIG = {
    'buy_until_limit': 5,
    'profit_threshold': 0.5,
    'profit_pnl': 0.05,
    'leverage': 10,
    'begin_size_of_balance': 0.001,
    'strategy_filter': 'EMA',  # Currently, only 'EMA' is supported
    'buy_below_percentage': 0.02,
    'logging_level': logging.INFO

}


def main():
    # Configure logging
    # Configure the logger to output structured JSON logs
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    logHandler = logging.StreamHandler()

    # Define a JSON log formatter
    formatter = json.JsonFormatter(
        '%(asctime)s %(levelname)s %(message)s %(symbol)s %(action)s %(json)s'
    )

    logHandler.setFormatter(formatter)
    logger.addHandler(logHandler)

    # Retrieve environment variables
    api_key = os.getenv('API_KEY')
    api_secret = os.getenv('API_SECRET')
    symbol = os.getenv('SYMBOL')
    ema_interval = int(os.getenv('EMA_INTERVAL', 5))  # Provide a default value (e.g., 200) if the variable isn't set
    testnet = os.getenv('TESTNET', 'False').lower() in ('true', '1', 't')

    # Validate required environment variables
    if not all([api_key, api_secret, symbol]):
        raise ValueError("API_KEY, API_SECRET, and SYMBOL environment variables must be set.")

    # Initialize Phemex client
    client = PhemexClient(api_key, api_secret, logger, testnet)

    # Initialize trading strategy with configuration parameters
    strategy = MartingaleTradingStrategy(
        client=client,
        leverage=CONFIG['leverage'],
        profit_threshold=CONFIG['profit_threshold'],
        profit_pnl=CONFIG['profit_pnl'],
        proportion_of_balance=CONFIG['begin_size_of_balance'],
        buy_until_limit=CONFIG['buy_until_limit'],
        logger=logger
    )

    try:
        # Execute the trading strategy for the specified symbol
        strategy.execute_strategy(
            symbol=symbol,
            strategy_filter=CONFIG['strategy_filter'],
            ema_interval=ema_interval,
            buy_below_percentage=CONFIG['buy_below_percentage'],
            leverage=CONFIG['leverage']
        )
    except Exception as e:
        logging.error(f'Error executing strategy for {symbol}: {e}')


if __name__ == "__main__":
    main()
