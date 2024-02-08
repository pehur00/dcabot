import configparser
import logging
import time

from pybit.unified_trading import HTTP

from LiveTradingStrategy import LiveTradingStrategy


def read_config(file_path):
    config = configparser.ConfigParser()
    config.read(file_path)
    return config


config = read_config('config.ini')
log_level = getattr(logging, config.get('Logging', 'level', fallback='INFO'))
# Set up logging
logging.basicConfig(filename='bot.log', level=log_level)


def get_api_credentials(config):
    return config.get('Bybit', 'api_key'), config.get('Bybit', 'api_secret')


def get_symbols(config):
    return config.get('Symbols', 'symbols').split(',')


def get_script_thresholds(config):
    return config.get('')


def setup_client(api_key, api_secret):
    return HTTP(testnet=True, api_key=api_key, api_secret=api_secret)


def get_account_balance(client):
    try:
        balance_info = client.get_wallet_balance(accountType='UNIFIED', coin='USDT')['result']['list'][0]
        return float(balance_info['totalAvailableBalance'])
    except Exception as e:
        logging.error(f'Error on retrieving balance: {e}')

def get_open_positions(client):
    return client.get_positions(category='linear', settleCoin='USDT')['result']['list']


def main():
    api_key, api_secret = get_api_credentials(config)
    client = setup_client(api_key, api_secret)

    # Set strategy parameters from config
    leverage = config.getint('Script', 'leverage')
    profit_pnl = config.getfloat('Script', 'profitPnL')
    profit_threshold = config.getfloat('Script', 'profitThreshold')
    proportion_of_balance = config.getfloat('Script', 'beginSizeOfBalance')
    buy_until_limit = config.getfloat('Script', 'buyUntilLimit')
    strategy_filter = config.get('Script', 'strategyFilter')
    ema_interval = config.getfloat('Script', 'emaInterval')

    strategy = LiveTradingStrategy(client, leverage, profit_threshold, profit_pnl, proportion_of_balance, buy_until_limit)

    symbols = get_symbols(config)

    # Fix leverage for provided symbols
    for symbol in symbols:
        strategy.set_leverage(symbol, leverage)

    while True:

        # Cancel all open orders at the start, so we don't pile up orders
        strategy.cancel_all_open_orders(None)

        total_balance = get_account_balance(client)
        open_positions = {pos['symbol']: pos for pos in get_open_positions(client)}

        for symbol in symbols:
            strategy.execute_strategy(symbol, total_balance, open_positions, strategy_filter, ema_interval)

        time.sleep(60)  # Sleep for 60 seconds


if __name__ == "__main__":
    main()
