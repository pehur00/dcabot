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

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from clients.PhemexClient import PhemexClient
from strategies.MartingaleTradingStrategy import MartingaleTradingStrategy
from backtest.data_fetcher import fetch_historical_data_ccxt, convert_phemex_to_binance_symbol


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

    def execute_trade(self, symbol: str, qty: float, price: float, side: str, pos_side: str):
        """Simulate trade execution"""
        # Calculate fee (0.075% maker fee on Phemex)
        fee = abs(qty * price * 0.00075)
        self.total_fees += fee

        trade = {
            'timestamp': datetime.now(),
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
                df, i  # Pass historical data for volatility analysis
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
            self.execute_trade(
                symbol, self.position_size, current_price,
                'Sell' if pos_side == 'Long' else 'Buy', pos_side
            )

        self._print_results()

    def _manage_position_backtest(self, symbol, current_price, ema_200, ema_50,
                                   position, total_balance, pos_side, automatic_mode,
                                   historical_df, current_idx):
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
                                     'Sell' if pos_side == 'Long' else 'Buy', pos_side)
                    conclusion = "Closed 50% - position > 10%"

                elif position_size_percentage > 7.5:
                    # Close 33%
                    close_qty = position['size'] * 0.33
                    self.execute_trade(symbol, close_qty, current_price,
                                     'Sell' if pos_side == 'Long' else 'Buy', pos_side)
                    conclusion = "Closed 33% - position > 7.5%"

                elif upnl_percentage > self.strategy.profit_pnl:
                    # Close full position
                    self.execute_trade(symbol, position['size'], current_price,
                                     'Sell' if pos_side == 'Long' else 'Buy', pos_side)
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

                self.execute_trade(symbol, qty, current_price, side, pos_side)
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
            self.execute_trade(symbol, qty, current_price, side, pos_side)
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

        # Save detailed results
        backtest_dir = Path(__file__).parent
        if self.balance_history:
            df_results = pd.DataFrame(self.balance_history)
            balance_csv = backtest_dir / 'backtest_balance_history.csv'
            df_results.to_csv(balance_csv, index=False)
            print(f"💾 Balance history saved to: {balance_csv}")

        if self.trades:
            df_trades = pd.DataFrame(self.trades)
            trades_csv = backtest_dir / 'backtest_trade_history.csv'
            df_trades.to_csv(trades_csv, index=False)
            print(f"💾 Trade history saved to: {trades_csv}")


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
