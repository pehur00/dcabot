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


def fetch_active_backtest_configs() -> List[Dict[str, Any]]:
    """
    Fetch all active symbols from backtest_configs table.

    Returns:
        List of dicts with symbol configuration including strategy parameters
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, symbol, side, leverage, interval, category,
                   days, balance, source,
                   profit_pnl, max_margin_pct, profit_threshold,
                   buy_until_limit, close_threshold_high, close_threshold_mid,
                   close_pct_high, close_pct_mid
            FROM backtest_configs
            WHERE is_active = true
            ORDER BY category, symbol
        """)

        configs = []
        for row in cursor.fetchall():
            configs.append({
                'id': row[0],
                'symbol': row[1],
                'side': row[2],
                'leverage': row[3],
                'interval': row[4],
                'category': row[5],
                'days': row[6],
                'balance': float(row[7]) if row[7] else 200.0,
                'source': row[8],
                'profit_pnl': float(row[9]) if row[9] else 0.1,
                'max_margin_pct': float(row[10]) if row[10] else None,
                'profit_threshold': float(row[11]) if row[11] else 0.003,
                'buy_until_limit': float(row[12]) if row[12] else 0.02,
                'close_threshold_high': float(row[13]) if row[13] else 10.0,
                'close_threshold_mid': float(row[14]) if row[14] else 7.5,
                'close_pct_high': float(row[15]) if row[15] else 0.5,
                'close_pct_mid': float(row[16]) if row[16] else 0.33
            })

        return configs


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


def run_weekly_backtests():
    """
    Main function to run weekly backtests for all active symbols.
    """
    print("=" * 80)
    print("🔄 WEEKLY BACKTEST RUNNER")
    print("=" * 80)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Fetch active configurations
    print("📋 Fetching active backtest configurations...")
    configs = fetch_active_backtest_configs()
    print(f"✅ Found {len(configs)} active symbols to test\n")

    if not configs:
        print("⚠️  No active symbols configured. Exiting.")
        return

    # Run backtests
    results_summary = []
    for idx, config in enumerate(configs, 1):
        symbol = config['symbol']
        side = config['side']
        leverage = config['leverage']
        category = config['category']

        print(f"[{idx}/{len(configs)}] Testing {symbol} ({side}, {leverage}x, {category})...")

        try:
            # Run backtest with configured parameters
            result = run_backtest_programmatic(
                symbol=symbol,
                side=side,
                days=config.get('days', 7),
                balance=config.get('balance', 200.0),
                leverage=leverage,
                interval=config.get('interval', 1),
                source=config.get('source', 'binance'),
                profit_pnl=config.get('profit_pnl', 0.1),
                max_margin_pct=config.get('max_margin_pct'),
                profit_threshold=config.get('profit_threshold', 0.003),
                buy_until_limit=config.get('buy_until_limit', 0.02)
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

    print(f"\n✅ Successful: {len(successful)}/{len(configs)}")
    print(f"❌ Failed: {len(failed)}/{len(configs)}")

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
