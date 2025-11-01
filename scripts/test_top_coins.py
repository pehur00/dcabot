#!/usr/bin/env python3
"""
Backtest top volume coins with configurable leverage and time period.

Usage:
    python test_top_coins.py --leverage 10 --days 30 --balance 200
"""

import os
import sys
import argparse
import subprocess
from pathlib import Path
from datetime import datetime
import ccxt

def get_top_volume_coins(exchange_name='binance', num_coins=10, quote_currency='USDT'):
    """
    Fetch top volume trading pairs from exchange.

    Args:
        exchange_name: Exchange to query (default: binance)
        num_coins: Number of top coins to return (default: 10)
        quote_currency: Quote currency for pairs (default: USDT)

    Returns:
        List of symbol strings (e.g., ['BTCUSDT', 'ETHUSDT', ...])
    """
    print(f"📊 Fetching top {num_coins} volume coins from {exchange_name.upper()}...")

    try:
        exchange = ccxt.binance()

        # Fetch all tickers
        tickers = exchange.fetch_tickers()

        # Filter for USDT pairs and perpetual futures
        usdt_pairs = []

        # Fiat and stablecoin currencies to exclude (we only want volatile crypto/USDT pairs)
        excluded_bases = [
            # Fiat pairs
            'IDR', 'BIDR', 'ARS', 'TRY', 'COP', 'UAH', 'BRL', 'EUR', 'GBP', 'AUD', 'RUB', 'NGN', 'PLN', 'RON', 'ZAR',
            # Stablecoins
            'USDC', 'BUSD', 'DAI', 'TUSD', 'FDUSD', 'USDP', 'GUSD'
        ]

        for symbol, ticker in tickers.items():
            # Only include USDT pairs
            if f'/{quote_currency}' in symbol:
                base_currency = symbol.split('/')[0]

                # Skip USDT itself
                if base_currency == quote_currency:
                    continue

                # Skip excluded bases (fiat and stablecoins)
                if base_currency in excluded_bases:
                    continue

                # Skip leveraged tokens and special pairs
                if any(x in base_currency for x in ['UP', 'DOWN', 'BULL', 'BEAR', '2S', '3S', '2L', '3L', 'USDT']):
                    continue

                if ticker.get('quoteVolume'):
                    usdt_pairs.append({
                        'symbol': symbol.replace('/', ''),  # Convert BTC/USDT to BTCUSDT
                        'volume': float(ticker['quoteVolume'])
                    })

        # Sort by volume (descending) and get top N
        sorted_pairs = sorted(usdt_pairs, key=lambda x: x['volume'], reverse=True)
        top_coins = [pair['symbol'] for pair in sorted_pairs[:num_coins]]

        print(f"✅ Top {num_coins} coins by volume:")
        for i, symbol in enumerate(top_coins, 1):
            volume = next(p['volume'] for p in sorted_pairs if p['symbol'] == symbol)
            print(f"   {i:2d}. {symbol:15s} (${volume:,.0f} 24h volume)")

        return top_coins

    except Exception as e:
        print(f"❌ Error fetching top coins: {e}")
        # Fallback to common coins
        fallback = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT',
                    'ADAUSDT', 'DOGEUSDT', 'TRXUSDT', 'AVAXUSDT', 'LINKUSDT']
        print(f"⚠️  Using fallback list: {', '.join(fallback[:num_coins])}")
        return fallback[:num_coins]


