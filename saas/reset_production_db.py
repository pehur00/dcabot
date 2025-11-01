#!/usr/bin/env python3
"""
Reset production database - DROP ALL TABLES and let migrations recreate them.
Use with caution - this will delete all data!
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from saas.database import get_db


def confirm_reset():
    """Ask for confirmation before proceeding"""
    print("=" * 70)
    print("⚠️  WARNING: This will DROP ALL TABLES in the production database!")
    print("=" * 70)
    print()
    print("This will delete:")
    print("  - All users and authentication data")
    print("  - All bots and configurations")
    print("  - All trading history")
    print("  - All logs and metrics")
    print("  - All migration records")
    print()

    response = input("Are you ABSOLUTELY SURE you want to proceed? (type 'yes' to confirm): ")
    return response.lower() == 'yes'


def reset_database():
    """Drop all tables from the database"""

    if not confirm_reset():
        print("\n❌ Reset cancelled")
        return False

    print("\n🔄 Connecting to database...")

    with get_db() as conn:
        cursor = conn.cursor()

        print("📋 Fetching list of tables...")
        cursor.execute("""
            SELECT tablename
            FROM pg_tables
            WHERE schemaname = 'public'
        """)
        tables = [row[0] for row in cursor.fetchall()]

        if not tables:
            print("✅ No tables found - database is already empty")
            return True

        print(f"\n📦 Found {len(tables)} tables:")
        for table in tables:
            print(f"  - {table}")

        print(f"\n🗑️  Dropping {len(tables)} tables...")

        # Drop all tables with CASCADE
        cursor.execute("""
            DROP TABLE IF EXISTS
                schema_migrations,
                settings,
                password_reset_tokens,
                execution_metrics,
                bot_metrics,
                bot_logs,
                trades,
                trading_pairs,
                bots,
                users
            CASCADE
        """)

        conn.commit()

        print("✅ All tables dropped successfully!")
        print()
        print("Next steps:")
        print("  1. Deploy the latest code to Render")
        print("  2. Migrations will run automatically on startup")
        print("  3. Fresh database will be created with correct schema")

        return True


if __name__ == "__main__":
    try:
        success = reset_database()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
