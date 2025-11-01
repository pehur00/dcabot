#!/usr/bin/env python3
"""
Test database connection to Digital Ocean managed PostgreSQL
Run this to verify your DATABASE_URL is correct
"""
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Load .env if it exists
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        print(f"✓ Loaded environment from {env_path}")
except ImportError:
    print("⚠ python-dotenv not installed, using environment variables only")

# Test connection using saas/database.py
try:
    from saas.database import test_connection, get_db_config, get_db

    print("\n" + "="*60)
    print("DCA Bot - Database Connection Test")
    print("="*60 + "\n")

    # Show configuration (without password)
    try:
        config = get_db_config()
        print("Database Configuration:")
        print(f"  Host: {config['host']}")
        print(f"  Port: {config['port']}")
        print(f"  Database: {config['database']}")
        print(f"  User: {config['user']}")
        print(f"  SSL Mode: {config['sslmode']}")
        print(f"  Password: {'*' * len(config['password']) if config['password'] else '(empty)'}")
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        print("\nMake sure DATABASE_URL is set in .env or environment")
        sys.exit(1)

    print("\nTesting connection...")

    # Test connection
    if test_connection():
        print("✅ Database connection successful!\n")

        # Show database info
        with get_db() as conn:
            cursor = conn.cursor()

            # PostgreSQL version
            cursor.execute("SELECT version()")
            version = cursor.fetchone()[0]
            print(f"PostgreSQL Version:")
            print(f"  {version.split(',')[0]}\n")

            # List tables
            cursor.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                ORDER BY table_name
            """)
            tables = cursor.fetchall()

            if tables:
                print("Existing Tables:")
                for table in tables:
                    # Count rows in each table
                    cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
                    count = cursor.fetchone()[0]
                    print(f"  • {table[0]} ({count} rows)")
            else:
                print("⚠ No tables found")
                print("\nTo create tables, run:")
                print("  psql $DATABASE_URL -f saas/schema.sql")

        print("\n✅ All checks passed!\n")
        sys.exit(0)

except Exception as e:
    print(f"\n❌ Database connection failed!")
    print(f"   Error: {e}\n")
    print("Troubleshooting:")
    print("  1. Check DATABASE_URL in .env file")
    print("  2. Verify password is correct")
    print("  3. Ensure SSL certificate is valid (sslmode=require)")
    print("  4. Check firewall allows connection to port 25060")
    print("  5. Verify database 'diptrader' exists")
    print()
    sys.exit(1)