def run_backtest(symbol, days, balance, leverage, side='Long', max_margin_pct=0.50):
    """
    Run a single backtest for a symbol.

    Returns:
        Tuple of (success: bool, result_files: dict)
    """
    print(f"\n{'='*60}")
    print(f"🔄 Testing: {symbol} ({leverage}x leverage, {days} days)")
    print(f"{'='*60}")

    try:
        # Run backtest
        cmd = [
            'dcabot-env/bin/python', 'backtest/backtest.py',
            '--symbol', symbol,
            '--days', str(days),
            '--balance', str(balance),
            '--side', side,
            '--leverage', str(leverage),
            '--max-margin-pct', str(max_margin_pct),
            '--interval', '1',
            '--source', 'binance'
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"❌ Backtest failed for {symbol}")
            print(f"Error: {result.stderr}")
            return False, {}

        # Find the latest result files
        results_dir = Path('backtest/results')

        # Get the most recent files for this symbol
        pattern_base = f"{symbol}_{side}_bal{int(balance)}_profit0.10_"

        chart_files = sorted(results_dir.glob(f"{pattern_base}*_chart.png"), key=lambda x: x.stat().st_mtime, reverse=True)
        balance_files = sorted(results_dir.glob(f"{pattern_base}*_balance.csv"), key=lambda x: x.stat().st_mtime, reverse=True)
        trades_files = sorted(results_dir.glob(f"{pattern_base}*_trades.csv"), key=lambda x: x.stat().st_mtime, reverse=True)

        result_files = {}
        if chart_files:
            result_files['chart'] = chart_files[0]
        if balance_files:
            result_files['balance'] = balance_files[0]
        if trades_files:
            result_files['trades'] = trades_files[0]

        # Rename files to include leverage and days
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        new_pattern = f"{symbol}_lev{leverage}x_{days}d_{timestamp}"

        renamed_files = {}
        if 'chart' in result_files:
            new_chart = results_dir / f"{new_pattern}_chart.png"
            result_files['chart'].rename(new_chart)
            renamed_files['chart'] = new_chart

        if 'balance' in result_files:
            new_balance = results_dir / f"{new_pattern}_balance.csv"
            result_files['balance'].rename(new_balance)
            renamed_files['balance'] = new_balance

        if 'trades' in result_files:
            new_trades = results_dir / f"{new_pattern}_trades.csv"
            result_files['trades'].rename(new_trades)
            renamed_files['trades'] = new_trades

        print(f"✅ Completed: {symbol}")
        return True, renamed_files

    except Exception as e:
        print(f"❌ Error testing {symbol}: {e}")
        return False, {}


def create_summary_report(results, output_dir):
    """
    Create a summary CSV of all backtest results.
    """
    import csv
    import pandas as pd

    summary_file = output_dir / f"summary_lev{results[0]['leverage']}x_{results[0]['days']}d_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    print(f"\n📝 Creating summary report: {summary_file.name}")

    summary_data = []

    for result in results:
        if result['success'] and 'balance' in result['files']:
            try:
                # Read the balance CSV to get final balance
                df = pd.read_csv(result['files']['balance'])

                initial_balance = df['balance'].iloc[0] if len(df) > 0 else 0
                final_balance = df['balance'].iloc[-1] if len(df) > 0 else 0
                total_return_pct = ((final_balance - initial_balance) / initial_balance * 100) if initial_balance > 0 else 0

                # Try to read trades CSV for more details
                trades_file = result['files'].get('trades')
                num_trades = 0
                if trades_file and trades_file.exists():
                    trades_df = pd.read_csv(trades_file)
                    num_trades = len(trades_df)

                summary_data.append({
                    'Symbol': result['symbol'],
                    'Leverage': result['leverage'],
                    'Days': result['days'],
                    'Initial Balance': f"${initial_balance:.2f}",
                    'Final Balance': f"${final_balance:.2f}",
                    'Return %': f"{total_return_pct:+.2f}%",
                    'Total Trades': num_trades,
                    'Status': 'Success'
                })
            except Exception as e:
                summary_data.append({
                    'Symbol': result['symbol'],
                    'Leverage': result['leverage'],
                    'Days': result['days'],
                    'Initial Balance': 'N/A',
                    'Final Balance': 'N/A',
                    'Return %': 'N/A',
                    'Total Trades': 'N/A',
                    'Status': f'Error: {str(e)[:50]}'
                })
        else:
            summary_data.append({
                'Symbol': result['symbol'],
                'Leverage': result['leverage'],
                'Days': result['days'],
                'Initial Balance': 'N/A',
                'Final Balance': 'N/A',
                'Return %': 'N/A',
                'Total Trades': 'N/A',
                'Status': 'Failed'
            })

    # Write summary CSV
    with open(summary_file, 'w', newline='') as f:
        if summary_data:
            writer = csv.DictWriter(f, fieldnames=summary_data[0].keys())
            writer.writeheader()
            writer.writerows(summary_data)

    # Print summary table
    print("\n" + "="*80)
    print("📊 BACKTEST SUMMARY")
    print("="*80)
    print(f"{'Symbol':<15} {'Leverage':<10} {'Days':<8} {'Return %':<12} {'Trades':<10} {'Status':<15}")
    print("-"*80)
    for row in summary_data:
        print(f"{row['Symbol']:<15} {str(row['Leverage']) + 'x':<10} {row['Days']:<8} {row['Return %']:<12} {row['Total Trades']:<10} {row['Status']:<15}")
    print("="*80)

    return summary_file


