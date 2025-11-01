"""
Migration script to add OAuth fields to users table
Run this to add Google OAuth support
"""
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from saas.database import get_db
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate_oauth_fields():
    """Add OAuth fields to users table"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()

            # Add OAuth fields
            logger.info("Adding OAuth fields to users table...")

            # Make password_hash nullable (for OAuth users)
            cursor.execute("""
                ALTER TABLE users
                ALTER COLUMN password_hash DROP NOT NULL
            """)
            logger.info("✓ Made password_hash nullable")

            # Change is_active default to FALSE (admin approval required)
            cursor.execute("""
                ALTER TABLE users
                ALTER COLUMN is_active SET DEFAULT FALSE
            """)
            logger.info("✓ Changed is_active default to FALSE")

            # Add google_id field
            cursor.execute("""
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS google_id VARCHAR(255) UNIQUE
            """)
            logger.info("✓ Added google_id column")

            # Add oauth_provider field
            cursor.execute("""
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS oauth_provider VARCHAR(20)
            """)
            logger.info("✓ Added oauth_provider column")

            # Add profile_picture_url field
            cursor.execute("""
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS profile_picture_url TEXT
            """)
            logger.info("✓ Added profile_picture_url column")

            # Create index on google_id
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_users_google_id ON users(google_id)
            """)
            logger.info("✓ Created index on google_id")

            conn.commit()
            logger.info("✅ OAuth migration completed successfully!")

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise


if __name__ == "__main__":
    migrate_oauth_fields()
