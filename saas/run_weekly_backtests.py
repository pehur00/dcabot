#!/usr/bin/env python3
"""
Weekly Backtest Runner

Runs backtests for all active symbols in backtest_configs table
and stores results in backtest_results and backtest_trades tables.

This script is designed to be run weekly via cron job.

Usage:
    python saas/run_weekly_backtests.py
"""

import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest.backtest import run_backtest_programmatic
from saas.database import get_db


def fetch_global_config() -> Dict[str, Any]:
    """
    Fetch active global backtest configuration.

    Returns:
        Dict with global strategy parameters
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT profit_pnl, profit_threshold, buy_until_limit, max_margin_pct,
                   begin_size_of_balance,
                   close_threshold_high, close_threshold_mid,
                   close_pct_high, close_pct_mid
            FROM global_backtest_config
            WHERE is_active = true
            LIMIT 1
        """)

        row = cursor.fetchone()
        if not row:
            raise ValueError("No active global backtest configuration found")

        return {
            'profit_pnl': float(row[0]),
            'profit_threshold': float(row[1]),
            'buy_until_limit': float(row[2]),
            'max_margin_pct': float(row[3]) if row[3] else None,
            'begin_size_of_balance': float(row[4]),
            'close_threshold_high': float(row[5]),
            'close_threshold_mid': float(row[6]),
            'close_pct_high': float(row[7]),
            'close_pct_mid': float(row[8])
        }


def fetch_active_backtest_symbols() -> List[Dict[str, Any]]:
    """
    Fetch all active symbols from backtest_configs table.

    Returns:
        List of dicts with symbol info (no strategy parameters)
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, symbol, side, leverage, interval, category,
                   days, balance, source
            FROM backtest_configs
            WHERE is_active = true
            ORDER BY category, symbol
        """)

        symbols = []
        for row in cursor.fetchall():
            symbols.append({
                'id': row[0],
                'symbol': row[1],
                'side': row[2],
                'leverage': row[3],
                'interval': row[4],
                'category': row[5],
                'days': row[6],
                'balance': float(row[7]) if row[7] else 200.0,
                'source': row[8]
            })

        return symbols


def store_backtest_result(result: Dict[str, Any], chart_data: bytes = None) -> int:
    """
    Store backtest result in backtest_results table.

    Args:
        result: Dictionary with backtest results
        chart_data: Optional PNG chart image as bytes

    Returns:
        ID of inserted backtest_result row
    """
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO backtest_results (
                symbol, side, leverage, interval, test_period_days,
                start_date, end_date,
                initial_balance, final_balance, profit_loss, profit_loss_pct,
                max_drawdown_pct, total_trades, winning_trades, losing_trades, win_rate,
                max_position_size, max_margin_used_pct, liquidation_occurred,
                execution_duration_seconds, data_source, status,
                chart_balance_path, chart_data
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s
            )
            RETURNING id
        """, (
            result['symbol'], result['side'], result['leverage'], result['interval'],
            result['test_period_days'],
            result['start_date'], result['end_date'],
            result['initial_balance'], result['final_balance'], result['profit_loss'],
            result['profit_loss_pct'],
            result['max_drawdown_pct'], result['total_trades'], result['winning_trades'],
            result['losing_trades'], result['win_rate'],
            result['max_position_size'], result['max_margin_used_pct'],
            result['liquidation_occurred'],
            result['execution_duration_seconds'], result['data_source'], 'completed',
            result.get('chart_path'),
            chart_data
        ))

        backtest_result_id = cursor.fetchone()[0]
        conn.commit()

        return backtest_result_id


def store_backtest_trades(backtest_result_id: int, trades: List[Dict[str, Any]]):
    """
    Store detailed trades for a backtest in backtest_trades table.

    Args:
        backtest_result_id: ID of the backtest_results row
        trades: List of trade dictionaries
    """
    if not trades:
        return

    with get_db() as conn:
        cursor = conn.cursor()

        for idx, trade in enumerate(trades, 1):
            cursor.execute("""
                INSERT INTO backtest_trades (
                    backtest_result_id, trade_number, timestamp,
                    action, side, price, quantity,
                    position_size, balance, pnl, margin_level
                ) VALUES (
                    %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s
                )
            """, (
                backtest_result_id, idx, trade['timestamp'],
                trade.get('action', 'TRADE'), trade['side'], trade['price'], trade['qty'],
                trade.get('position_size'), trade.get('balance'),
                trade.get('pnl'), trade.get('margin_level')
            ))

        conn.commit()


def store_backtest_error(symbol: str, side: str, leverage: int, error_message: str):
    """
    Store failed backtest in backtest_results with error status.

    Args:
        symbol: Trading symbol
        side: Position side
        leverage: Leverage used
        error_message: Error description
    """
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO backtest_results (
                symbol, side, leverage, interval, test_period_days,
                start_date, end_date,
                initial_balance, final_balance, profit_loss, profit_loss_pct,
                status, error_message
            ) VALUES (
                %s, %s, %s, %s, %s,
                NOW(), NOW(),
                0, 0, 0, 0,
                %s, %s
            )
        """, (
            symbol, side, leverage, 1, 7,
            'failed', error_message
        ))

        conn.commit()