def main():
    parser = argparse.ArgumentParser(
        description='Backtest top volume coins with configurable parameters',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test top 10 coins with 10x leverage over 30 days
  python test_top_coins.py --leverage 10 --days 30 --balance 200

  # Test top 5 coins with 5x leverage over 60 days
  python test_top_coins.py --leverage 5 --days 60 --balance 500 --num-coins 5

  # Test specific coins
  python test_top_coins.py --leverage 10 --days 30 --coins BTCUSDT ETHUSDT SOLUSDT
        """
    )

    parser.add_argument('--leverage', type=int, default=10,
                       help='Leverage to use (default: 10)')
    parser.add_argument('--days', type=int, default=30,
                       help='Number of days to backtest (default: 30)')
    parser.add_argument('--balance', type=float, default=200.0,
                       help='Initial balance in USDT (default: 200)')
    parser.add_argument('--num-coins', type=int, default=10,
                       help='Number of top volume coins to test (default: 10)')
    parser.add_argument('--coins', nargs='+', default=None,
                       help='Specific coins to test (overrides --num-coins)')
    parser.add_argument('--side', type=str, default='Long', choices=['Long', 'Short'],
                       help='Position side (default: Long)')
    parser.add_argument('--max-margin-pct', type=float, default=0.50,
                       help='Maximum margin percentage (default: 0.50 = 50%%)')

    args = parser.parse_args()

    print("\n" + "="*80)
    print("🚀 TOP COINS BACKTEST RUNNER")
    print("="*80)
    print(f"Leverage: {args.leverage}x")
    print(f"Period: {args.days} days")
    print(f"Initial Balance: ${args.balance:.2f}")
    print(f"Max Margin: {args.max_margin_pct:.0%}")
    print(f"Side: {args.side}")
    print("="*80 + "\n")

    # Get coins to test
    if args.coins:
        # Use user-specified coins
        coins = args.coins
        print(f"📋 Testing {len(coins)} user-specified coins: {', '.join(coins)}\n")
    else:
        # Fetch top volume coins
        coins = get_top_volume_coins(num_coins=args.num_coins)

    # Create results directory if it doesn't exist
    results_dir = Path('backtest/results')
    results_dir.mkdir(parents=True, exist_ok=True)

    # Run backtests
    results = []
    successful = 0
    failed = 0

    for i, symbol in enumerate(coins, 1):
        print(f"\n[{i}/{len(coins)}] Processing {symbol}...")

        success, files = run_backtest(
            symbol=symbol,
            days=args.days,
            balance=args.balance,
            leverage=args.leverage,
            side=args.side,
            max_margin_pct=args.max_margin_pct
        )

        results.append({
            'symbol': symbol,
            'leverage': args.leverage,
            'days': args.days,
            'balance': args.balance,
            'success': success,
            'files': files
        })

        if success:
            successful += 1
        else:
            failed += 1

    # Create summary report
    summary_file = create_summary_report(results, results_dir)

    print(f"\n✅ Summary saved to: {summary_file}")
    print(f"📁 All results saved to: {results_dir}/")
    print(f"\n🎯 Results: {successful} successful, {failed} failed out of {len(coins)} total")
    print("\n" + "="*80 + "\n")


if __name__ == '__main__':
    main()
