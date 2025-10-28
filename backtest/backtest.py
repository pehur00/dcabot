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
                 initial_balance: float = 10000.0, max_margin_pct: float = None):
        self.client = client
        self.strategy = strategy
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.peak_balance = initial_balance
        self.max_margin_pct = max_margin_pct  # Optional margin cap

        # Position tracking
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

        # Instrument specs for minimum quantity rounding
        self.min_qty = 1.0
        self.max_qty = 1000000.0
        self.qty_step = 1.0

        # Configuration settings (for display in results)
        self.config_settings = {}

    def set_instrument_specs(self, min_qty: float, max_qty: float, qty_step: float):
        """Set instrument specifications for quantity rounding"""
        self.min_qty = min_qty
        self.max_qty = max_qty
        self.qty_step = qty_step

    def custom_round(self, number: float) -> float:
        """Round quantity to meet exchange requirements (same logic as real bot)"""
        number = Decimal(str(number))
        min_qty = Decimal(str(self.min_qty))
        max_qty = Decimal(str(self.max_qty))
        qty_step = Decimal(str(self.qty_step))

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

    def execute_trade(self, symbol: str, qty: float, price: float, side: str, pos_side: str, timestamp=None):
        """Simulate trade execution with exchange-side validations"""
        # Calculate required margin for this trade
        trade_notional = qty * price
        required_margin = trade_notional / self.strategy.leverage

        # === USER-CONFIGURED PROTECTIONS (optional) ===
        # ONLY apply max_margin_pct if explicitly set (optional protection)
        if side in ['Buy', 'Sell'] and (side == 'Buy' if pos_side == 'Long' else side == 'Sell'):
            if self.max_margin_pct is not None:
                # This is opening or adding to position - check margin cap
                current_used_margin = (self.position_value / self.strategy.leverage) if self.position else 0
                total_required_margin = current_used_margin + required_margin
                margin_usage = total_required_margin / self.balance

                if margin_usage > self.max_margin_pct:
                    return  # Skip this trade

        # === EXCHANGE-SIDE VALIDATIONS (always enforced) ===
        if side in ['Buy', 'Sell'] and (side == 'Buy' if pos_side == 'Long' else side == 'Sell'):
            # Calculate current used margin
            current_used_margin = (self.position_value / self.strategy.leverage) if self.position else 0

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

        if not self.position:
            # Open new position
            self.position = {
                'symbol': symbol,
                'pos_side': pos_side
            }
            self.position_size = qty
            self.position_entry_price = price
            self.position_value = qty * price
            trade['action'] = 'OPEN'
            trade['position_size'] = self.position_size
            trade['position_value'] = self.position_value

        elif side == 'Buy' if pos_side == 'Long' else 'Sell':
            # Add to position (average down)
            total_value = (self.position_size * self.position_entry_price) + (qty * price)
            self.position_size += qty
            self.position_entry_price = total_value / self.position_size
            self.position_value = self.position_size * price
            trade['action'] = 'ADD'
            trade['position_size'] = self.position_size
            trade['position_value'] = self.position_value

        else:
            # Close position (partial or full)
            realized_pnl = 0
            if pos_side == 'Long':
                realized_pnl = (price - self.position_entry_price) * qty
            else:
                realized_pnl = (self.position_entry_price - price) * qty

            self.balance += realized_pnl - fee
            self.position_size -= qty

            if self.position_size <= 0:
                # Fully closed
                self.position = None
                self.position_size = 0
                self.position_entry_price = 0
                self.position_value = 0
                self.unrealized_pnl = 0
                trade['action'] = 'CLOSE'
                trade['position_size'] = 0
                trade['position_value'] = 0

                # Track win/loss
                self.total_trades += 1
                if realized_pnl > 0:
                    self.winning_trades += 1
                else:
                    self.losing_trades += 1
            else:
                # Partially closed
                self.position_value = self.position_size * price
                trade['action'] = 'REDUCE'
                trade['position_size'] = self.position_size
                trade['position_value'] = self.position_value

            trade['realized_pnl'] = realized_pnl

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
        df_1h = df.resample('1H').agg({'close': 'last', 'high': 'max', 'low': 'min', 'open': 'first', 'volume': 'sum'})
        df_1h['ema_100_1h'] = df_1h['close'].ewm(span=100, adjust=False).mean()

        # Forward-fill 1h EMA100 to 1-minute timeframe
        df = df.join(df_1h[['ema_100_1h']], how='left')
        df['ema_100_1h'] = df['ema_100_1h'].fillna(method='ffill')

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


def main():
    parser = argparse.ArgumentParser(description='Backtest DCABot Martingale Strategy')
    parser.add_argument('--symbol', type=str, default='u1000PEPEUSDT',
                       help='Trading symbol (default: u1000PEPEUSDT)')
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

    args = parser.parse_args()

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
    print(f"  Symbol: {args.symbol}")
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

    # Fetch historical data
    if args.source == 'binance':
        # Use CCXT to fetch from Binance (much more history available)
        binance_symbol = convert_phemex_to_binance_symbol(args.symbol)

        # Convert interval minutes to timeframe string
        timeframe_map = {
            1: '1m', 3: '3m', 5: '5m', 15: '15m', 30: '30m',
            60: '1h', 120: '2h', 240: '4h', 360: '6h', 720: '12h',
            1440: '1d'
        }
        timeframe = timeframe_map.get(args.interval, '1h')

        df = fetch_historical_data_ccxt(
            symbol=binance_symbol,
            timeframe=timeframe,
            days=args.days,
            exchange_name='binance'
        )
    else:
        # Use Phemex API (limited to ~1000 candles)
        print(f"\n📡 Fetching historical data from Phemex...")
        periods_needed = (args.days * 24 * 60) // args.interval + 200

        print(f"📊 Requesting {periods_needed} candles ({args.days} days @ {args.interval}min interval)")

        df = fetch_extended_historical_data(client, args.symbol, args.interval, periods_needed)

    if df.empty:
        print(f"❌ Failed to fetch historical data for {args.symbol}")
        return

    # Display protection status
    if args.max_margin_pct is not None:
        print(f"  Protections: Max Margin: {args.max_margin_pct:.0%}")
    else:
        print(f"  Protections: None (matches real bot)")

    # Run backtest
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

    engine.run_backtest(
        df=df,
        symbol=args.symbol,
        pos_side=args.side,
        ema_interval=args.interval,
        automatic_mode=True
    )


if __name__ == '__main__':
    main()