def cleanup_old_results():
    """
    Clean up old and failed backtest results to prevent unique constraint violations.
    Keeps successful results from today.
    """
    with get_db() as conn:
        cursor = conn.cursor()

        # Delete failed results
        cursor.execute("DELETE FROM backtest_results WHERE status = 'failed'")
        failed_count = cursor.rowcount

        # Delete old results (older than today, keeping most recent successful run per symbol)
        cursor.execute("""
            DELETE FROM backtest_results
            WHERE id NOT IN (
                SELECT DISTINCT ON (symbol, side, leverage)
                    id
                FROM backtest_results
                WHERE status = 'completed'
                ORDER BY symbol, side, leverage, executed_at DESC
            )
            AND status = 'completed'
            AND executed_at::date < CURRENT_DATE
        """)
        old_count = cursor.rowcount

        conn.commit()

        return failed_count, old_count


def run_weekly_backtests():
    """
    Main function to run weekly backtests for all active symbols using global config.
    """
    print("=" * 80)
    print("🔄 WEEKLY BACKTEST RUNNER")
    print("=" * 80)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Clean up old results
    print("🧹 Cleaning up old backtest results...")
    failed_count, old_count = cleanup_old_results()
    print(f"   Deleted {failed_count} failed results")
    print(f"   Deleted {old_count} old results (keeping latest per symbol)")
    print()

    # Fetch global config (used for all symbols)
    print("⚙️  Loading global backtest configuration...")
    try:
        global_config = fetch_global_config()
        print(f"✅ Loaded global config:")
        print(f"   - Profit target: {global_config['profit_pnl']*100:.1f}%")
        print(f"   - Max margin: {global_config['max_margin_pct']*100:.0f}%" if global_config['max_margin_pct'] else "   - Max margin: None")
        print(f"   - Buy until: {global_config['buy_until_limit']*100:.1f}%")
        print()
    except Exception as e:
        print(f"❌ Failed to load global config: {e}")
        return

    # Fetch active symbols
    print("📋 Fetching active symbols to test...")
    symbols = fetch_active_backtest_symbols()
    print(f"✅ Found {len(symbols)} active symbols\n")

    if not symbols:
        print("⚠️  No active symbols configured. Exiting.")
        return

    # Run backtests
    results_summary = []
    for idx, config in enumerate(symbols, 1):
        symbol = config['symbol']
        side = config['side']
        leverage = config['leverage']
        category = config['category']

        print(f"[{idx}/{len(symbols)}] Testing {symbol} ({side}, {leverage}x, {category})...")

        try:
            # Run backtest with global config parameters
            result = run_backtest_programmatic(
                symbol=symbol,
                side=side,
                days=config.get('days', 7),
                balance=config.get('balance', 200.0),
                leverage=leverage,
                interval=config.get('interval', 1),
                source=config.get('source', 'binance'),
                # Global config parameters (same for all symbols)
                profit_pnl=global_config['profit_pnl'],
                max_margin_pct=global_config['max_margin_pct'],
                profit_threshold=global_config['profit_threshold'],
                buy_until_limit=global_config['buy_until_limit'],
                begin_size_of_balance=global_config['begin_size_of_balance']
            )

            # Read chart file if it was generated
            chart_data = None
            if result.get('chart_path'):
                # Extract actual file path from the chart_path
                # chart_path format: '/static/charts/filename.png'
                try:
                    chart_filename = result['chart_path'].split('/')[-1]
                    chart_file_path = Path(__file__).parent.parent / 'saas' / 'static' / 'charts' / chart_filename

                    if chart_file_path.exists():
                        with open(chart_file_path, 'rb') as f:
                            chart_data = f.read()
                        print(f"   📊 Read chart data ({len(chart_data)} bytes)")
                except Exception as e:
                    print(f"   ⚠️  Failed to read chart file: {e}")

            # Store results with chart data
            backtest_result_id = store_backtest_result(result, chart_data)
            print(f"   ✅ Stored result (ID: {backtest_result_id})")

            # Store trades (optional, can be commented out to save space)
            if 'trades' in result and result['trades']:
                store_backtest_trades(backtest_result_id, result['trades'])
                print(f"   ✅ Stored {len(result['trades'])} trades")

            # Track summary
            results_summary.append({
                'symbol': symbol,
                'profit_loss_pct': result['profit_loss_pct'],
                'total_trades': result['total_trades'],
                'status': 'success'
            })

            print(f"   📊 P&L: {result['profit_loss_pct']:+.2f}% | Trades: {result['total_trades']} | Duration: {result['execution_duration_seconds']}s\n")

        except Exception as e:
            error_msg = str(e)
            print(f"   ❌ Failed: {error_msg}\n")

            # Store error
            store_backtest_error(symbol, side, leverage, error_msg)

            results_summary.append({
                'symbol': symbol,
                'profit_loss_pct': 0,
                'total_trades': 0,
                'status': 'failed'
            })

    # Print summary
    print("=" * 80)
    print("📊 SUMMARY")
    print("=" * 80)

    successful = [r for r in results_summary if r['status'] == 'success']
    failed = [r for r in results_summary if r['status'] == 'failed']

    print(f"\n✅ Successful: {len(successful)}/{len(symbols)}")
    print(f"❌ Failed: {len(failed)}/{len(symbols)}")

    if successful:
        print(f"\n🏆 Top Performers:")
        sorted_results = sorted(successful, key=lambda x: x['profit_loss_pct'], reverse=True)
        for result in sorted_results[:5]:
            print(f"   {result['symbol']}: {result['profit_loss_pct']:+.2f}% ({result['total_trades']} trades)")

    if failed:
        print(f"\n⚠️  Failed Backtests:")
        for result in failed:
            print(f"   {result['symbol']}")

    print(f"\n✅ Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)


if __name__ == '__main__':
    run_weekly_backtests()
