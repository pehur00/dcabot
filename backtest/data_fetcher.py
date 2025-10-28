#!/usr/bin/env python3
"""
Extended Historical Data Fetcher using CCXT

Fetches long-term historical OHLCV data from multiple exchanges (Binance, etc.)
for comprehensive backtesting.
"""

import ccxt
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional
import time
import sys
from tqdm import tqdm


def fetch_historical_data_ccxt(
    symbol: str,
    timeframe: str = '1h',
    days: int = 365,
    exchange_name: str = 'binance'
) -> pd.DataFrame:
    """
    Fetch extended historical data using CCXT library.

    Args:
        symbol: Trading pair (e.g., '1000PEPE/USDT', 'BTC/USDT')
        timeframe: Candle timeframe ('1m', '5m', '15m', '1h', '4h', '1d')
        days: Number of days of historical data to fetch
        exchange_name: Exchange to fetch from ('binance', 'bybit', 'okx', etc.)

    Returns:
        DataFrame with OHLCV data indexed by timestamp
    """
    print(f"\n📡 Fetching {days} days of {timeframe} data for {symbol} from {exchange_name.upper()}...")

    # Initialize exchange
    exchange_class = getattr(ccxt, exchange_name)
    exchange = exchange_class({
        'enableRateLimit': True,  # Respect rate limits
        'options': {'defaultType': 'future'}  # Use futures market
    })

    # Calculate time range
    now = datetime.now()
    since = int((now - timedelta(days=days)).timestamp() * 1000)  # Convert to milliseconds

    # Fetch data in batches
    all_candles = []
    current_since = since

    # Determine batch size based on timeframe
    timeframe_minutes = {
        '1m': 1, '3m': 3, '5m': 5, '15m': 15, '30m': 30,
        '1h': 60, '2h': 120, '4h': 240, '6h': 360, '12h': 720,
        '1d': 1440, '1w': 10080
    }
    minutes = timeframe_minutes.get(timeframe, 60)

    # Calculate required batches dynamically based on requested days
    # Each batch fetches ~1000 candles, add 20% buffer for safety
    candles_per_day = (24 * 60) / minutes
    total_candles_needed = int(days * candles_per_day)
    max_batches = int((total_candles_needed / 1000) * 1.2) + 10  # 20% buffer + 10 extra batches

    print(f"\n📡 Fetching {days} days of {timeframe} data for {symbol} from {exchange_name.upper()}...")
    print(f"   Estimated batches needed: ~{int(total_candles_needed / 1000)} (max: {max_batches})")

    batch_num = 0

    # Setup progress tracking
    use_tqdm = sys.stdout.isatty()
    pbar = tqdm(total=max_batches, desc="Fetching data", unit=" batch",
                bar_format='{desc}: {n_fmt}/{total_fmt} batches |{bar}| {elapsed}',
                disable=not use_tqdm, leave=True) if use_tqdm else None

    while current_since < int(now.timestamp() * 1000) and batch_num < max_batches:
        try:
            # Fetch batch (most exchanges return 500-1000 candles per request)
            candles = exchange.fetch_ohlcv(
                symbol=symbol,
                timeframe=timeframe,
                since=current_since,
                limit=1000  # Max candles per request
            )

            if not candles:
                break

            all_candles.extend(candles)
            batch_num += 1

            # Update since to last candle timestamp + 1 period
            current_since = candles[-1][0] + (minutes * 60 * 1000)

            # Update progress bar or print message
            if pbar:
                pbar.update(1)
                pbar.set_postfix({'total_candles': len(all_candles)})
            else:
                # Fallback for non-TTY: print every 5 batches
                if batch_num % 5 == 0 or batch_num == 1:
                    print(f"  Batch {batch_num}: Fetched {len(candles)} candles (total: {len(all_candles)})")

            # Small delay to respect rate limits
            time.sleep(exchange.rateLimit / 1000)

        except Exception as e:
            print(f"  ⚠️ Error fetching batch {batch_num}: {e}")
            break

    if pbar:
        pbar.close()

    if not all_candles:
        print("❌ No data fetched")
        return pd.DataFrame()

    # Convert to DataFrame
    df = pd.DataFrame(
        all_candles,
        columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
    )

    # Convert timestamp to datetime
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)

    # Remove duplicates
    df = df[~df.index.duplicated(keep='first')]

    print(f"✅ Fetched {len(df)} candles from {df.index[0]} to {df.index[-1]}")
    print(f"   Period: {(df.index[-1] - df.index[0]).days} days")

    return df


def convert_phemex_to_binance_symbol(phemex_symbol: str) -> str:
    """
    Convert Phemex symbol format to Binance format.

    Examples:
        u1000PEPEUSDT -> 1000PEPE/USDT
        BTCUSDT -> BTC/USDT
        ETHUSDT -> ETH/USDT
    """
    # Remove 'u' prefix if present (Phemex futures notation)
    if phemex_symbol.startswith('u'):
        phemex_symbol = phemex_symbol[1:]

    # Remove USDT suffix and add slash
    if phemex_symbol.endswith('USDT'):
        base = phemex_symbol[:-4]
        return f"{base}/USDT"

    return phemex_symbol


def test_fetch():
    """Test the data fetcher"""
    # Test with 1000PEPE
    symbol = '1000PEPE/USDT'
    df = fetch_historical_data_ccxt(
        symbol=symbol,
        timeframe='1h',
        days=180,
        exchange_name='binance'
    )

    if not df.empty:
        print(f"\n📊 Sample Data:")
        print(df.head())
        print(f"\n📈 Statistics:")
        print(df.describe())


if __name__ == '__main__':
    test_fetch()
