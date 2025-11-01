"""
Simple migration system for DCA Bot SaaS
Tracks and auto-runs database migrations
"""
import os
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class MigrationRunner:
    """Handles database migrations with tracking"""

    def __init__(self, db_connection):
        self.conn = db_connection
        self.migrations_dir = Path(__file__).parent / 'migrations'

    def ensure_migrations_table(self):
        """Create schema_migrations table if it doesn't exist"""
        cursor = self.conn.cursor()

        # Create table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                id SERIAL PRIMARY KEY,
                version VARCHAR(255) UNIQUE NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Add description column if it doesn't exist (for backwards compatibility)
        cursor.execute("""
            ALTER TABLE schema_migrations
            ADD COLUMN IF NOT EXISTS description TEXT
        """)

        self.conn.commit()
        logger.info("✓ Schema migrations table ready")

    def get_applied_migrations(self):
        """Get list of already applied migrations"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT version FROM schema_migrations ORDER BY version")
        return set(row[0] for row in cursor.fetchall())

    def get_pending_migrations(self):
        """Get list of migrations that haven't been applied yet"""
        applied = self.get_applied_migrations()

        # Find all migration files (format: 001_name.py)
        migration_files = sorted([
            f for f in os.listdir(self.migrations_dir)
            if f.endswith('.py') and not f.startswith('__')
        ])

        pending = []
        for filename in migration_files:
            version = filename.replace('.py', '')
            if version not in applied:
                pending.append((version, filename))

        return pending

    def run_migration(self, version, filename):
        """Run a single migration"""
        logger.info(f"Running migration: {version}")

        # Import the migration module
        import importlib.util
        migration_path = self.migrations_dir / filename
        spec = importlib.util.spec_from_file_location(version, migration_path)
        migration_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration_module)

        # Run the upgrade function
        migration_module.upgrade(self.conn)

        # Get description from module
        description = getattr(migration_module, 'description', version)

        # Record migration as applied
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO schema_migrations (version, description)
            VALUES (%s, %s)
        """, (version, description))
        self.conn.commit()

        logger.info(f"✓ Migration {version} completed")

    def run_pending_migrations(self):
        """Run all pending migrations"""
        self.ensure_migrations_table()

        pending = self.get_pending_migrations()

        if not pending:
            logger.info("✓ No pending migrations")
            return

        logger.info(f"Found {len(pending)} pending migration(s)")

        for version, filename in pending:
            try:
                self.run_migration(version, filename)
            except Exception as e:
                logger.error(f"✗ Migration {version} failed: {e}")
                raise

        logger.info(f"✅ All migrations completed successfully")


def run_migrations(db_connection):
    """
    Convenience function to run all pending migrations
    Call this on app startup
    """
    runner = MigrationRunner(db_connection)
    runner.run_pending_migrations()
