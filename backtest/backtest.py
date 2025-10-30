#!/usr/bin/env python3
"""
DCABot Backtesting Framework

Simulates the Martingale trading strategy on historical data.
Provides performance metrics, trade history, and drawdown analysis.

Usage:
    python backtest.py --symbol u1000PEPEUSDT --days 30 --interval 5
"""

import argparse
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any
from decimal import Decimal, ROUND_DOWN
import pandas as pd
import numpy as np
from dotenv import load_dotenv
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from tqdm import tqdm

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from clients.PhemexClient import PhemexClient
from strategies.MartingaleTradingStrategy import MartingaleTradingStrategy
from data_fetcher import fetch_historical_data_ccxt, convert_phemex_to_binance_symbol


def fetch_extended_historical_data(client: PhemexClient, symbol: str, interval: int,
                                   total_periods: int) -> pd.DataFrame:
    """
    Fetch extended historical data by making multiple API requests.

    Phemex API returns max 1000 candles per request, so we fetch in batches
    and stitch them together.

    Args:
        client: PhemexClient instance
        symbol: Trading symbol
        interval: Interval in minutes
        total_periods: Total number of candles needed

    Returns:
        DataFrame with extended OHLCV data
    """
    max_candles_per_request = 1000

    if total_periods <= max_candles_per_request:
        # Single request is enough
        return client.fetch_historical_data(symbol, interval, total_periods)

    # Calculate number of batches needed
    num_batches = (total_periods + max_candles_per_request - 1) // max_candles_per_request

    print(f"📊 Fetching {total_periods} candles in {num_batches} batches...")

    all_data = []

    for batch_num in range(num_batches):
        # Fetch batch
        batch_size = min(max_candles_per_request, total_periods - (batch_num * max_candles_per_request))

        print(f"  Batch {batch_num + 1}/{num_batches}: Fetching {batch_size} candles...")

        df_batch = client.fetch_historical_data(symbol, interval, batch_size)

        if df_batch.empty:
            print(f"  ⚠️ Batch {batch_num + 1} returned no data, stopping")
            break

        all_data.append(df_batch)

        # Small delay to avoid rate limiting
        import time
        time.sleep(0.5)

    if not all_data:
        return pd.DataFrame()

    # Combine all batches
    print(f"📦 Combining {len(all_data)} batches...")
    combined_df = pd.concat(all_data, ignore_index=False)

    # Remove duplicates and sort
    combined_df = combined_df[~combined_df.index.duplicated(keep='first')]
    combined_df = combined_df.sort_index()

    print(f"✅ Total candles fetched: {len(combined_df)}")

    return combined_df


