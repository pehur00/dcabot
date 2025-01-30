# Configuration parameters
import asyncio
import logging
import os

from pythonjsonlogger import json

from strategies.MartingaleTradingStrategy import MartingaleTradingStrategy
from workflows.MartingaleTradingWorkflow import MartingaleTradingWorkflow
from clients.PhemexClient import PhemexClient

CONFIG = {
    'buy_until_limit': 5,
    'profit_threshold': 0.5,
    'profit_pnl': 0.2,
    'leverage': 6,
    'begin_size_of_balance': 0.03,
    'strategy_filter': 'EMA',  # Currently, only 'EMA' is supported
    'buy_below_percentage': 0.04,
    'logging_level': logging.INFO
}

async def main():
    # Remove all existing handlers to prevent duplicate logging
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Set the logging level globally
    root_logger.setLevel(logging.INFO)

    # Create a StreamHandler for structured logging
    log_handler = logging.StreamHandler()

    # Define JSON log formatter
    formatter = json.JsonFormatter(
        '%(asctime)s %(levelname)s %(message)s %(symbol)s %(action)s %(json)s'
    )

    log_handler.setFormatter(formatter)
    root_logger.addHandler(log_handler)

    # Ensure there is no "extra" module-based logger overriding the root logger
    logger = logging.getLogger(__name__)
    logger.propagate = True

    # Retrieve environment variables
    api_key = os.getenv('API_KEY')
    api_secret = os.getenv('API_SECRET')
    ema_interval = int(os.getenv('EMA_INTERVAL', 1))  # Provide a default value (e.g., 200) if the variable isn't set
    testnet = os.getenv('TESTNET', 'False').lower() in ('true', '1', 't')
    # Parse the symbol configuration into a dictionary
    # Retrieve symbols from environment or configuration
    symbol_sides = os.getenv('SYMBOL', '')  # Example: "BTCUSDT:Buy,ETHUSDT:Sell,ADAUSDT:Buy"
    symbol_side_map = await parse_symbols(symbol_sides)

    # Validate required environment variables
    if not all([api_key, api_secret, symbol_sides]):
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

    workflow = MartingaleTradingWorkflow(strategy, logger)

    for symbol, pos_side, automatic_mode in symbol_side_map:
        await execute_symbol_strategy(symbol, workflow, ema_interval, pos_side, automatic_mode)  # Sequentially process each symbol


async def parse_symbols(symbol_sides):
    symbol_side_map = []
    if symbol_sides:
        try:
            for item in symbol_sides.split(','):
                if ':' in item:
                    symbol, side, automatic = item.split(':', 2)
                    symbol_side_map.append((symbol.strip(), side.strip(), automatic.strip()))
        except Exception as e:
            print(f"Error parsing SYMBOL_SIDES: {e}")

    # 3 items will be extracted:
    # - Symbol, the symbol you want to trade
    # - Position Side, what bias do you have
    # - Automatic start, do you want the script to automatically start new position if none exist
    # Example SYMBOL_SIDES input: "INJUSDT:Short:True,INJUSDT:Long:True,POPCATUSDT:Short:false"
    # Output symbol_side_map:
    # [
    #     ("INJUSDT", "Short", "True"),
    #     ("INJUSDT", "Long", "True"),
    #     ("POPCATUSDT", "Short", False)
    # ]
    return symbol_side_map


async def execute_symbol_strategy(symbol, workflow, ema_interval, pos_side, automatic_mode):
    try:
        # Execute the trading strategy for the specific symbol
        await asyncio.to_thread(
            workflow.execute,
            symbol=symbol,
            ema_interval=ema_interval,
            pos_side=pos_side,
            buy_below_percentage=CONFIG['buy_below_percentage'],
            leverage=CONFIG['leverage'],
            automatic_mode=automatic_mode
        )
        logging.info(f'Successfully executed strategy for {symbol}')
    except Exception as e:
        logging.error(f'Error executing strategy for {symbol}: {e}')


# Run the asyncio event loop
if __name__ == '__main__':
    asyncio.run(main())
