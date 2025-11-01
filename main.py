# Configuration parameters
import asyncio
import logging
import os
from pathlib import Path

from pythonjsonlogger import json
from dotenv import load_dotenv

from strategies.MartingaleTradingStrategy import MartingaleTradingStrategy
from workflows.MartingaleTradingWorkflow import MartingaleTradingWorkflow
from clients.PhemexClient import PhemexClient
from notifications.TelegramNotifier import TelegramNotifier


async def load_bot_from_database(bot_id):
    """Load bot configuration from database when BOT_ID is set"""
    from saas.database import get_db
    from saas.security import decrypt_api_key

    with get_db() as conn:
        cursor = conn.cursor()

        # Get bot info
        cursor.execute("""
            SELECT exchange, testnet, api_key_encrypted, api_secret_encrypted
            FROM bots
            WHERE id = %s
        """, (bot_id,))
        bot = cursor.fetchone()

        if not bot:
            raise ValueError(f"Bot {bot_id} not found in database")

        exchange, testnet, api_key_encrypted, api_secret_encrypted = bot

        # Decrypt API keys
        api_key = decrypt_api_key(api_key_encrypted)
        api_secret = decrypt_api_key(api_secret_encrypted)

        # Get trading pairs
        cursor.execute("""
            SELECT symbol, side, leverage, ema_interval, automatic_mode
            FROM trading_pairs
            WHERE bot_id = %s AND is_active = true
        """, (bot_id,))
        pairs = cursor.fetchall()

        # Validate bot has trading pairs
        if not pairs:
            raise ValueError(f"Bot {bot_id} has no active trading pairs configured. Please add at least one trading pair.")

        # Build symbol_sides string: "BTCUSDT:Long:True,ETHUSDT:Short:False"
        # Convert boolean to 'True'/'False' string
        symbol_sides = ','.join([f"{symbol}:{side}:{'True' if automatic else 'False'}" for symbol, side, leverage, ema_interval, automatic in pairs])

        # Use first pair's EMA interval (or default to 1)
        ema_interval = pairs[0][3] if pairs else 1

        return {
            'api_key': api_key,
            'api_secret': api_secret,
            'testnet': testnet,
            'symbol_sides': symbol_sides,
            'ema_interval': ema_interval,
            'exchange': exchange
        }


async def main():
    # Load .env file if it exists (for local development)
    # Docker/Render will inject env vars directly
    env_path = Path(__file__).parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        logging.info("Loaded environment variables from .env file")

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

    # Check if BOT_ID is set (SaaS mode)
    bot_id = os.getenv('BOT_ID')
    if bot_id:
        # Load from database
        logger.info(f"Loading bot configuration from database (BOT_ID={bot_id})")
        config = await load_bot_from_database(int(bot_id))
        api_key = config['api_key']
        api_secret = config['api_secret']
        testnet = config['testnet']
        symbol_sides = config['symbol_sides']
        ema_interval = config['ema_interval']
    else:
        # Load from environment variables (legacy mode)
        logger.info("Loading bot configuration from environment variables")
        api_key = os.getenv('API_KEY')
        api_secret = os.getenv('API_SECRET')
        ema_interval = int(os.getenv('EMA_INTERVAL', 1))
        testnet = os.getenv('TESTNET', 'False').lower() in ('true', '1', 't')
        symbol_sides = os.getenv('SYMBOL', '')

    # Parse the symbol configuration into a dictionary
    symbol_side_map = await parse_symbols(symbol_sides)

    # Validate required environment variables
    if not all([api_key, api_secret, symbol_sides]):
        raise ValueError("API_KEY, API_SECRET, and SYMBOL environment variables must be set.")

    # Initialize Phemex client
    client = PhemexClient(api_key, api_secret, logger, testnet)

    # Initialize Telegram notifier
    notifier = TelegramNotifier(logger=logger)

    # Only send startup notification if BOT_STARTUP env var is set
    # This prevents notification spam from cron jobs
    # Set BOT_STARTUP=true manually when you want to know bot restarted
    if os.getenv('BOT_STARTUP', 'False').lower() in ('true', '1', 't'):
        notifier.notify_bot_started(symbol_side_map, testnet)

    # Initialize trading strategy with configuration parameters
    strategy = MartingaleTradingStrategy(
        client=client,
        logger=logger,
        notifier=notifier
    )

    workflow = MartingaleTradingWorkflow(strategy, logger)

    for symbol, pos_side, automatic_mode in symbol_side_map:
        await execute_symbol_strategy(symbol, workflow, ema_interval, pos_side, automatic_mode, notifier)  # Sequentially process each symbol


async def parse_symbols(symbol_sides):
    symbol_side_map = []
    if symbol_sides:
        try:
            for item in symbol_sides.split(','):
                if ':' in item:
                    symbol, side, automatic = item.split(':', 2)
                    automatic_bool = automatic.strip().lower() in ["true", "1", "yes"]  # Convert to Boolean
                    symbol_side_map.append((symbol.strip(), side.strip(), automatic_bool))
        except Exception as e:
            print(f"Error parsing SYMBOL_SIDES: {e}")

    # Example SYMBOL_SIDES input: "INJUSDT:Short:True,INJUSDT:Long:True,POPCATUSDT:Short:false"
    # Output symbol_side_map:
    # [
    #     ("INJUSDT", "Short", True),
    #     ("INJUSDT", "Long", True),
    #     ("POPCATUSDT", "Short", False)
    # ]
    return symbol_side_map


async def execute_symbol_strategy(symbol, workflow, ema_interval, pos_side, automatic_mode, notifier=None):
    try:
        # Execute the trading strategy for the specific symbol
        result = await asyncio.to_thread(
            workflow.execute,
            symbol=symbol,
            ema_interval=ema_interval,
            pos_side=pos_side,
            automatic_mode=automatic_mode
        )

        # Log the conclusion and metrics in formats that execute_all_bots.py can parse
        if result:
            import json
            action = result.get('action', 'unknown')
            conclusion = result.get('conclusion', 'No details')

            # Output conclusion for logging
            print(f"EXECUTION_CONCLUSION: {symbol} {pos_side} - {action.upper()} - {conclusion}")

            # Output full metrics as JSON for database persistence
            metrics_json = json.dumps(result)
            print(f"EXECUTION_METRICS: {metrics_json}")

            logging.info(f'Successfully executed strategy for {symbol}: {conclusion}')
        else:
            print(f"EXECUTION_CONCLUSION: {symbol} {pos_side} - COMPLETED - No result returned")
            logging.info(f'Successfully executed strategy for {symbol}')
    except Exception as e:
        error_msg = str(e)
        print(f"EXECUTION_CONCLUSION: {symbol} {pos_side} - ERROR - {error_msg}")
        logging.error(f'Error executing strategy for {symbol}: {error_msg}')

        # Send Telegram notification on error
        if notifier:
            notifier.notify_error(
                error_type="Strategy Execution Failed",
                symbol=symbol,
                error_message=error_msg
            )


# Run the asyncio event loop
if __name__ == '__main__':
    asyncio.run(main())
