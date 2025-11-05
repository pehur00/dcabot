#!/usr/bin/env python3
"""
Insert dummy data for testing timezone functionality
Creates a bot with activity logs, trades, and metrics for oudejans@gmail.com
"""
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from saas.database import get_db
from saas.security import encrypt_api_key

# Database connection details
os.environ['DATABASE_URL'] = 'postgresql://dcabot:dcabot_dev_password@localhost:5435/dcabot_dev'

# Phemex testnet credentials from project context
API_KEY = "540fcfd6-0310-47eb-a0a6-29ef4dcad4f9"
API_SECRET = "test_secret_key_for_dummy_data"
ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY', 'test-encryption-key-32-bytes-long!')

def main():
    print("🔧 Creating dummy data for oudejans@gmail.com...")

    with get_db() as conn:
        cursor = conn.cursor()

        # Get user ID
        cursor.execute("SELECT id FROM users WHERE email = %s", ('oudejans@gmail.com',))
        user = cursor.fetchone()
        if not user:
            print("❌ User oudejans@gmail.com not found!")
            return

        user_id = user[0]
        print(f"✅ Found user ID: {user_id}")

        # Encrypt API credentials
        encrypted_key = encrypt_api_key(API_KEY)
        encrypted_secret = encrypt_api_key(API_SECRET)
        print("✅ Encrypted API credentials")

        # Create bot
        cursor.execute("""
            INSERT INTO bots (user_id, name, exchange, testnet, api_key_encrypted, api_secret_encrypted, status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            user_id,
            'Test BTC/ETH Bot',
            'phemex',
            True,  # testnet
            encrypted_key,
            encrypted_secret,
            'running',
            datetime.utcnow() - timedelta(days=3)
        ))
        bot_id = cursor.fetchone()[0]
        print(f"✅ Created bot ID: {bot_id}")

        # Create trading pairs
        trading_pairs = [
            ('BTCUSDT', 'Long', 10, 1, True),
            ('ETHUSDT', 'Long', 10, 1, True),
        ]

        pair_ids = []
        for symbol, side, leverage, ema_interval, automatic_mode in trading_pairs:
            cursor.execute("""
                INSERT INTO trading_pairs (bot_id, symbol, side, leverage, ema_interval, automatic_mode, is_active, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                bot_id,
                symbol,
                side,
                leverage,
                ema_interval,
                automatic_mode,
                True,
                datetime.utcnow() - timedelta(days=3)
            ))
            pair_id = cursor.fetchone()[0]
            pair_ids.append((pair_id, symbol))
            print(f"✅ Created trading pair: {symbol} (ID: {pair_id})")

        # Create bot logs with various timestamps (last 3 days)
        now = datetime.utcnow()
        log_entries = [
            # 3 days ago - Bot started
            (now - timedelta(days=3, hours=2), 'INFO', 'Bot started successfully'),
            (now - timedelta(days=3, hours=1), 'INFO', 'Position opened for BTCUSDT at $42,500'),

            # 2 days ago - Various activities
            (now - timedelta(days=2, hours=14), 'INFO', 'Holding position - waiting for better entry (4.2% from target)'),
            (now - timedelta(days=2, hours=8), 'WARNING', 'High volatility detected - monitoring closely'),
            (now - timedelta(days=2, hours=6), 'INFO', 'Added to position - Average entry improved to $42,200'),

            # Yesterday - Morning activity
            (now - timedelta(days=1, hours=22), 'INFO', 'Position opened for ETHUSDT at $2,250'),
            (now - timedelta(days=1, hours=18), 'INFO', 'Holding position - position in profit (+2.1%)'),
            (now - timedelta(days=1, hours=12), 'ERROR', 'API rate limit reached - retrying in 60s'),
            (now - timedelta(days=1, hours=10), 'INFO', 'Successfully added to BTCUSDT position'),

            # Today - Recent activity
            (now - timedelta(hours=6), 'INFO', 'Holding position - waiting for dip (price above EMA100)'),
            (now - timedelta(hours=4), 'WARNING', 'Margin level at 3.2x - monitoring position'),
            (now - timedelta(hours=2), 'INFO', 'Decline velocity: MODERATE - safe to continue'),
            (now - timedelta(hours=1), 'INFO', 'Position updated - Current PnL: +$12.50 (+0.8%)'),
            (now - timedelta(minutes=30), 'INFO', 'Execution completed in 245ms'),
            (now - timedelta(minutes=5), 'INFO', 'All positions evaluated - no action needed'),
        ]

        for timestamp, level, message in log_entries:
            cursor.execute("""
                INSERT INTO bot_logs (bot_id, level, message, created_at)
                VALUES (%s, %s, %s, %s)
            """, (bot_id, level, message, timestamp))

        print(f"✅ Created {len(log_entries)} bot log entries")

        # Create some trades
        trades = [
            # 3 days ago - Initial entries
            (now - timedelta(days=3, hours=1), 'BTCUSDT', 'BUY', 'Long', 0.005, 42500.00, None, 200.00),
            (now - timedelta(days=2, hours=23), 'ETHUSDT', 'BUY', 'Long', 0.1, 2250.00, None, 198.50),

            # 2 days ago - Add to positions
            (now - timedelta(days=2, hours=6), 'BTCUSDT', 'BUY', 'Long', 0.008, 42200.00, None, 195.20),
            (now - timedelta(days=2, hours=4), 'ETHUSDT', 'BUY', 'Long', 0.15, 2240.00, None, 192.80),

            # Yesterday - Some closes with profit
            (now - timedelta(days=1, hours=16), 'BTCUSDT', 'SELL', 'Long', 0.003, 42800.00, 8.50, 201.30),
            (now - timedelta(days=1, hours=12), 'ETHUSDT', 'SELL', 'Long', 0.08, 2270.00, 4.20, 205.50),

            # Today - Recent trades
            (now - timedelta(hours=8), 'BTCUSDT', 'BUY', 'Long', 0.004, 42350.00, None, 203.50),
            (now - timedelta(hours=3), 'ETHUSDT', 'BUY', 'Long', 0.12, 2255.00, None, 201.80),
        ]

        for timestamp, symbol, action, side, quantity, price, pnl, balance_after in trades:
            cursor.execute("""
                INSERT INTO trades (bot_id, symbol, action, side, quantity, price, pnl, balance_after, executed_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (bot_id, symbol, action, side, quantity, price, pnl, balance_after, timestamp))

        print(f"✅ Created {len(trades)} trade entries")

        # Create bot metrics (snapshots over last 3 days)
        base_time = now - timedelta(days=3)
        for i in range(0, 72, 6):  # Every 6 hours for 3 days
            timestamp = base_time + timedelta(hours=i)

            # Simulate some realistic metric changes
            balance = 200.00 + (i * 0.05) + ((-1) ** i * 2)  # Fluctuating balance
            btc_position = 0.010 + (i * 0.0001)
            eth_position = 0.15 + (i * 0.002)
            btc_pnl = ((-1) ** i) * (1 + i * 0.1)
            eth_pnl = ((-1) ** (i+1)) * (0.5 + i * 0.08)
            margin_btc = 5.0 - (i * 0.02)
            margin_eth = 4.5 - (i * 0.015)

            # BTC metrics
            cursor.execute("""
                INSERT INTO bot_metrics (bot_id, symbol, balance, position_value, unrealized_pnl, margin_level, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (bot_id, 'BTCUSDT', balance, btc_position * 42500, btc_pnl, max(margin_btc, 2.0), timestamp))

            # ETH metrics
            cursor.execute("""
                INSERT INTO bot_metrics (bot_id, symbol, balance, position_value, unrealized_pnl, margin_level, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (bot_id, 'ETHUSDT', balance, eth_position * 2250, eth_pnl, max(margin_eth, 2.0), timestamp))

        print(f"✅ Created bot metrics (72 data points)")

        conn.commit()
        print("\n🎉 Dummy data successfully created!")
        print(f"\n📊 Summary:")
        print(f"   - User: oudejans@gmail.com (Timezone: Europe/Amsterdam)")
        print(f"   - Bot: Test BTC/ETH Bot (ID: {bot_id})")
        print(f"   - Trading Pairs: BTCUSDT, ETHUSDT")
        print(f"   - Bot Logs: {len(log_entries)} entries over 3 days")
        print(f"   - Trades: {len(trades)} trades")
        print(f"   - Metrics: 72 data points (hourly snapshots)")
        print(f"\n🌐 Login at http://localhost:5000 to see the data!")

if __name__ == '__main__':
    main()
