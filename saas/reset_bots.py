#!/usr/bin/env python3
"""
Reset AI bots - clear all historical data but keep bot configurations
This allows you to start fresh without re-creating the bots
"""
import sys
sys.path.insert(0, '..')
from database import get_db

def reset_ai_bots(bot_ids=None):
    """
    Reset AI bot historical data

    Args:
        bot_ids: List of bot IDs to reset, or None to reset all bots
    """
    with get_db() as conn:
        cursor = conn.cursor()

        if bot_ids:
            bot_filter = f"WHERE ai_bot_id = ANY(%s)"
            params = (bot_ids,)
            print(f"Resetting bots: {bot_ids}")
        else:
            bot_filter = ""
            params = ()
            print("Resetting ALL AI bots")

        # 1. Delete all trades
        cursor.execute(f"DELETE FROM ai_trades {bot_filter}", params)
        trades_deleted = cursor.rowcount
        print(f"✓ Deleted {trades_deleted} trades")

        # 2. Delete all decisions
        cursor.execute(f"DELETE FROM ai_decisions {bot_filter}", params)
        decisions_deleted = cursor.rowcount
        print(f"✓ Deleted {decisions_deleted} decisions")

        # 3. Delete all portfolio decisions (if they exist)
        try:
            cursor.execute(f"DELETE FROM ai_portfolio_decisions {bot_filter}", params)
            portfolio_deleted = cursor.rowcount
            print(f"✓ Deleted {portfolio_deleted} portfolio decisions")
        except Exception as e:
            print(f"⚠ Portfolio decisions table doesn't exist or error: {e}")

        # 4. Delete balance history
        cursor.execute(f"DELETE FROM ai_bot_balance_history {bot_filter}", params)
        balance_deleted = cursor.rowcount
        print(f"✓ Deleted {balance_deleted} balance history records")

        # 5. Delete performance snapshots
        cursor.execute(f"DELETE FROM ai_model_performance {bot_filter}", params)
        perf_deleted = cursor.rowcount
        print(f"✓ Deleted {perf_deleted} performance snapshots")

        # 6. Reset virtual balance to initial value (1000.0)
        if bot_ids:
            cursor.execute("""
                UPDATE ai_bots
                SET virtual_balance = 1000.0,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ANY(%s)
            """, params)
        else:
            cursor.execute("""
                UPDATE ai_bots
                SET virtual_balance = 1000.0,
                    updated_at = CURRENT_TIMESTAMP
            """)
        bots_reset = cursor.rowcount
        print(f"✓ Reset {bots_reset} bot balances to $1000.00")

        conn.commit()
        print("\n✅ Reset complete! Bots are ready for a fresh start.")


def list_bots():
    """List all AI bots"""
    from database import execute_query

    bots = execute_query("""
        SELECT
            ab.id,
            ab.name,
            ab.side,
            ab.symbols,
            ab.virtual_balance,
            ab.is_active,
            amc.name as model_name,
            COUNT(ad.id) as decision_count,
            COUNT(at.id) as trade_count
        FROM ai_bots ab
        JOIN ai_model_configs amc ON ab.model_config_id = amc.id
        LEFT JOIN ai_decisions ad ON ab.id = ad.ai_bot_id
        LEFT JOIN ai_trades at ON ab.id = at.ai_bot_id
        GROUP BY ab.id, ab.name, ab.side, ab.symbols, ab.virtual_balance, ab.is_active, amc.name
        ORDER BY ab.id
    """)

    print("\n=== Current AI Bots ===")
    for bot in bots:
        active = "🟢 ACTIVE" if bot['is_active'] else "⚪ PAUSED"
        print(f"\nBot #{bot['id']}: {bot['name']} ({active})")
        print(f"  Model: {bot['model_name']}")
        print(f"  Side: {bot['side']}")
        print(f"  Symbols: {bot['symbols']}")
        print(f"  Balance: ${bot['virtual_balance']:.2f}")
        print(f"  History: {bot['decision_count']} decisions, {bot['trade_count']} trades")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Reset AI bot historical data')
    parser.add_argument('--bots', type=int, nargs='+', help='Bot IDs to reset (e.g., --bots 1 2)')
    parser.add_argument('--list', action='store_true', help='List all bots')
    parser.add_argument('--all', action='store_true', help='Reset all bots')

    args = parser.parse_args()

    if args.list:
        list_bots()
    elif args.all:
        confirm = input("\n⚠️  Are you sure you want to reset ALL bots? (yes/no): ")
        if confirm.lower() == 'yes':
            reset_ai_bots()
        else:
            print("Cancelled.")
    elif args.bots:
        confirm = input(f"\n⚠️  Are you sure you want to reset bots {args.bots}? (yes/no): ")
        if confirm.lower() == 'yes':
            reset_ai_bots(args.bots)
        else:
            print("Cancelled.")
    else:
        print("Usage:")
        print("  List bots:       python reset_bots.py --list")
        print("  Reset specific:  python reset_bots.py --bots 1 2")
        print("  Reset all:       python reset_bots.py --all")