class BacktestEngine:
    def __init__(self, client: PhemexClient, strategy: MartingaleTradingStrategy,
                 initial_balance: float = 10000.0, max_margin_pct: float = None, symbols: List[str] = None):
        self.client = client
        self.strategy = strategy
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.peak_balance = initial_balance
        self.max_margin_pct = max_margin_pct  # Optional margin cap

        # Multi-symbol support
        self.symbols = symbols or []
        self.multi_symbol = len(self.symbols) > 1

        # Position tracking (per-symbol for multi-symbol mode)
        if self.multi_symbol:
            self.positions = {symbol: None for symbol in self.symbols}
            self.position_entry_prices = {symbol: 0 for symbol in self.symbols}
            self.position_sizes = {symbol: 0 for symbol in self.symbols}
            self.position_values = {symbol: 0 for symbol in self.symbols}
            self.unrealized_pnls = {symbol: 0 for symbol in self.symbols}
            self.symbol_margins = {symbol: 0 for symbol in self.symbols}  # Track margin per symbol
        else:
            # Single symbol mode (backward compatible)
            self.position = None
            self.position_entry_price = 0
            self.position_size = 0
            self.position_value = 0
            self.unrealized_pnl = 0

        # Trade history
        self.trades: List[Dict[str, Any]] = []
        self.balance_history: List[Dict[str, Any]] = []
        self.price_history: List[Dict[str, Any]] = []  # Store price + EMAs for charting

        # Performance metrics
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.liquidations = 0  # Track liquidation events
        self.max_drawdown = 0
        self.max_drawdown_absolute = 0
        self.peak_total_value = initial_balance
        self.total_fees = 0

        # Per-symbol metrics (for multi-symbol mode)
        if self.multi_symbol:
            self.symbol_trades = {symbol: [] for symbol in self.symbols}
            self.symbol_winning_trades = {symbol: 0 for symbol in self.symbols}
            self.symbol_losing_trades = {symbol: 0 for symbol in self.symbols}
            self.symbol_total_pnl = {symbol: 0 for symbol in self.symbols}

        # Instrument specs for minimum quantity rounding (per symbol)
        self.instrument_specs = {}  # {symbol: {min_qty, max_qty, qty_step}}
        self.min_qty = 1.0  # Default for single symbol mode
        self.max_qty = 1000000.0
        self.qty_step = 1.0

        # Configuration settings (for display in results)
        self.config_settings = {}

    def set_instrument_specs(self, min_qty: float, max_qty: float, qty_step: float, symbol: str = None):
        """Set instrument specifications for quantity rounding"""
        if symbol and self.multi_symbol:
            # Multi-symbol mode: store per symbol
            self.instrument_specs[symbol] = {
                'min_qty': min_qty,
                'max_qty': max_qty,
                'qty_step': qty_step
            }
        else:
            # Single symbol mode
            self.min_qty = min_qty
            self.max_qty = max_qty
            self.qty_step = qty_step

    def get_total_margin(self) -> float:
        """Get total margin usage across all symbols"""
        if self.multi_symbol:
            return sum(self.symbol_margins.values())
        else:
            return self.position_value / self.strategy.leverage if self.position_value > 0 else 0

    def custom_round(self, number: float, symbol: str = None) -> float:
        """Round quantity to meet exchange requirements (same logic as real bot)"""
        # Get specs for this symbol (multi-symbol mode) or use defaults (single symbol mode)
        if symbol and self.multi_symbol and symbol in self.instrument_specs:
            specs = self.instrument_specs[symbol]
            min_qty = Decimal(str(specs['min_qty']))
            max_qty = Decimal(str(specs['max_qty']))
            qty_step = Decimal(str(specs['qty_step']))
        else:
            min_qty = Decimal(str(self.min_qty))
            max_qty = Decimal(str(self.max_qty))
            qty_step = Decimal(str(self.qty_step))

        number = Decimal(str(number))

        # Perform floor rounding to qty_step
        rounded_qty = (number / qty_step).quantize(Decimal('1'), rounding=ROUND_DOWN) * qty_step

        # Clamp the result within the min and max bounds (FORCES minimum!)
        return float(max(min(rounded_qty, max_qty), min_qty))

    def simulate_position(self, current_price: float) -> Dict[str, Any]:
        """Simulate a position dict like Phemex returns"""
        if not self.position:
            return None

        # Calculate unrealized PnL
        if self.position['pos_side'] == 'Long':
            self.unrealized_pnl = (current_price - self.position_entry_price) * self.position_size
        else:
            self.unrealized_pnl = (self.position_entry_price - current_price) * self.position_size

        self.position_value = current_price * self.position_size
        # Calculate profit % relative to MARGIN invested, not notional value
        margin_invested = self.position_value / self.strategy.leverage
        upnl_percentage = (self.unrealized_pnl / margin_invested) if margin_invested > 0 else 0

        # Calculate margin level (simplified)
        used_margin = self.position_value / self.strategy.leverage
        if used_margin > 0:
            margin_level = (self.balance + self.unrealized_pnl) / used_margin  # Fixed: + not -
        else:
            margin_level = 999

        # IMPORTANT: Phemex returns assignedPosBalanceRv (MARGIN) as positionValue, not notional!
        # So we need to return margin-based value to match real bot behavior
        position_value_as_margin = self.position_value / self.strategy.leverage

        return {
            'symbol': self.position['symbol'],
            'pos_side': self.position['pos_side'],
            'size': self.position_size,
            'positionValue': position_value_as_margin,  # Return MARGIN, not notional!
            'unrealisedPnl': self.unrealized_pnl,
            'upnlPercentage': upnl_percentage,
            'position_size_percentage': (position_value_as_margin / self.balance) * 100,
            'margin_level': margin_level,
            'entry_price': self.position_entry_price
        }

    def simulate_position_for_symbol(self, symbol: str, current_price: float):
        """Simulate position state for a specific symbol in multi-symbol mode"""
        if not self.positions.get(symbol):
            return None

        # Calculate unrealized PnL for this symbol
        if self.positions[symbol]['pos_side'] == 'Long':
            self.unrealized_pnls[symbol] = (current_price - self.position_entry_prices[symbol]) * self.position_sizes[symbol]
        else:
            self.unrealized_pnls[symbol] = (self.position_entry_prices[symbol] - current_price) * self.position_sizes[symbol]

        self.position_values[symbol] = current_price * self.position_sizes[symbol]

        # Calculate profit % relative to MARGIN invested
        margin_invested = self.position_values[symbol] / self.strategy.leverage
        upnl_percentage = (self.unrealized_pnls[symbol] / margin_invested) if margin_invested > 0 else 0

        # Calculate total margin level across ALL symbols
        total_used_margin = self.get_total_margin()
        total_unrealized_pnl = sum(self.unrealized_pnls.values())

        if total_used_margin > 0:
            margin_level = (self.balance + total_unrealized_pnl) / total_used_margin
        else:
            margin_level = 999

        position_value_as_margin = self.position_values[symbol] / self.strategy.leverage

        return {
            'symbol': self.positions[symbol]['symbol'],
            'pos_side': self.positions[symbol]['pos_side'],
            'size': self.position_sizes[symbol],
            'positionValue': position_value_as_margin,
            'unrealisedPnl': self.unrealized_pnls[symbol],
            'upnlPercentage': upnl_percentage,
            'position_size_percentage': (position_value_as_margin / self.balance) * 100,
            'margin_level': margin_level,  # Total margin level across all symbols
            'entry_price': self.position_entry_prices[symbol]
        }

    def execute_trade(self, symbol: str, qty: float, price: float, side: str, pos_side: str, timestamp=None):
        """Simulate trade execution with exchange-side validations"""
        # Calculate required margin for this trade
        trade_notional = qty * price
        required_margin = trade_notional / self.strategy.leverage

        # Determine current position state (multi-symbol vs single-symbol)
        if self.multi_symbol:
            current_position = self.positions.get(symbol)
            current_position_value = self.position_values.get(symbol, 0)
            current_position_size = self.position_sizes.get(symbol, 0)
            current_position_entry_price = self.position_entry_prices.get(symbol, 0)
        else:
            current_position = self.position
            current_position_value = self.position_value
            current_position_size = self.position_size
            current_position_entry_price = self.position_entry_price

        # === USER-CONFIGURED PROTECTIONS (optional) ===
        # ONLY apply max_margin_pct if explicitly set (optional protection)
        if side in ['Buy', 'Sell'] and (side == 'Buy' if pos_side == 'Long' else side == 'Sell'):
            if self.max_margin_pct is not None:
                # This is opening or adding to position - check margin cap
                if self.multi_symbol:
                    # Check total margin across ALL symbols
                    current_used_margin = self.get_total_margin()
                else:
                    current_used_margin = (current_position_value / self.strategy.leverage) if current_position else 0

                total_required_margin = current_used_margin + required_margin
                margin_usage = total_required_margin / self.balance

                if margin_usage > self.max_margin_pct:
                    return  # Skip this trade

        # === EXCHANGE-SIDE VALIDATIONS (always enforced) ===
        if side in ['Buy', 'Sell'] and (side == 'Buy' if pos_side == 'Long' else side == 'Sell'):
            # Calculate current used margin
            if self.multi_symbol:
                current_used_margin = self.get_total_margin()
            else:
                current_used_margin = (current_position_value / self.strategy.leverage) if current_position else 0

            # Calculate available balance (total balance - used margin)
            # Note: unrealized PnL is included in balance, so we need to account for it
            available_balance = self.balance - current_used_margin

            # Exchange would reject if not enough available balance for required margin
            if required_margin > available_balance:
                # print(f"  ⚠️  Order REJECTED by exchange: Required margin ${required_margin:.2f} > Available ${available_balance:.2f}")
                return  # Exchange rejects this order

        # NOTE: Real bot has NO pre-execution checks!
        # It relies on exchange liquidation engine
        # The checks above simulate EXCHANGE behavior, not bot behavior

        # Calculate fee (0.075% maker fee on Phemex)
        fee = abs(qty * price * 0.00075)
        self.total_fees += fee

        trade = {
            'timestamp': timestamp if timestamp else datetime.now(),
            'symbol': symbol,
            'side': side,
            'pos_side': pos_side,
            'qty': qty,
            'price': price,
            'value': qty * price,
            'fee': fee
        }

        if not current_position:
            # Open new position
            if self.multi_symbol:
                self.positions[symbol] = {'symbol': symbol, 'pos_side': pos_side}
                self.position_sizes[symbol] = qty
                self.position_entry_prices[symbol] = price
                self.position_values[symbol] = qty * price
                self.symbol_margins[symbol] = required_margin
            else:
                self.position = {'symbol': symbol, 'pos_side': pos_side}
                self.position_size = qty
                self.position_entry_price = price
                self.position_value = qty * price

            trade['action'] = 'OPEN'
            trade['position_size'] = qty
            trade['position_value'] = qty * price

        elif side == 'Buy' if pos_side == 'Long' else 'Sell':
            # Add to position (average down)
            total_value = (current_position_size * current_position_entry_price) + (qty * price)
            new_position_size = current_position_size + qty
            new_entry_price = total_value / new_position_size
            new_position_value = new_position_size * price

            if self.multi_symbol:
                self.position_sizes[symbol] = new_position_size
                self.position_entry_prices[symbol] = new_entry_price
                self.position_values[symbol] = new_position_value
                self.symbol_margins[symbol] = new_position_value / self.strategy.leverage
            else:
                self.position_size = new_position_size
                self.position_entry_price = new_entry_price
                self.position_value = new_position_value

            trade['action'] = 'ADD'
            trade['position_size'] = new_position_size
            trade['position_value'] = new_position_value

        else:
            # Close position (partial or full)
            realized_pnl = 0
            if pos_side == 'Long':
                realized_pnl = (price - current_position_entry_price) * qty
            else:
                realized_pnl = (current_position_entry_price - price) * qty

            self.balance += realized_pnl - fee
            new_position_size = current_position_size - qty

            if new_position_size <= 0:
                # Fully closed
                if self.multi_symbol:
                    self.positions[symbol] = None
                    self.position_sizes[symbol] = 0
                    self.position_entry_prices[symbol] = 0
                    self.position_values[symbol] = 0
                    self.unrealized_pnls[symbol] = 0
                    self.symbol_margins[symbol] = 0

                    # Track win/loss for this symbol
                    if realized_pnl > 0:
                        self.symbol_winning_trades[symbol] += 1
                    else:
                        self.symbol_losing_trades[symbol] += 1
                    self.symbol_total_pnl[symbol] += realized_pnl
                else:
                    self.position = None
                    self.position_size = 0
                    self.position_entry_price = 0
                    self.position_value = 0
                    self.unrealized_pnl = 0

                    # Track win/loss
                    self.total_trades += 1
                    if realized_pnl > 0:
                        self.winning_trades += 1
                    else:
                        self.losing_trades += 1

                trade['action'] = 'CLOSE'
                trade['position_size'] = 0
                trade['position_value'] = 0
            else:
                # Partially closed
                new_position_value = new_position_size * price

                if self.multi_symbol:
                    self.position_sizes[symbol] = new_position_size
                    self.position_values[symbol] = new_position_value
                    self.symbol_margins[symbol] = new_position_value / self.strategy.leverage
                    self.symbol_total_pnl[symbol] += realized_pnl
                else:
                    self.position_size = new_position_size
                    self.position_value = new_position_value

                trade['action'] = 'REDUCE'
                trade['position_size'] = new_position_size
                trade['position_value'] = new_position_value

            trade['realized_pnl'] = realized_pnl

        # Track trades
        if self.multi_symbol:
            self.symbol_trades[symbol].append(trade)

        self.trades.append(trade)

    def run_backtest(self, df: pd.DataFrame, symbol: str, pos_side: str,
                     ema_interval: int, automatic_mode: bool = True):
        """
        Run backtest on historical data

        Args:
            df: DataFrame with OHLCV data
            symbol: Trading symbol
            pos_side: 'Long' or 'Short'
            ema_interval: EMA interval in minutes
            automatic_mode: Auto-open positions
        """
        print(f"\n🚀 Starting backtest for {symbol} ({pos_side})")
        print(f"Initial Balance: ${self.initial_balance:,.2f}")
        print(f"Period: {df.index[0]} to {df.index[-1]}")
        print(f"Data Points: {len(df)}")
        print("=" * 80)

        # Pre-calculate EMAs for entire dataset
        df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
        df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()

        # Calculate 1h EMA100 for dip-buying filter (resample 1m data to 1h, then map back)
        # STRATEGY: Buy BELOW 1h EMA100 to catch dips with upside potential
        df_1h = df.resample('1h').agg({'close': 'last', 'high': 'max', 'low': 'min', 'open': 'first', 'volume': 'sum'})
        df_1h['ema_100_1h'] = df_1h['close'].ewm(span=100, adjust=False).mean()

        # Forward-fill 1h EMA100 to 1-minute timeframe
        df = df.join(df_1h[['ema_100_1h']], how='left')
        df['ema_100_1h'] = df['ema_100_1h'].ffill()

        # Need at least 200 periods for EMA200
        if len(df) < 200:
            print("❌ Insufficient data for EMA200 calculation (need 200+ periods)")
            return

        # Run simulation - check every 5 minutes (every 5th candle) to match real bot behavior
        check_interval = 5  # minutes - matches agent.py sleep(300 seconds)

        # Setup progress tracking
        use_tqdm = sys.stdout.isatty()
        iterations = range(200, len(df), check_interval)
        total_iterations = len(list(iterations))

        for idx, i in enumerate(tqdm(iterations, desc="Simulating", unit=" checks",
                     bar_format='{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]',
                     disable=not use_tqdm, mininterval=1.0, leave=True)):
            current_candle = df.iloc[i]
            timestamp = current_candle.name
            current_price = float(current_candle['close'])
            ema_50 = float(current_candle['ema_50'])
            ema_200 = float(current_candle['ema_200'])
            ema_100_1h = float(current_candle['ema_100_1h'])

            # Simulate position
            simulated_position = self.simulate_position(current_price)

            # Check if position management is valid
            # Note: is_valid_position() now returns True for new positions (no conflict with 1h EMA100 filter)
            valid_position = self.strategy.is_valid_position(
                simulated_position, current_price, ema_200, pos_side
            )

            # Store price data for charting
            self.price_history.append({
                'timestamp': timestamp,
                'price': current_price,
                'ema_50': ema_50,
                'ema_200': ema_200,
                'ema_100_1h': ema_100_1h
            })

            if not valid_position:
                # Record balance snapshot
                # Use margin-based position value (like Phemex does!)
                position_value_for_history = (self.position_value / self.strategy.leverage) if self.position else 0

                self.balance_history.append({
                    'timestamp': timestamp,
                    'balance': self.balance,
                    'position_value': position_value_for_history,  # Margin, not notional!
                    'unrealized_pnl': self.unrealized_pnl,
                    'total_value': self.balance + self.unrealized_pnl
                })
                continue

            # Get strategy decision WITH FULL VOLATILITY PROTECTION
            conclusion = self._manage_position_backtest(
                symbol, current_price, ema_200, ema_50, ema_100_1h,
                simulated_position, self.balance, pos_side, automatic_mode,
                df, i, timestamp  # Pass historical data and timestamp
            )

            # === EXCHANGE AUTO-LIQUIDATION ===
            # Check if margin_level dropped to liquidation threshold
            if self.position and simulated_position:
                margin_level = simulated_position.get('margin_level', 999)

                # Phemex liquidates when margin_level <= 1.0
                if margin_level <= 1.0:
                    print(f"\n💀 LIQUIDATED at {timestamp}")
                    print(f"   Price: ${current_price:.6f}")
                    print(f"   Margin Level: {margin_level:.4f}")
                    print(f"   Position Size: {self.position_size:.2f}")
                    print(f"   Position Value: ${self.position_value:.2f}")
                    print(f"   Unrealized PnL: ${self.unrealized_pnl:.2f}")
                    print(f"   Balance before liquidation: ${self.balance:.2f}")

                    # Liquidation: Close position at market (assume small slippage)
                    liquidation_price = current_price * 0.995  # 0.5% slippage
                    realized_pnl = 0
                    if pos_side == 'Long':
                        realized_pnl = (liquidation_price - self.position_entry_price) * self.position_size
                    else:
                        realized_pnl = (self.position_entry_price - liquidation_price) * self.position_size

                    # Update balance with realized PnL
                    self.balance += realized_pnl

                    # Record liquidation as trade
                    self.trades.append({
                        'timestamp': timestamp,
                        'symbol': symbol,
                        'side': 'Sell' if pos_side == 'Long' else 'Buy',
                        'pos_side': pos_side,
                        'qty': self.position_size,
                        'price': liquidation_price,
                        'value': self.position_size * liquidation_price,
                        'fee': 0,  # Liquidation fees already accounted in slippage
                        'action': 'LIQUIDATED',
                        'position_size': 0,
                        'position_value': 0,
                        'pnl': realized_pnl
                    })

                    # Clear position
                    self.position = None
                    self.position_size = 0
                    self.position_entry_price = 0
                    self.position_value = 0
                    self.unrealized_pnl = 0

                    # Track liquidation
                    self.liquidations += 1

                    print(f"   Realized PnL: ${realized_pnl:.2f}")
                    print(f"   Balance after liquidation: ${self.balance:.2f}")
                    print(f"   Remaining balance: ${self.balance:.2f} ({(self.balance/self.initial_balance)*100:.1f}% of initial)")

                    conclusion = "LIQUIDATED - Account wiped"

            # Record balance snapshot
            # Use margin-based position value (like Phemex does!)
            position_value_for_history = (self.position_value / self.strategy.leverage) if self.position else 0
            total_value = self.balance + self.unrealized_pnl

            self.balance_history.append({
                'timestamp': timestamp,
                'balance': self.balance,
                'position_value': position_value_for_history,  # Margin, not notional!
                'unrealized_pnl': self.unrealized_pnl,
                'total_value': total_value,
                'action': conclusion
            })

            # Track drawdown based on total value (including unrealized PnL)
            if total_value > self.peak_total_value:
                self.peak_total_value = total_value

            drawdown_pct = ((self.peak_total_value - total_value) / self.peak_total_value) * 100
            drawdown_abs = self.peak_total_value - total_value
            if drawdown_pct > self.max_drawdown:
                self.max_drawdown = drawdown_pct
                self.max_drawdown_absolute = drawdown_abs

            # Print progress every 10% if not using tqdm
            if not use_tqdm and idx % max(1, total_iterations // 10) == 0 and idx > 0:
                progress_pct = (idx / total_iterations) * 100
                print(f"  Progress: {progress_pct:.0f}% ({idx}/{total_iterations} checks)")

        # Close any open position at end
        if self.position:
            print(f"\n📊 Closing remaining position at end of backtest")
            final_timestamp = df.index[-1]
            self.execute_trade(
                symbol, self.position_size, current_price,
                'Sell' if pos_side == 'Long' else 'Buy', pos_side, final_timestamp
            )

        self._print_results(symbol, pos_side)
        self.generate_charts(symbol, pos_side)

    def run_multi_symbol_backtest(self, df_dict: Dict[str, pd.DataFrame], pos_side: str,
                                    ema_interval: int, automatic_mode: bool = True):
        """
        Run backtest on multiple symbols with shared balance

        Args:
            df_dict: Dictionary of {symbol: DataFrame} with OHLCV data
            pos_side: 'Long' or 'Short' (applies to all symbols)
            ema_interval: EMA interval in minutes
            automatic_mode: Auto-open positions
        """
        print(f"\n🚀 Starting MULTI-SYMBOL backtest ({len(self.symbols)} symbols)")
        print(f"Symbols: {', '.join(self.symbols)}")
        print(f"Initial Balance: ${self.initial_balance:,.2f}")
        print(f"Max Margin Cap: {self.max_margin_pct * 100:.0f}% (${self.max_margin_pct * self.initial_balance:.2f})" if self.max_margin_pct else "No cap")
        print("=" * 80)

        # Pre-calculate EMAs for each symbol
        for symbol in self.symbols:
            df = df_dict[symbol]
            df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
            df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()

            # Calculate 1h EMA100
            df_1h = df.resample('1h').agg({'close': 'last', 'high': 'max', 'low': 'min', 'open': 'first', 'volume': 'sum'})
            df_1h['ema_100_1h'] = df_1h['close'].ewm(span=100, adjust=False).mean()
            df = df.join(df_1h[['ema_100_1h']], how='left')
            df['ema_100_1h'] = df['ema_100_1h'].ffill()
            df_dict[symbol] = df

            if len(df) < 200:
                print(f"❌ Insufficient data for {symbol} (need 200+ periods)")
                return

        # Find common time range across all symbols
        start_times = [df.index[200] for df in df_dict.values()]
        end_times = [df.index[-1] for df in df_dict.values()]
        start_time = max(start_times)
        end_time = min(end_times)

        print(f"\nCommon Period: {start_time} to {end_time}")

        # Create unified timeline (every 5 minutes to match real bot)
        check_interval = 5
        first_df = df_dict[self.symbols[0]]
        timeline = first_df.loc[start_time:end_time].index[::check_interval]

        # Setup progress tracking
        use_tqdm = sys.stdout.isatty()
        total_iterations = len(timeline)

        # Track per-symbol price history for charts and correlation
        symbol_price_histories = {symbol: [] for symbol in self.symbols}

        for idx, timestamp in enumerate(tqdm(timeline, desc="Simulating", unit=" checks",
                     bar_format='{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]',
                     disable=not use_tqdm, mininterval=1.0, leave=True)):

            # Check each symbol at this timestamp
            for symbol in self.symbols:
                df = df_dict[symbol]

                # Find closest timestamp in this symbol's dataframe
                if timestamp not in df.index:
                    closest_idx = df.index.get_indexer([timestamp], method='nearest')[0]
                    current_candle = df.iloc[closest_idx]
                else:
                    current_candle = df.loc[timestamp]

                current_price = float(current_candle['close'])
                ema_50 = float(current_candle['ema_50'])
                ema_200 = float(current_candle['ema_200'])
                ema_100_1h = float(current_candle['ema_100_1h'])

                # Store price history for this symbol
                symbol_price_histories[symbol].append({
                    'timestamp': timestamp,
                    'price': current_price,
                    'ema_50': ema_50,
                    'ema_200': ema_200,
                    'ema_100_1h': ema_100_1h
                })

                # Simulate position for this symbol
                simulated_position = self.simulate_position_for_symbol(symbol, current_price)

                # Check if position management is valid
                valid_position = True
                if simulated_position:
                    valid_position = self.strategy.is_valid_position(
                        simulated_position, current_price, ema_200, pos_side
                    )

                if not valid_position:
                    continue

                # Get strategy decision for this symbol
                conclusion = self._manage_position_backtest(
                    symbol, current_price, ema_200, ema_50, ema_100_1h,
                    simulated_position, self.balance, pos_side, automatic_mode,
                    df, df.index.get_loc(current_candle.name), timestamp
                )

            # Check for liquidation across ALL symbols
            total_used_margin = self.get_total_margin()
            total_unrealized_pnl = sum(self.unrealized_pnls.values())

            if total_used_margin > 0:
                margin_level = (self.balance + total_unrealized_pnl) / total_used_margin

                # Liquidation if margin level drops to 1.0 or below
                if margin_level <= 1.0:
                    print(f"\n💀 LIQUIDATED at {timestamp}")
                    print(f"   Total Margin Level: {margin_level:.4f}")
                    print(f"   Total Used Margin: ${total_used_margin:.2f}")
                    print(f"   Total Unrealized PnL: ${total_unrealized_pnl:.2f}")
                    print(f"   Balance before liquidation: ${self.balance:.2f}")

                    # Close all positions
                    for symbol in self.symbols:
                        if self.positions.get(symbol):
                            df = df_dict[symbol]
                            if timestamp not in df.index:
                                closest_idx = df.index.get_indexer([timestamp], method='nearest')[0]
                                current_candle = df.iloc[closest_idx]
                            else:
                                current_candle = df.loc[timestamp]
                            current_price = float(current_candle['close'])

                            liquidation_price = current_price * 0.995  # 0.5% slippage
                            position_size = self.position_sizes[symbol]
                            entry_price = self.position_entry_prices[symbol]

                            # Calculate realized PnL
                            if pos_side == 'Long':
                                realized_pnl = (liquidation_price - entry_price) * position_size
                            else:
                                realized_pnl = (entry_price - liquidation_price) * position_size

                            self.balance += realized_pnl

                            # Record liquidation
                            self.trades.append({
                                'timestamp': timestamp,
                                'symbol': symbol,
                                'side': 'Sell' if pos_side == 'Long' else 'Buy',
                                'pos_side': pos_side,
                                'qty': position_size,
                                'price': liquidation_price,
                                'value': position_size * liquidation_price,
                                'fee': 0,
                                'action': 'LIQUIDATED',
                                'position_size': 0,
                                'position_value': 0,
                                'pnl': realized_pnl
                            })

                            # Clear position
                            self.positions[symbol] = None
                            self.position_sizes[symbol] = 0
                            self.position_entry_prices[symbol] = 0
                            self.position_values[symbol] = 0
                            self.unrealized_pnls[symbol] = 0
                            self.symbol_margins[symbol] = 0

                    self.liquidations += 1
                    print(f"   Balance after liquidation: ${self.balance:.2f}")
                    print(f"   Remaining: ${self.balance:.2f} ({(self.balance/self.initial_balance)*100:.1f}% of initial)")
                    break  # Stop backtest after liquidation

            # Record balance snapshot with per-symbol margins
            total_value = self.balance + total_unrealized_pnl
            self.balance_history.append({
                'timestamp': timestamp,
                'balance': self.balance,
                'total_margin': total_used_margin,
                'total_unrealized_pnl': total_unrealized_pnl,
                'total_value': total_value,
                'symbol_margins': {s: self.symbol_margins[s] for s in self.symbols},
                'symbol_unrealized_pnls': {s: self.unrealized_pnls[s] for s in self.symbols}
            })

            # Track drawdown
            if total_value > self.peak_total_value:
                self.peak_total_value = total_value

            drawdown_pct = ((self.peak_total_value - total_value) / self.peak_total_value) * 100
            drawdown_abs = self.peak_total_value - total_value
            if drawdown_pct > self.max_drawdown:
                self.max_drawdown = drawdown_pct
                self.max_drawdown_absolute = drawdown_abs

        # Close any remaining positions
        for symbol in self.symbols:
            if self.positions.get(symbol):
                print(f"\n📊 Closing remaining {symbol} position at end of backtest")
                df = df_dict[symbol]
                final_price = float(df.iloc[-1]['close'])
                position_size = self.position_sizes[symbol]
                self.execute_trade(
                    symbol, position_size, final_price,
                    'Sell' if pos_side == 'Long' else 'Buy', pos_side, timestamp
                )

        # Store symbol price histories for charting
        self.symbol_price_histories = symbol_price_histories

        self._print_multi_symbol_results(pos_side)
        self.generate_multi_symbol_charts(pos_side)

    def _manage_position_backtest(self, symbol, current_price, ema_200, ema_50, ema_100_1h,
                                   position, total_balance, pos_side, automatic_mode,
                                   historical_df, current_idx, timestamp):
        """
        Full position management for backtesting with volatility protection.

        Simulates check_volatility() and decline_velocity using historical data.
        Uses 1h EMA100 for dip-buying filter: Only opens when price is BELOW 1h EMA100.
        """

        conclusion = "Nothing changed"

        # Simulate volatility check using recent historical data
        # Get last 100 candles for volatility analysis
        lookback_start = max(0, current_idx - 100)
        recent_data = historical_df.iloc[lookback_start:current_idx + 1]

        # Import volatility indicators
        from indicators.volatility import VolatilityIndicators

        # Check volatility and decline velocity
        is_high_volatility, vol_metrics = VolatilityIndicators.is_high_volatility(recent_data)
        decline_velocity = VolatilityIndicators.calculate_decline_velocity(recent_data) if len(recent_data) >= 30 else {}

        # Extract decline velocity metrics
        decline_type = decline_velocity.get('decline_type', 'UNKNOWN') if decline_velocity else 'UNKNOWN'
        velocity_score = decline_velocity.get('velocity_score', 0) if decline_velocity else 0

        # Determine if decline is safe for adding to position
        is_safe_decline = decline_type in ['SLOW_DECLINE', 'MODERATE_DECLINE']
        is_dangerous_decline = decline_type in ['FAST_DECLINE', 'CRASH']

        if position:
            # Extract position details
            position_value = float(position['positionValue'])
            unrealised_pnl = float(position['unrealisedPnl'])
            upnl_percentage = float(position['upnlPercentage'])
            position_size_percentage = float(position['position_size_percentage'])
            side = "Buy" if pos_side == "Long" else "Sell"
            position_factor = position_value / total_balance

            # Check if profitable - take profits
            if (unrealised_pnl/total_balance > self.strategy.profit_threshold
                and position_factor >= self.strategy.buy_until_limit):

                # Check thresholds
                if position_size_percentage > 10:
                    # Close 50%
                    close_qty = position['size'] * 0.5
                    self.execute_trade(symbol, close_qty, current_price,
                                     'Sell' if pos_side == 'Long' else 'Buy', pos_side, timestamp)
                    conclusion = "Closed 50% - position > 10%"

                elif position_size_percentage > 7.5:
                    # Close 33%
                    close_qty = position['size'] * 0.33
                    self.execute_trade(symbol, close_qty, current_price,
                                     'Sell' if pos_side == 'Long' else 'Buy', pos_side, timestamp)
                    conclusion = "Closed 33% - position > 7.5%"

                elif upnl_percentage > self.strategy.profit_pnl:
                    # Close full position
                    self.execute_trade(symbol, position['size'], current_price,
                                     'Sell' if pos_side == 'Long' else 'Buy', pos_side, timestamp)
                    conclusion = "Closed full position - target profit"

            # Check if should add to position (WITH PROTECTIONS)
            # Enhanced logic with decline velocity analysis
            elif (
                    position.get('margin_level', 999) < 2  # Critical: margin level requires maintenance - always add
                    or (
                        # Normal conditions - check both volatility AND decline velocity
                        not is_dangerous_decline and (  # Only add if NOT a crash/fast decline
                            # Slow/moderate decline is GOOD for Martingale - safe to add
                            (is_safe_decline and position_factor < self.strategy.buy_until_limit * 1.5) or  # Allow 50% more position size on slow declines
                            # Normal volatility - standard rules
                            (not is_high_volatility and (
                                position_factor < self.strategy.buy_until_limit  # Position size is within limits
                                or (unrealised_pnl < 0 and upnl_percentage < -0.05  # Buy at a dip
                                    and (pos_side == 'Long' and current_price > ema_50)  # Valid position side
                                    or (pos_side == 'Short' and current_price < ema_50))
                            ))
                        )
                    )
            ):
                # Calculate order quantity
                if position_value == 0:
                    qty = (total_balance * self.strategy.proportion_of_balance) * self.strategy.leverage / current_price
                else:
                    qty = (position_value * self.strategy.leverage * (-upnl_percentage)) / current_price

                # Apply dynamic tapering if margin cap is enabled
                if self.strategy.max_margin_pct:
                    # Calculate current margin usage
                    current_margin_pct = position_value / total_balance if position_value > 0 else 0

                    # Taper factor: 1.0 at 0% margin, 0.0 at max_margin_pct
                    # Use exponential tapering for smoother reduction
                    if current_margin_pct < self.strategy.max_margin_pct:
                        taper_factor = ((self.strategy.max_margin_pct - current_margin_pct) / self.strategy.max_margin_pct) ** 2
                    else:
                        taper_factor = 0

                    original_qty = qty
                    qty = qty * taper_factor

                    # Tapering applied silently (no console output to avoid disrupting progress bar)

                # Apply minimum quantity rounding (KEY: matches real bot behavior!)
                qty = self.custom_round(qty)

                self.execute_trade(symbol, qty, current_price, side, pos_side, timestamp)
                conclusion = "Added to position"

            elif is_dangerous_decline:
                conclusion = f"Skipped add - dangerous decline ({decline_type}, score: {velocity_score:.0f})"

            elif is_high_volatility:
                conclusion = f"Skipped add - high volatility ({vol_metrics.get('trigger', 'unknown')})"

        # Open new position if automatic mode (WITH PROTECTIONS)
        # STRATEGY: Buy BELOW 1h EMA100 to catch dips (Martingale works best on pullbacks)
        elif automatic_mode and not is_high_volatility and not is_dangerous_decline and (
            (pos_side == "Long" and current_price < ema_100_1h) or
            (pos_side == "Short" and current_price > ema_100_1h)
        ):
            side = "Buy" if pos_side == "Long" else "Sell"
            qty = (total_balance * self.strategy.proportion_of_balance) * self.strategy.leverage / current_price

            # Note: No tapering for opening positions - they start small
            # Tapering only applies when adding to existing positions

            # Apply minimum quantity rounding (KEY: matches real bot behavior!)
            qty = self.custom_round(qty)

            self.execute_trade(symbol, qty, current_price, side, pos_side, timestamp)
            conclusion = "Opened new position"

        elif automatic_mode and is_dangerous_decline:
            conclusion = f"Skipped open - dangerous decline ({decline_type})"

        elif automatic_mode and is_high_volatility:
            conclusion = f"Skipped open - high volatility"

        elif automatic_mode:
            # If we get here, it's because price is on wrong side of 1h EMA100
            if pos_side == "Long":
                conclusion = f"Skipped open - price above 1h EMA100 ({current_price:.2f} > {ema_100_1h:.2f}, waiting for dip)"
            else:
                conclusion = f"Skipped open - price below 1h EMA100 ({current_price:.2f} < {ema_100_1h:.2f}, waiting for dip)"

        return conclusion

    def _print_results(self, symbol: str = "UNKNOWN", pos_side: str = "UNKNOWN"):
        """Print backtest results"""
        final_balance = self.balance
        total_return = ((final_balance - self.initial_balance) / self.initial_balance) * 100
        win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0

        print("\n" + "=" * 80)
        print("📊 BACKTEST RESULTS")
        print("=" * 80)

        # Display configuration settings
        if self.config_settings:
            print(f"\n⚙️  Configuration:")
            print(f"  {'Parameter':<25} {'Value':<20}")
            print(f"  {'-'*25} {'-'*20}")
            for key, value in self.config_settings.items():
                print(f"  {key:<25} {value:<20}")

        print(f"\n💰 Balance Summary:")
        print(f"  Initial Balance:  ${self.initial_balance:,.2f}")
        print(f"  Final Balance:    ${final_balance:,.2f}")
        print(f"  Total Return:     {total_return:+.2f}%")
        print(f"  Total Fees:       ${self.total_fees:,.2f}")

        print(f"\n📈 Trade Statistics:")
        print(f"  Total Trades:     {self.total_trades}")
        print(f"  Winning Trades:   {self.winning_trades}")
        print(f"  Losing Trades:    {self.losing_trades}")
        print(f"  Win Rate:         {win_rate:.2f}%")

        print(f"\n⚠️  Risk Metrics:")
        print(f"  Max Drawdown:     {self.max_drawdown:.2f}% (${self.max_drawdown_absolute:.2f})")
        print(f"  Peak Value:       ${self.peak_total_value:,.2f}")
        if self.liquidations > 0:
            print(f"  ⚠️  LIQUIDATIONS:  {self.liquidations} 💀")

        if self.trades:
            print(f"\n📋 Trade History (Last 10):")
            print("-" * 80)
            for trade in self.trades[-10:]:
                action = trade.get('action', 'TRADE')
                pnl_str = ""
                if 'realized_pnl' in trade:
                    pnl = trade['realized_pnl']
                    pnl_str = f" | PnL: ${pnl:+,.2f}"

                # Show position size after operation
                pos_size = trade.get('position_size', 0)
                pos_value = trade.get('position_value', 0)
                position_str = f" → Position: {pos_size:.4f} (${pos_value:.2f})" if pos_size > 0 else ""

                print(f"  {action:6} | {trade['side']:4} {trade['qty']:.4f} @ ${trade['price']:.6f}{pnl_str}{position_str}")

        print("\n" + "=" * 80)

        # Save detailed results with unique filename
        backtest_dir = Path(__file__).parent / 'results'
        backtest_dir.mkdir(exist_ok=True)

        # Create unique filename based on parameters
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        base_name = f"{symbol}_{pos_side}_bal{int(self.initial_balance)}_profit{self.strategy.profit_pnl:.2f}_{timestamp}"

        if self.balance_history:
            df_results = pd.DataFrame(self.balance_history)
            balance_csv = backtest_dir / f'{base_name}_balance.csv'
            df_results.to_csv(balance_csv, index=False)
            print(f"💾 Balance history saved to: {balance_csv}")

        if self.trades:
            df_trades = pd.DataFrame(self.trades)
            trades_csv = backtest_dir / f'{base_name}_trades.csv'
            df_trades.to_csv(trades_csv, index=False)
            print(f"💾 Trade history saved to: {trades_csv}")

    def generate_charts(self, symbol: str, pos_side: str):
        """Generate visualization charts for backtest results"""
        if not self.balance_history:
            print("⚠️  No balance history to plot")
            return

        backtest_dir = Path(__file__).parent

        # Convert balance history to DataFrame
        df = pd.DataFrame(self.balance_history)
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        # Create figure with subplots (5 panels: price, balance, position, drawdown, summary)
        fig, axes = plt.subplots(5, 1, figsize=(14, 20))
        fig.suptitle(f'Backtest Results: {symbol} ({pos_side})', fontsize=16, fontweight='bold')

        # Get price data
        price_df = pd.DataFrame(self.price_history)
        price_df['timestamp'] = pd.to_datetime(price_df['timestamp'])

        # 1. Price Chart with EMAs
        ax1 = axes[0]
        ax1.plot(price_df['timestamp'], price_df['price'], label='Price', color='#333333', linewidth=2)
        ax1.plot(price_df['timestamp'], price_df['ema_200'], label='1min EMA200', color='#FF6B35', linewidth=1.5, linestyle='--')
        ax1.plot(price_df['timestamp'], price_df['ema_100_1h'], label='1h EMA100 (Dip-Buy Filter)', color='#9B59B6', linewidth=2, linestyle='-', alpha=0.8)

        ax1.set_xlabel('Date')
        ax1.set_ylabel('Price (USDT)')
        ax1.set_title('Price Action & 1-minute EMA200')
        ax1.legend(loc='best')
        ax1.grid(True, alpha=0.3)
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))

        # 2. Balance & Total Value Chart (no trade markers)
        ax2 = axes[1]
        ax2.plot(df['timestamp'], df['balance'], label='Balance', color='#2E86AB', linewidth=2)
        ax2.plot(df['timestamp'], df['total_value'], label='Total Value (Balance + Unrealized PnL)',
                color='#A23B72', linewidth=2, linestyle='--')
        ax2.axhline(y=self.initial_balance, color='gray', linestyle=':', alpha=0.5, label='Initial Balance')

        # Mark trades on both price and balance charts
        if self.trades:
            trades_df = pd.DataFrame(self.trades)
            trades_df['timestamp'] = pd.to_datetime(trades_df['timestamp'])

            # Different colors for different actions - using high contrast colors
            for action, color, marker in [
                ('OPEN', '#00FF00', '^'),      # Bright green
                ('ADD', '#0000FF', 'v'),       # Bright blue
                ('REDUCE', '#FFA500', 's'),    # Bright orange
                ('CLOSE', '#FF0000', 'o')      # Bright red
            ]:
                action_trades = trades_df[trades_df['action'] == action]
                if not action_trades.empty:
                    # Get balance and price at trade time
                    trade_balances = []
                    trade_prices = []
                    for idx, ts in enumerate(action_trades['timestamp']):
                        balance_idx = (df['timestamp'] - ts).abs().idxmin()
                        balance_val = df.loc[balance_idx, 'total_value']
                        trade_balances.append(balance_val)

                        price_idx = (price_df['timestamp'] - ts).abs().idxmin()
                        price_val = price_df.loc[price_idx, 'price']
                        trade_prices.append(price_val)

                    # Plot markers on price chart (with label)
                    ax1.scatter(action_trades['timestamp'], trade_prices,
                              color=color, marker=marker, s=200, alpha=1.0,
                              edgecolors='black', linewidths=2.5,
                              label=f'{action} ({len(action_trades)})', zorder=10)

        ax2.set_xlabel('Date')
        ax2.set_ylabel('Balance (USDT)')
        ax2.set_title('Account Balance & Total Value')
        ax2.legend(loc='best')
        ax2.grid(True, alpha=0.3)
        ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))

        # 3. Position Size Chart (Margin)
        ax3 = axes[2]
        ax3.plot(df['timestamp'], df['position_value'], label='Position Size (Margin)',
                color='#F77F00', linewidth=2)
        ax3.fill_between(df['timestamp'], 0, df['position_value'], color='#F77F00', alpha=0.3)
        ax3.set_xlabel('Date')
        ax3.set_ylabel('Position Size (USDT)')
        ax3.set_title('Position Size Over Time (Margin Invested)')
        ax3.legend(loc='best')
        ax3.grid(True, alpha=0.3)
        ax3.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))

        # 4. Drawdown Chart (based on total value including unrealized PnL)
        ax4 = axes[3]
        df['peak'] = df['total_value'].expanding().max()
        df['drawdown'] = ((df['peak'] - df['total_value']) / df['peak']) * 100

        ax4.fill_between(df['timestamp'], 0, df['drawdown'], color='#C73E1D', alpha=0.3)
        ax4.plot(df['timestamp'], df['drawdown'], color='#C73E1D', linewidth=2)
        ax4.axhline(y=self.max_drawdown, color='darkred', linestyle='--',
                   label=f'Max Drawdown: {self.max_drawdown:.2f}%')

        ax4.set_xlabel('Date')
        ax4.set_ylabel('Drawdown (%)')
        ax4.set_title('Drawdown Analysis')
        ax4.legend(loc='best')
        ax4.grid(True, alpha=0.3)
        ax4.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        ax4.invert_yaxis()  # Drawdown goes down

        # 5. Performance Metrics Summary
        ax5 = axes[4]
        ax5.axis('off')

        # Calculate metrics
        final_balance = self.balance
        total_return = ((final_balance - self.initial_balance) / self.initial_balance) * 100
        win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0

        # Calculate average win/loss
        if self.trades:
            trades_df = pd.DataFrame(self.trades)
            closed_trades = trades_df[trades_df['action'].isin(['CLOSE', 'REDUCE'])]
            if not closed_trades.empty and 'realized_pnl' in closed_trades.columns:
                wins = closed_trades[closed_trades['realized_pnl'] > 0]['realized_pnl']
                losses = closed_trades[closed_trades['realized_pnl'] < 0]['realized_pnl']
                avg_win = wins.mean() if not wins.empty else 0
                avg_loss = losses.mean() if not losses.empty else 0
            else:
                avg_win = avg_loss = 0
        else:
            avg_win = avg_loss = 0

        # Count total operations
        total_operations = len(self.trades) if self.trades else 0
        open_ops = len([t for t in self.trades if t.get('action') == 'OPEN']) if self.trades else 0
        add_ops = len([t for t in self.trades if t.get('action') == 'ADD']) if self.trades else 0
        reduce_ops = len([t for t in self.trades if t.get('action') == 'REDUCE']) if self.trades else 0
        close_ops = len([t for t in self.trades if t.get('action') == 'CLOSE']) if self.trades else 0

        # Create summary text
        summary_text = f"""
        📊 PERFORMANCE SUMMARY

        Initial Balance:        ${self.initial_balance:,.2f}
        Final Balance:          ${final_balance:,.2f}
        Total Return:           {total_return:+.2f}%
        Total Fees Paid:        ${self.total_fees:,.2f}

        Completed Positions:    {self.total_trades} (full round-trips)
        Winning Positions:      {self.winning_trades}
        Losing Positions:       {self.losing_trades}
        Win Rate:               {win_rate:.2f}%

        Total Operations:       {total_operations}
          - OPEN:  {open_ops}  |  ADD:  {add_ops}
          - REDUCE: {reduce_ops}  |  CLOSE: {close_ops}

        Average Win:            ${avg_win:+.2f}
        Average Loss:           ${avg_loss:+.2f}

        Max Drawdown:           {self.max_drawdown:.2f}% (${self.max_drawdown_absolute:.2f})
        Peak Value:             ${self.peak_total_value:,.2f}
        """

        ax5.text(0.05, 0.5, summary_text, transform=ax5.transAxes,
                fontsize=11, verticalalignment='center', family='monospace',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))

        # Create configuration text (right side)
        if self.config_settings:
            config_lines = ["        ⚙️  CONFIGURATION\n"]
            for key, value in self.config_settings.items():
                config_lines.append(f"        {key:<20} {value}")
            config_text = "\n".join(config_lines)

            ax5.text(0.55, 0.5, config_text, transform=ax5.transAxes,
                    fontsize=11, verticalalignment='center', family='monospace',
                    bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.3))

        # Adjust layout and save
        plt.tight_layout()

        # Use same unique filename as CSVs
        backtest_dir = Path(__file__).parent / 'results'
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        base_name = f"{symbol}_{pos_side}_bal{int(self.initial_balance)}_profit{self.strategy.profit_pnl:.2f}_{timestamp}"

        chart_path = backtest_dir / f'{base_name}_chart.png'
        plt.savefig(chart_path, dpi=150, bbox_inches='tight')
        print(f"📈 Backtest chart saved to: {chart_path}")

        plt.close()

    def _print_multi_symbol_results(self, pos_side: str):
        """Print multi-symbol backtest results with per-symbol breakdown"""
        final_balance = self.balance
        total_return = ((final_balance - self.initial_balance) / self.initial_balance) * 100

        # Calculate per-symbol statistics
        symbol_stats = {}
        for symbol in self.symbols:
            wins = self.symbol_winning_trades.get(symbol, 0)
            losses = self.symbol_losing_trades.get(symbol, 0)
            total = wins + losses
            win_rate = (wins / total * 100) if total > 0 else 0
            total_pnl = self.symbol_total_pnl.get(symbol, 0)
            num_trades = len(self.symbol_trades.get(symbol, []))

            symbol_stats[symbol] = {
                'trades': num_trades,
                'completed': total,
                'wins': wins,
                'losses': losses,
                'win_rate': win_rate,
                'total_pnl': total_pnl
            }

        print("\n" + "=" * 80)
        print(f"📊 MULTI-SYMBOL BACKTEST RESULTS ({len(self.symbols)} symbols)")
        print("=" * 80)

        # Display configuration
        if self.config_settings:
            print(f"\n⚙️  Configuration:")
            print(f"  {'Parameter':<25} {'Value':<20}")
            print(f"  {'-'*25} {'-'*20}")
            for key, value in self.config_settings.items():
                print(f"  {key:<25} {value:<20}")

        print(f"\n💰 Balance Summary:")
        print(f"  Initial Balance:  ${self.initial_balance:,.2f}")
        print(f"  Final Balance:    ${final_balance:,.2f}")
        print(f"  Total Return:     {total_return:+.2f}%")
        print(f"  Total Fees:       ${self.total_fees:,.2f}")

        print(f"\n📈 Per-Symbol Statistics:")
        print(f"  {'Symbol':<12} {'Trades':<8} {'Completed':<10} {'Wins':<6} {'Losses':<7} {'Win Rate':<10} {'Total PnL':<12}")
        print(f"  {'-'*12} {'-'*8} {'-'*10} {'-'*6} {'-'*7} {'-'*10} {'-'*12}")
        for symbol in self.symbols:
            stats = symbol_stats[symbol]
            pnl_str = f"${stats['total_pnl']:+,.2f}"
            print(f"  {symbol:<12} {stats['trades']:<8} {stats['completed']:<10} {stats['wins']:<6} "
                  f"{stats['losses']:<7} {stats['win_rate']:>7.1f}%   {pnl_str:>10}")

        print(f"\n⚠️  Risk Metrics:")
        print(f"  Max Drawdown:     {self.max_drawdown:.2f}% (${self.max_drawdown_absolute:.2f})")
        print(f"  Peak Value:       ${self.peak_total_value:,.2f}")
        if self.liquidations > 0:
            print(f"  ⚠️  LIQUIDATIONS:  {self.liquidations} 💀")

        # Calculate correlation
        if len(self.symbols) == 2 and hasattr(self, 'symbol_price_histories'):
            print(f"\n🔗 Symbol Correlation:")
            symbol1, symbol2 = self.symbols[0], self.symbols[1]
            prices1 = [p['price'] for p in self.symbol_price_histories[symbol1]]
            prices2 = [p['price'] for p in self.symbol_price_histories[symbol2]]

            if len(prices1) == len(prices2) and len(prices1) > 0:
                correlation = np.corrcoef(prices1, prices2)[0, 1]
                print(f"  {symbol1} vs {symbol2}: {correlation:.4f}")

                if correlation > 0.7:
                    print(f"  ⚠️  High positive correlation - symbols move together (less diversification)")
                elif correlation < -0.7:
                    print(f"  ✅ High negative correlation - symbols move opposite (good diversification)")
                else:
                    print(f"  ✅ Low correlation - good diversification")

        # Show last 10 trades across all symbols
        if self.trades:
            print(f"\n📋 Trade History (Last 10 across all symbols):")
            print("-" * 90)
            for trade in self.trades[-10:]:
                action = trade.get('action', 'TRADE')
                symbol = trade.get('symbol', '???')
                pnl_str = ""
                if 'realized_pnl' in trade:
                    pnl = trade['realized_pnl']
                    pnl_str = f" | PnL: ${pnl:+,.2f}"

                pos_size = trade.get('position_size', 0)
                pos_value = trade.get('position_value', 0)
                position_str = f" → Pos: {pos_size:.4f} (${pos_value:.2f})" if pos_size > 0 else ""

                print(f"  {symbol:<10} {action:6} | {trade['side']:4} {trade['qty']:.4f} @ "
                      f"${trade['price']:.6f}{pnl_str}{position_str}")

        # Analysis and Conclusion Section
        print(f"\n{'='*80}")
        print(f"📊 ANALYSIS & CONCLUSION")
        print(f"{'='*80}")

        # Calculate margin usage statistics per symbol
        max_margins = {}
        avg_margins = {}
        margin_utilization = {}

        for symbol in self.symbols:
            symbol_margins_list = [row['symbol_margins'].get(symbol, 0) for row in self.balance_history if 'symbol_margins' in row]
            if symbol_margins_list:
                max_margins[symbol] = max(symbol_margins_list)
                avg_margins[symbol] = sum(symbol_margins_list) / len(symbol_margins_list)
                margin_utilization[symbol] = (max_margins[symbol] / self.initial_balance) * 100
            else:
                max_margins[symbol] = 0
                avg_margins[symbol] = 0
                margin_utilization[symbol] = 0

        # Calculate total margin statistics
        total_margins_list = [row.get('total_margin', 0) for row in self.balance_history if 'total_margin' in row]
        max_total_margin = max(total_margins_list) if total_margins_list else 0
        avg_total_margin = sum(total_margins_list) / len(total_margins_list) if total_margins_list else 0
        max_total_margin_pct = (max_total_margin / self.initial_balance) * 100
        avg_total_margin_pct = (avg_total_margin / self.initial_balance) * 100

        print(f"\n💼 Margin Usage Analysis:")
        print(f"  {'Symbol':<12} {'Max Margin':<15} {'Avg Margin':<15} {'Peak Usage':<12}")
        print(f"  {'-'*12} {'-'*15} {'-'*15} {'-'*12}")
        for symbol in self.symbols:
            print(f"  {symbol:<12} ${max_margins[symbol]:>8.2f}      ${avg_margins[symbol]:>8.2f}      {margin_utilization[symbol]:>6.1f}%")

        print(f"\n  {'Total (All)':<12} ${max_total_margin:>8.2f}      ${avg_total_margin:>8.2f}      {max_total_margin_pct:>6.1f}%")

        if self.max_margin_pct:
            margin_cap = self.initial_balance * self.max_margin_pct
            margin_buffer = margin_cap - max_total_margin
            buffer_pct = (margin_buffer / margin_cap) * 100
            print(f"  {'Margin Cap':<12} ${margin_cap:>8.2f}      Remaining: ${margin_buffer:>6.2f} ({buffer_pct:.1f}%)")

        # Correlation analysis (if 2 symbols)
        if len(self.symbols) == 2 and hasattr(self, 'symbol_price_histories'):
            symbol1, symbol2 = self.symbols[0], self.symbols[1]
            prices1 = [p['price'] for p in self.symbol_price_histories[symbol1]]
            prices2 = [p['price'] for p in self.symbol_price_histories[symbol2]]

            if len(prices1) == len(prices2) and len(prices1) > 0:
                correlation = np.corrcoef(prices1, prices2)[0, 1]

                print(f"\n🔗 Correlation Analysis:")
                print(f"  {symbol1} vs {symbol2}: {correlation:.4f}")

                if abs(correlation) > 0.7:
                    if correlation > 0:
                        print(f"  ⚠️  HIGH POSITIVE CORRELATION ({correlation:.2f})")
                        print(f"     → Symbols move together, offering LIMITED diversification")
                        print(f"     → Both positions likely to be in drawdown simultaneously")
                        print(f"     → Margin competition without risk reduction benefits")
                    else:
                        print(f"  ✅ HIGH NEGATIVE CORRELATION ({correlation:.2f})")
                        print(f"     → Symbols move opposite, offering EXCELLENT diversification")
                        print(f"     → One position often profits while other is in drawdown")
                        print(f"     → Natural hedging effect reduces overall risk")
                elif abs(correlation) < 0.3:
                    print(f"  ✅ VERY LOW CORRELATION ({correlation:.2f})")
                    print(f"     → Symbols move independently")
                    print(f"     → Good diversification, uncorrelated risk exposure")
                else:
                    print(f"  ✅ MODERATE CORRELATION ({correlation:.2f})")
                    print(f"     → Some correlation but still beneficial diversification")

        # Performance assessment
        print(f"\n📈 Performance Assessment:")

        # Calculate actual returns per symbol
        winning_symbols = [s for s in self.symbols if self.symbol_total_pnl.get(s, 0) > 0]
        losing_symbols = [s for s in self.symbols if self.symbol_total_pnl.get(s, 0) <= 0]

        print(f"  Profitable symbols: {len(winning_symbols)}/{len(self.symbols)}")
        if winning_symbols:
            print(f"    Winners: {', '.join([f'{s} (${self.symbol_total_pnl[s]:+.2f})' for s in winning_symbols])}")
        if losing_symbols:
            print(f"    Losers:  {', '.join([f'{s} (${self.symbol_total_pnl[s]:+.2f})' for s in losing_symbols])}")

        # Risk metrics
        risk_score = 0
        risk_factors = []

        if self.max_drawdown > 10:
            risk_factors.append(f"High drawdown ({self.max_drawdown:.1f}%)")
            risk_score += 2
        elif self.max_drawdown > 5:
            risk_factors.append(f"Moderate drawdown ({self.max_drawdown:.1f}%)")
            risk_score += 1

        if self.max_margin_pct and max_total_margin_pct > (self.max_margin_pct * 100 * 0.9):
            risk_factors.append(f"Margin cap nearly reached ({max_total_margin_pct:.1f}%)")
            risk_score += 2

        if len(self.symbols) == 2 and hasattr(self, 'symbol_price_histories'):
            prices1 = [p['price'] for p in self.symbol_price_histories[self.symbols[0]]]
            prices2 = [p['price'] for p in self.symbol_price_histories[self.symbols[1]]]
            if len(prices1) > 0:
                correlation = np.corrcoef(prices1, prices2)[0, 1]
                if correlation > 0.7:
                    risk_factors.append(f"High positive correlation ({correlation:.2f})")
                    risk_score += 2

        print(f"\n  Risk Level: ", end="")
        if risk_score >= 4:
            print(f"🔴 HIGH RISK")
        elif risk_score >= 2:
            print(f"🟡 MODERATE RISK")
        else:
            print(f"🟢 LOW RISK")

        if risk_factors:
            print(f"  Risk Factors:")
            for factor in risk_factors:
                print(f"    • {factor}")

        # Overall conclusion
        print(f"\n🎯 Conclusion:")

        # Assess overall quality
        is_profitable = total_return > 0
        has_good_diversification = True
        if len(self.symbols) == 2 and hasattr(self, 'symbol_price_histories'):
            prices1 = [p['price'] for p in self.symbol_price_histories[self.symbols[0]]]
            prices2 = [p['price'] for p in self.symbol_price_histories[self.symbols[1]]]
            if len(prices1) > 0:
                correlation = np.corrcoef(prices1, prices2)[0, 1]
                has_good_diversification = abs(correlation) < 0.7

        margin_is_safe = True
        if self.max_margin_pct:
            margin_is_safe = max_total_margin_pct < (self.max_margin_pct * 100 * 0.85)

        multiple_winners = len(winning_symbols) > 0

        # Overall verdict
        if is_profitable and has_good_diversification and margin_is_safe and multiple_winners:
            print(f"  ✅ GOOD SETUP - This symbol combination shows promise")
            print(f"     • Profitable with {total_return:+.2f}% return")
            if has_good_diversification:
                print(f"     • Good diversification reduces risk")
            if margin_is_safe:
                print(f"     • Safe margin usage with buffer remaining")
            print(f"     • {len(winning_symbols)} of {len(self.symbols)} symbols contributed positively")
        elif has_good_diversification and margin_is_safe:
            print(f"  ⚠️  ACCEPTABLE SETUP - Mixed results but manageable risk")
            if not is_profitable:
                print(f"     • Unprofitable this period ({total_return:+.2f}%), but may be timing")
            if has_good_diversification:
                print(f"     • Good diversification provides risk protection")
            if margin_is_safe:
                print(f"     • Margin usage is safe with room for more drawdown")
        else:
            print(f"  ❌ POOR SETUP - Consider alternative symbol combinations")
            if not has_good_diversification:
                print(f"     • High correlation means limited diversification benefit")
            if not margin_is_safe:
                print(f"     • Margin usage too high ({max_total_margin_pct:.1f}%), risky for liquidation")
            if not multiple_winners:
                print(f"     • No symbols showing consistent profitability")

        # Recommendations
        print(f"\n💡 Recommendations:")
        if not has_good_diversification and len(self.symbols) == 2:
            print(f"     • Choose symbols with lower correlation (< 0.5) for better diversification")
            print(f"     • Consider pairing coins from different sectors (e.g., L1 + meme, DeFi + L1)")

        if not margin_is_safe:
            print(f"     • Increase initial balance or reduce position sizes")
            print(f"     • Consider reducing max_margin_pct to maintain larger safety buffer")

        if len(losing_symbols) == len(self.symbols):
            print(f"     • All symbols unprofitable - reconsider strategy parameters or market conditions")
            print(f"     • Test different leverage, profit targets, or EMA intervals")

        if self.max_drawdown > 10:
            print(f"     • High drawdown indicates excessive risk - consider lower leverage")
            print(f"     • Add more capital or reduce position sizes to weather drawdowns")

        print("\n" + "=" * 80)

        # Save results
        backtest_dir = Path(__file__).parent / 'results'
        backtest_dir.mkdir(exist_ok=True)

        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        symbols_str = '_'.join(self.symbols)
        base_name = f"multi_{symbols_str}_{pos_side}_bal{int(self.initial_balance)}_{timestamp}"

        if self.balance_history:
            df_results = pd.DataFrame(self.balance_history)
            balance_csv = backtest_dir / f'{base_name}_balance.csv'
            df_results.to_csv(balance_csv, index=False)
            print(f"💾 Balance history saved to: {balance_csv}")

        if self.trades:
            df_trades = pd.DataFrame(self.trades)
            trades_csv = backtest_dir / f'{base_name}_trades.csv'
            df_trades.to_csv(trades_csv, index=False)
            print(f"💾 Trade history saved to: {trades_csv}")

    def generate_multi_symbol_charts(self, pos_side: str):
        """Generate visualization charts for multi-symbol backtest"""
        if not self.balance_history:
            print("⚠️  No balance history to plot")
            return

        backtest_dir = Path(__file__).parent / 'results'

        # Convert balance history to DataFrame
        df = pd.DataFrame(self.balance_history)
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        # Create figure with subplots
        num_symbols = len(self.symbols)
        fig, axes = plt.subplots(4 + num_symbols, 1, figsize=(14, 6 * (4 + num_symbols)))
        symbols_str = ' + '.join(self.symbols)
        fig.suptitle(f'Multi-Symbol Backtest: {symbols_str} ({pos_side})', fontsize=16, fontweight='bold')

        # Panel 1-N: Price charts for each symbol
        for idx, symbol in enumerate(self.symbols):
            ax = axes[idx]
            price_df = pd.DataFrame(self.symbol_price_histories[symbol])
            price_df['timestamp'] = pd.to_datetime(price_df['timestamp'])

            # Plot price and EMAs
            ax.plot(price_df['timestamp'], price_df['price'], label='Price', color='black', linewidth=1.5)
            ax.plot(price_df['timestamp'], price_df['ema_200'], label='EMA200', color='blue', linewidth=1, linestyle='--')
            ax.plot(price_df['timestamp'], price_df['ema_100_1h'], label='1h EMA100 (Dip Filter)',
                   color='purple', linewidth=1, linestyle='--')

            # Plot trades for this symbol
            symbol_trades = self.symbol_trades.get(symbol, [])
            for trade in symbol_trades:
                action = trade.get('action', 'TRADE')
                timestamp = pd.to_datetime(trade['timestamp'])
                price = trade['price']

                if action == 'OPEN':
                    ax.scatter(timestamp, price, color='green', marker='^', s=100, zorder=5, label='OPEN' if 'OPEN' not in ax.get_legend_handles_labels()[1] else '')
                elif action == 'ADD':
                    ax.scatter(timestamp, price, color='blue', marker='^', s=60, alpha=0.6, zorder=5, label='ADD' if 'ADD' not in ax.get_legend_handles_labels()[1] else '')
                elif action == 'REDUCE':
                    ax.scatter(timestamp, price, color='orange', marker='s', s=60, alpha=0.7, zorder=5, label='REDUCE' if 'REDUCE' not in ax.get_legend_handles_labels()[1] else '')
                elif action == 'CLOSE':
                    ax.scatter(timestamp, price, color='red', marker='o', s=80, zorder=5, label='CLOSE' if 'CLOSE' not in ax.get_legend_handles_labels()[1] else '')
                elif action == 'LIQUIDATED':
                    ax.scatter(timestamp, price, color='black', marker='X', s=150, zorder=5, label='LIQUIDATED' if 'LIQUIDATED' not in ax.get_legend_handles_labels()[1] else '')

            ax.set_title(f'{symbol} Price & Positions', fontweight='bold')
            ax.set_ylabel('Price (USDT)')
            ax.legend(loc='upper left', fontsize=8)
            ax.grid(True, alpha=0.3)

        # Panel N+1: Account Balance & Total Value
        ax_balance = axes[num_symbols]
        ax_balance.plot(df['timestamp'], df['balance'], label='Balance (Realized)', color='blue', linewidth=1.5)
        ax_balance.plot(df['timestamp'], df['total_value'], label='Total Value (Balance + Unrealized PnL)',
                       color='purple', linewidth=1.5, linestyle='--')
        ax_balance.axhline(y=self.initial_balance, color='gray', linestyle=':', label='Initial Balance')
        ax_balance.set_title('Account Balance & Total Value', fontweight='bold')
        ax_balance.set_ylabel('Balance (USDT)')
        ax_balance.legend()
        ax_balance.grid(True, alpha=0.3)

        # Panel N+2: Per-Symbol Margin Usage (Stacked)
        ax_margin = axes[num_symbols + 1]
        margins_df = pd.DataFrame([{
            'timestamp': row['timestamp'],
            **row['symbol_margins']
        } for row in self.balance_history])
        margins_df['timestamp'] = pd.to_datetime(margins_df['timestamp'])

        # Create stacked area chart
        margin_data = margins_df[self.symbols].values.T
        ax_margin.stackplot(margins_df['timestamp'], *margin_data, labels=self.symbols, alpha=0.7)

        # Add total margin cap line if configured
        if self.max_margin_pct:
            max_margin_line = self.initial_balance * self.max_margin_pct
            ax_margin.axhline(y=max_margin_line, color='red', linestyle='--', linewidth=2,
                             label=f'Max Margin Cap ({self.max_margin_pct*100:.0f}%)')

        ax_margin.set_title('Per-Symbol Margin Usage (Stacked)', fontweight='bold')
        ax_margin.set_ylabel('Margin (USDT)')
        ax_margin.legend(loc='upper left')
        ax_margin.grid(True, alpha=0.3)

        # Panel N+3: Drawdown Analysis
        ax_dd = axes[num_symbols + 2]
        drawdowns = []
        peak = self.initial_balance
        for _, row in df.iterrows():
            total_val = row['total_value']
            if total_val > peak:
                peak = total_val
            dd_pct = ((peak - total_val) / peak) * 100
            drawdowns.append(dd_pct)

        ax_dd.fill_between(df['timestamp'], 0, drawdowns, color='red', alpha=0.3, label='Drawdown')
        ax_dd.axhline(y=self.max_drawdown, color='darkred', linestyle='--',
                     label=f'Max Drawdown: {self.max_drawdown:.2f}%')
        ax_dd.set_title('Drawdown Analysis', fontweight='bold')
        ax_dd.set_ylabel('Drawdown (%)')
        ax_dd.legend()
        ax_dd.grid(True, alpha=0.3)
        ax_dd.invert_yaxis()

        # Panel N+4: Performance Summary
        ax_summary = axes[num_symbols + 3]
        ax_summary.axis('off')

        final_balance = self.balance
        total_return = ((final_balance - self.initial_balance) / self.initial_balance) * 100

        summary_text = f"""
PERFORMANCE SUMMARY

Initial Balance:  ${self.initial_balance:,.2f}
Final Balance:    ${final_balance:,.2f}
Total Return:     {total_return:+.2f}%
Total Fees Paid:  ${self.total_fees:,.2f}

Max Drawdown:     {self.max_drawdown:.2f}% (${self.max_drawdown_absolute:.2f})
Peak Value:       ${self.peak_total_value:,.2f}
"""

        # Add per-symbol statistics
        summary_text += "\nPER-SYMBOL BREAKDOWN\n"
        for symbol in self.symbols:
            wins = self.symbol_winning_trades.get(symbol, 0)
            losses = self.symbol_losing_trades.get(symbol, 0)
            total = wins + losses
            win_rate = (wins / total * 100) if total > 0 else 0
            total_pnl = self.symbol_total_pnl.get(symbol, 0)
            num_trades = len(self.symbol_trades.get(symbol, []))

            summary_text += f"{symbol}: {num_trades} trades, {total} completed ({wins}W/{losses}L), "
            summary_text += f"{win_rate:.1f}% win rate, ${total_pnl:+.2f} PnL\n"

        # Add correlation if 2 symbols
        correlation = None
        if len(self.symbols) == 2:
            symbol1, symbol2 = self.symbols[0], self.symbols[1]
            prices1 = [p['price'] for p in self.symbol_price_histories[symbol1]]
            prices2 = [p['price'] for p in self.symbol_price_histories[symbol2]]
            if len(prices1) == len(prices2) and len(prices1) > 0:
                correlation = np.corrcoef(prices1, prices2)[0, 1]
                summary_text += f"\nCORRELATION\n{symbol1} vs {symbol2}: {correlation:.4f}"

        # Add margin usage statistics
        total_margins_list = [row.get('total_margin', 0) for row in self.balance_history if 'total_margin' in row]
        max_total_margin = max(total_margins_list) if total_margins_list else 0
        max_total_margin_pct = (max_total_margin / self.initial_balance) * 100

        summary_text += f"\n\nMARGIN USAGE\n"
        summary_text += f"Peak Total Margin: ${max_total_margin:.2f} ({max_total_margin_pct:.1f}%)\n"
        if self.max_margin_pct:
            margin_cap = self.initial_balance * self.max_margin_pct
            margin_buffer = margin_cap - max_total_margin
            summary_text += f"Margin Cap: ${margin_cap:.2f}, Buffer: ${margin_buffer:.2f}"

        # Calculate conclusion
        is_profitable = total_return > 0
        has_good_diversification = True
        if correlation is not None:
            has_good_diversification = abs(correlation) < 0.7

        margin_is_safe = True
        if self.max_margin_pct:
            margin_is_safe = max_total_margin_pct < (self.max_margin_pct * 100 * 0.85)

        winning_symbols = [s for s in self.symbols if self.symbol_total_pnl.get(s, 0) > 0]
        multiple_winners = len(winning_symbols) > 0

        # Add conclusion to chart
        summary_text += f"\n\nCONCLUSION\n"

        if is_profitable and has_good_diversification and margin_is_safe and multiple_winners:
            summary_text += "✅ GOOD SETUP\n"
            summary_text += f"Profitable ({total_return:+.2f}%), good diversification,\n"
            summary_text += f"safe margins. {len(winning_symbols)}/{len(self.symbols)} symbols profitable."
        elif has_good_diversification and margin_is_safe:
            summary_text += "⚠️ ACCEPTABLE SETUP\n"
            if not is_profitable:
                summary_text += f"Unprofitable ({total_return:+.2f}%), may be timing.\n"
            summary_text += "Good diversification, safe margin usage."
        else:
            summary_text += "❌ POOR SETUP\n"
            if not has_good_diversification:
                summary_text += "High correlation, limited diversification.\n"
            if not margin_is_safe:
                summary_text += f"Margin too high ({max_total_margin_pct:.1f}%), risky.\n"
            if not multiple_winners:
                summary_text += "No consistently profitable symbols."

        ax_summary.text(0.1, 0.9, summary_text, transform=ax_summary.transAxes,
                       fontsize=9, verticalalignment='top', fontfamily='monospace',
                       bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))

        plt.tight_layout()

        # Save chart
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        symbols_str = '_'.join(self.symbols)
        chart_path = backtest_dir / f'multi_{symbols_str}_{pos_side}_bal{int(self.initial_balance)}_{timestamp}_chart.png'

        plt.savefig(chart_path, dpi=150, bbox_inches='tight')
        print(f"📈 Multi-symbol backtest chart saved to: {chart_path}")

        plt.close()


