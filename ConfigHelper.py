import configparser
import logging


def read_config(file_path):
    config = configparser.ConfigParser()
    config.read(file_path)
    return config


config = read_config('config.ini')
log_level = getattr(logging, config.get('Logging', 'level', fallback='INFO'))
# Set up logging
logging.basicConfig(filename='bot.log', level=log_level)


def get_api_credentials():
    return config.get('Bybit', 'api_key'), config.get('Bybit', 'api_secret'), config.getboolean('Bybit', 'test',
                                                                                                fallback=True)


def get_config():
    return config


def get_symbols():
    return config.get('Symbols', 'symbols').split(',')


def get_script_thresholds():
    return config.get('')
