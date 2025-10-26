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
import pandas as pd
from dotenv import load_dotenv
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

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
                 initial_balance: float = 10000.0):
        self.client = client
        self.strategy = strategy
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.peak_balance = initial_balance

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
        self.max_drawdown = 0
        self.total_fees = 0

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
        upnl_percentage = (self.unrealized_pnl / self.position_value) if self.position_value > 0 else 0

        # Calculate margin level (simplified)
        used_margin = self.position_value / self.strategy.leverage
        if used_margin > 0:
            margin_level = (self.balance - self.unrealized_pnl) / used_margin
        else:
            margin_level = 999

        return {
            'symbol': self.position['symbol'],
            'pos_side': self.position['pos_side'],
            'size': self.position_size,
            'positionValue': self.position_value,
            'unrealisedPnl': self.unrealized_pnl,
            'upnlPercentage': upnl_percentage,
            'position_size_percentage': (self.position_value / self.balance) * 100,
            'margin_level': margin_level,
            'entry_price': self.position_entry_price
        }

    def execute_trade(self, symbol: str, qty: float, price: float, side: str, pos_side: str, timestamp=None):
        """Simulate trade execution"""
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

        elif side == 'Buy' if pos_side == 'Long' else 'Sell':
            # Add to position (average down)
            total_value = (self.position_size * self.position_entry_price) + (qty * price)
            self.position_size += qty
            self.position_entry_price = total_value / self.position_size
            self.position_value = self.position_size * price
            trade['action'] = 'ADD'

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

            trade['realized_pnl'] = realized_pnl

        self.trades.append(trade)

        # Update peak and calculate drawdown
        if self.balance > self.peak_balance:
            self.peak_balance = self.balance

        drawdown = ((self.peak_balance - self.balance) / self.peak_balance) * 100
        if drawdown > self.max_drawdown:
            self.max_drawdown = drawdown

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

        # Need at least 200 periods for EMA200
        if len(df) < 200:
            print("❌ Insufficient data for EMA200 calculation (need 200+ periods)")
            return

        # Run simulation
        for i in range(200, len(df)):
            current_candle = df.iloc[i]
            timestamp = current_candle.name
            current_price = float(current_candle['close'])
            ema_50 = float(current_candle['ema_50'])
            ema_200 = float(current_candle['ema_200'])

            # Simulate position
            simulated_position = self.simulate_position(current_price)

            # Check if position management is valid
            valid_position = self.strategy.is_valid_position(
                simulated_position, current_price, ema_200, pos_side
            )

            # Store price data for charting
            self.price_history.append({
                'timestamp': timestamp,
                'price': current_price,
                'ema_50': ema_50,
                'ema_200': ema_200
            })

            if not valid_position:
                # Record balance snapshot
                self.balance_history.append({
                    'timestamp': timestamp,
                    'balance': self.balance,
                    'position_value': self.position_value,
                    'unrealized_pnl': self.unrealized_pnl,
                    'total_value': self.balance + self.unrealized_pnl
                })
                continue

            # Get strategy decision WITH FULL VOLATILITY PROTECTION
            conclusion = self._manage_position_backtest(
                symbol, current_price, ema_200, ema_50,
                simulated_position, self.balance, pos_side, automatic_mode,
                df, i, timestamp  # Pass historical data and timestamp
            )

            # Record balance snapshot
            self.balance_history.append({
                'timestamp': timestamp,
                'balance': self.balance,
                'position_value': self.position_value,
                'unrealized_pnl': self.unrealized_pnl,
                'total_value': self.balance + self.unrealized_pnl,
                'action': conclusion
            })

        # Close any open position at end
        if self.position:
            print(f"\n📊 Closing remaining position at end of backtest")
            final_timestamp = df.index[-1]
            self.execute_trade(
                symbol, self.position_size, current_price,
                'Sell' if pos_side == 'Long' else 'Buy', pos_side, final_timestamp
            )

        self._print_results()
        self.generate_charts(symbol, pos_side)

    def _manage_position_backtest(self, symbol, current_price, ema_200, ema_50,
                                   position, total_balance, pos_side, automatic_mode,
                                   historical_df, current_idx, timestamp):
        """
        Full position management for backtesting with volatility protection.

        Simulates check_volatility() and decline_velocity using historical data.
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

                self.execute_trade(symbol, qty, current_price, side, pos_side, timestamp)
                conclusion = "Added to position"

            elif is_dangerous_decline:
                conclusion = f"Skipped add - dangerous decline ({decline_type}, score: {velocity_score:.0f})"

            elif is_high_volatility:
                conclusion = f"Skipped add - high volatility ({vol_metrics.get('trigger', 'unknown')})"

        # Open new position if automatic mode (WITH PROTECTIONS)
        elif automatic_mode and not is_high_volatility and not is_dangerous_decline and (
            (pos_side == "Long" and current_price > ema_200) or
            (pos_side == "Short" and current_price < ema_200)
        ):
            side = "Buy" if pos_side == "Long" else "Sell"
            qty = (total_balance * self.strategy.proportion_of_balance) * self.strategy.leverage / current_price
            self.execute_trade(symbol, qty, current_price, side, pos_side, timestamp)
            conclusion = "Opened new position"

        elif automatic_mode and is_dangerous_decline:
            conclusion = f"Skipped open - dangerous decline ({decline_type})"

        elif automatic_mode and is_high_volatility:
            conclusion = f"Skipped open - high volatility"

        return conclusion

    def _print_results(self):
        """Print backtest results"""
        final_balance = self.balance
        total_return = ((final_balance - self.initial_balance) / self.initial_balance) * 100
        win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0

        print("\n" + "=" * 80)
        print("📊 BACKTEST RESULTS")
        print("=" * 80)

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
        print(f"  Max Drawdown:     {self.max_drawdown:.2f}%")
        print(f"  Peak Balance:     ${self.peak_balance:,.2f}")

        if self.trades:
            print(f"\n📋 Trade History (Last 10):")
            print("-" * 80)
            for trade in self.trades[-10:]:
                action = trade.get('action', 'TRADE')
                pnl_str = ""
                if 'realized_pnl' in trade:
                    pnl = trade['realized_pnl']
                    pnl_str = f" | PnL: ${pnl:+,.2f}"

                print(f"  {action:6} | {trade['side']:4} {trade['qty']:.4f} @ ${trade['price']:.6f}{pnl_str}")

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

        # Create figure with subplots (4 panels now)
        fig, axes = plt.subplots(4, 1, figsize=(14, 16))
        fig.suptitle(f'Backtest Results: {symbol} ({pos_side})', fontsize=16, fontweight='bold')

        # Get price data
        price_df = pd.DataFrame(self.price_history)
        price_df['timestamp'] = pd.to_datetime(price_df['timestamp'])

        # 1. Price Chart with EMAs
        ax1 = axes[0]
        ax1.plot(price_df['timestamp'], price_df['price'], label='Price', color='#333333', linewidth=2)
        ax1.plot(price_df['timestamp'], price_df['ema_200'], label='EMA200', color='#FF6B35', linewidth=1.5, linestyle='--')
        ax1.plot(price_df['timestamp'], price_df['ema_50'], label='EMA50', color='#004E89', linewidth=1.5, linestyle='-.')

        ax1.set_xlabel('Date')
        ax1.set_ylabel('Price (USDT)')
        ax1.set_title('Price Action & EMAs')
        ax1.legend(loc='best')
        ax1.grid(True, alpha=0.3)
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))

        # 2. Balance History Chart
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

                    # Plot markers on price chart (no label)
                    ax1.scatter(action_trades['timestamp'], trade_prices,
                              color=color, marker=marker, s=200, alpha=1.0,
                              edgecolors='black', linewidths=2.5, zorder=10)

                    # Plot markers on balance chart (with label)
                    ax2.scatter(action_trades['timestamp'], trade_balances,
                              color=color, marker=marker, s=200, alpha=1.0,
                              edgecolors='black', linewidths=2.5,
                              label=f'{action} ({len(action_trades)})', zorder=10)

        ax2.set_xlabel('Date')
        ax2.set_ylabel('Balance (USDT)')
        ax2.set_title('Balance History Over Time')
        ax2.legend(loc='best')
        ax2.grid(True, alpha=0.3)
        ax2.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))

        # 3. Drawdown Chart (based on total value including unrealized PnL)
        ax3 = axes[2]
        df['peak'] = df['total_value'].expanding().max()
        df['drawdown'] = ((df['peak'] - df['total_value']) / df['peak']) * 100

        ax3.fill_between(df['timestamp'], 0, df['drawdown'], color='#C73E1D', alpha=0.3)
        ax3.plot(df['timestamp'], df['drawdown'], color='#C73E1D', linewidth=2)
        ax3.axhline(y=self.max_drawdown, color='darkred', linestyle='--',
                   label=f'Max Drawdown: {self.max_drawdown:.2f}%')

        ax3.set_xlabel('Date')
        ax3.set_ylabel('Drawdown (%)')
        ax3.set_title('Drawdown Analysis')
        ax3.legend(loc='best')
        ax3.grid(True, alpha=0.3)
        ax3.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
        ax3.invert_yaxis()  # Drawdown goes down

        # 4. Performance Metrics Summary
        ax4 = axes[3]
        ax4.axis('off')

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

        Max Drawdown:           {self.max_drawdown:.2f}%
        Peak Balance:           ${self.peak_balance:,.2f}
        """

        ax4.text(0.1, 0.5, summary_text, transform=ax4.transAxes,
                fontsize=12, verticalalignment='center', family='monospace',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))

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

    # Run backtest
    engine = BacktestEngine(client, strategy, args.balance)
    engine.run_backtest(
        df=df,
        symbol=args.symbol,
        pos_side=args.side,
        ema_interval=args.interval,
        automatic_mode=True
    )


if __name__ == '__main__':
    main()
