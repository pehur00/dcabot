#!/usr/bin/env python3
"""
Database migration runner
Tracks which migrations have been applied and runs pending ones
"""
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from saas.database import get_db


def create_migrations_table():
    """Create table to track applied migrations"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version VARCHAR(255) PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT NOW()
            )
        """)
        conn.commit()
        print("✅ Migrations tracking table ready")


def get_applied_migrations():
    """Get list of already applied migrations"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT version FROM schema_migrations ORDER BY version")
        return set(row[0] for row in cursor.fetchall())


def get_pending_migrations(migrations_dir):
    """Get list of migration files that haven't been applied yet"""
    applied = get_applied_migrations()

    migration_files = sorted([
        f for f in os.listdir(migrations_dir)
        if f.endswith('.sql')
    ])

    pending = [f for f in migration_files if f not in applied]
    return pending


def apply_migration(migration_file, migrations_dir):
    """Apply a single migration file"""
    filepath = os.path.join(migrations_dir, migration_file)

    print(f"📝 Applying migration: {migration_file}")

    with open(filepath, 'r') as f:
        migration_sql = f.read()

    try:
        with get_db() as conn:
            cursor = conn.cursor()

            # Run the migration
            cursor.execute(migration_sql)

            # Record that this migration was applied
            cursor.execute("""
                INSERT INTO schema_migrations (version)
                VALUES (%s)
            """, (migration_file,))

            conn.commit()

        print(f"✅ Successfully applied: {migration_file}")
        return True
    except Exception as e:
        print(f"❌ Failed to apply {migration_file}: {e}")
        return False


def run_migrations():
    """Run all pending migrations"""
    migrations_dir = os.path.join(os.path.dirname(__file__), 'migrations')

    if not os.path.exists(migrations_dir):
        print(f"❌ Migrations directory not found: {migrations_dir}")
        sys.exit(1)

    print("🚀 Starting database migrations...")
    print(f"📁 Migrations directory: {migrations_dir}")

    # Ensure migrations tracking table exists
    create_migrations_table()

    # Get pending migrations
    pending = get_pending_migrations(migrations_dir)

    if not pending:
        print("✅ No pending migrations - database is up to date!")
        return True

    print(f"📋 Found {len(pending)} pending migration(s)")

    # Apply each pending migration
    success_count = 0
    for migration_file in pending:
        if apply_migration(migration_file, migrations_dir):
            success_count += 1
        else:
            print(f"❌ Migration failed, stopping here")
            sys.exit(1)

    print(f"\n✅ Successfully applied {success_count}/{len(pending)} migration(s)")
    print("🎉 Database is now up to date!")
    return True


def show_status():
    """Show migration status"""
    migrations_dir = os.path.join(os.path.dirname(__file__), 'migrations')

    create_migrations_table()

    applied = get_applied_migrations()
    all_migrations = sorted([
        f for f in os.listdir(migrations_dir)
        if f.endswith('.sql')
    ])

    print("\n📊 Migration Status:")
    print("=" * 60)

    for migration in all_migrations:
        status = "✅ Applied" if migration in applied else "⏳ Pending"
        print(f"{status:15} {migration}")

    print("=" * 60)
    print(f"Total: {len(all_migrations)} migrations ({len(applied)} applied, {len(all_migrations) - len(applied)} pending)")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Database migration runner')
    parser.add_argument('--status', action='store_true', help='Show migration status')
    args = parser.parse_args()

    if args.status:
        show_status()
    else:
        run_migrations()