def main():
    parser = argparse.ArgumentParser(description='Backtest DCABot Martingale Strategy')

    # Symbol arguments - either --symbol OR --symbols, but not both
    symbol_group = parser.add_mutually_exclusive_group(required=True)
    symbol_group.add_argument('--symbol', type=str,
                       help='Single trading symbol (e.g., BTCUSDT)')
    symbol_group.add_argument('--symbols', type=str, nargs='+',
                       help='Multiple trading symbols (e.g., BTCUSDT TRXUSDT SOLUSDT)')

    parser.add_argument('--side', type=str, default='Long', choices=['Long', 'Short'],
                       help='Position side (default: Long)')
    parser.add_argument('--days', type=int, default=7,
                       help='Number of days to backtest (default: 7)')
    parser.add_argument('--interval', type=int, default=5,
                       help='Candle interval in minutes (default: 5)')
    parser.add_argument('--balance', type=float, default=10000.0,
                       help='Initial balance in USDT (default: 10000)')
    parser.add_argument('--source', type=str, default='binance', choices=['phemex', 'binance'],
                       help='Data source: binance (extended history) or phemex (live API) (default: binance)')
    parser.add_argument('--profit-pnl', type=float, default=None,
                       help='Override profit_pnl threshold (e.g., 0.15 for 15%% profit target)')
    parser.add_argument('--max-margin-pct', type=float, default=None,
                       help='Optional maximum margin usage as percentage (e.g., 0.40 = 40%% cap). When absent, no margin cap is applied.')
    parser.add_argument('--leverage', type=int, default=None,
                       help='Override leverage (e.g., 5, 10, 20). Default: 10x')

    args = parser.parse_args()

    # Determine if multi-symbol mode
    if args.symbols:
        symbols = args.symbols
        multi_symbol = True
    else:
        symbols = [args.symbol]
        multi_symbol = False

    # Load environment from parent directory
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)

    # Setup logging
    logging.basicConfig(
        level=logging.WARNING,  # Reduce noise during backtest
        format='%(message)s'
    )
    logger = logging.getLogger(__name__)

    # Initialize client and strategy
    api_key = os.getenv('API_KEY')
    api_secret = os.getenv('API_SECRET')
    testnet = os.getenv('TESTNET', 'True').lower() in ('true', '1', 't')

    if not api_key or not api_secret:
        print("❌ Error: API_KEY and API_SECRET must be set in .env file")
        return

    print(f"🔧 Initializing backtest...")
    if multi_symbol:
        print(f"  Symbols: {', '.join(symbols)} (Multi-Symbol Mode)")
    else:
        print(f"  Symbol: {symbols[0]}")
    print(f"  Side: {args.side}")
    print(f"  Period: {args.days} days")
    print(f"  Interval: {args.interval} minutes")
    print(f"  Initial Balance: ${args.balance:,.2f}")
    print(f"  Data Source: {args.source.upper()}")
    if args.source == 'phemex':
        print(f"  Testnet: {testnet}")

    client = PhemexClient(api_key, api_secret, logger, testnet)
    strategy = MartingaleTradingStrategy(client=client, logger=logger, notifier=None)

    # Override profit_pnl if specified
    if args.profit_pnl is not None:
        print(f"  Overriding profit_pnl: {strategy.profit_pnl:.2f} -> {args.profit_pnl:.2f}")
        strategy.profit_pnl = args.profit_pnl

    # Override leverage if specified
    if args.leverage is not None:
        print(f"  Overriding leverage: {strategy.leverage}x -> {args.leverage}x")
        strategy.leverage = args.leverage

    # Fetch historical data for all symbols
    df_dict = {}  # {symbol: dataframe}

    timeframe_map = {
        1: '1m', 3: '3m', 5: '5m', 15: '15m', 30: '30m',
        60: '1h', 120: '2h', 240: '4h', 360: '6h', 720: '12h',
        1440: '1d'
    }
    timeframe = timeframe_map.get(args.interval, '1h')

    for symbol in symbols:
        print(f"\n📡 Fetching data for {symbol}...")

        if args.source == 'binance':
            # Use CCXT to fetch from Binance (much more history available)
            binance_symbol = convert_phemex_to_binance_symbol(symbol)

            df = fetch_historical_data_ccxt(
                symbol=binance_symbol,
                timeframe=timeframe,
                days=args.days,
                exchange_name='binance'
            )
        else:
            # Use Phemex API (limited to ~1000 candles)
            periods_needed = (args.days * 24 * 60) // args.interval + 200
            print(f"📊 Requesting {periods_needed} candles ({args.days} days @ {args.interval}min interval)")

            df = fetch_extended_historical_data(client, symbol, args.interval, periods_needed)

        if df.empty:
            print(f"❌ Failed to fetch historical data for {symbol}")
            return

        df_dict[symbol] = df
        print(f"✅ Fetched {len(df)} candles for {symbol}")

    # Display protection status
    if args.max_margin_pct is not None:
        print(f"  Protections: Max Margin: {args.max_margin_pct:.0%}")
    else:
        print(f"  Protections: None (matches real bot)")

    # Run backtest
    if multi_symbol:
        # Multi-symbol mode
        engine = BacktestEngine(client, strategy, args.balance, max_margin_pct=args.max_margin_pct, symbols=symbols)

        # Set configuration settings for display
        engine.config_settings = {
            'Symbols': ', '.join(symbols),
            'Side': args.side,
            'Initial Balance': f"${args.balance:,.2f}",
            'Leverage': f"{strategy.leverage}x",
            'Profit Target': f"{strategy.profit_pnl:.0%}",
            'Max Margin Cap': f"{args.max_margin_pct:.0%}" if args.max_margin_pct else "None",
            'Period': f"{args.days} days",
            'Data Source': args.source.upper()
        }

        # Get instrument specs for each symbol
        for symbol in symbols:
            try:
                min_qty, max_qty, qty_step = client.define_instrument_info(symbol)
                engine.set_instrument_specs(min_qty, max_qty, qty_step, symbol=symbol)
                print(f"📏 {symbol} Specs: min={min_qty}, max={max_qty}, step={qty_step}")
            except Exception as e:
                print(f"⚠️  Could not fetch instrument specs for {symbol}: {e}. Using defaults")

        engine.run_multi_symbol_backtest(
            df_dict=df_dict,
            pos_side=args.side,
            ema_interval=args.interval,
            automatic_mode=True
        )
    else:
        # Single symbol mode (backward compatible)
        engine = BacktestEngine(client, strategy, args.balance, max_margin_pct=args.max_margin_pct)

        # Set configuration settings for display in results
        engine.config_settings = {
            'Symbol': args.symbol,
            'Side': args.side,
            'Initial Balance': f"${args.balance:,.2f}",
            'Leverage': f"{strategy.leverage}x",
            'Profit Target': f"{strategy.profit_pnl:.0%}",
            'Max Margin Cap': f"{args.max_margin_pct:.0%}" if args.max_margin_pct else "None",
            'Period': f"{args.days} days",
            'Data Source': args.source.upper()
        }

        # Get instrument specs for proper quantity rounding (matches real bot!)
        try:
            min_qty, max_qty, qty_step = client.define_instrument_info(args.symbol)
            engine.set_instrument_specs(min_qty, max_qty, qty_step)
            print(f"\n📏 Instrument Specs: min={min_qty}, max={max_qty}, step={qty_step}")
        except Exception as e:
            print(f"⚠️  Could not fetch instrument specs: {e}. Using defaults (min=1.0)")

        df = df_dict[args.symbol]  # Get the dataframe for single symbol

        engine.run_backtest(
            df=df,
            symbol=args.symbol,
            pos_side=args.side,
            ema_interval=args.interval,
            automatic_mode=True
        )


if __name__ == '__main__':
    main()
