"""
Migration: Add Google OAuth support
Date: 2025-11-01

Adds OAuth authentication fields to users table and changes default behavior
for admin approval system.
"""

description = "Add Google OAuth support (google_id, oauth_provider, profile_picture_url)"


def upgrade(conn):
    """Add OAuth fields to users table"""
    cursor = conn.cursor()

    # Make password_hash nullable (OAuth users don't need passwords)
    cursor.execute("""
        ALTER TABLE users
        ALTER COLUMN password_hash DROP NOT NULL
    """)

    # Change is_active default to FALSE (admin approval required)
    cursor.execute("""
        ALTER TABLE users
        ALTER COLUMN is_active SET DEFAULT FALSE
    """)

    # Add google_id field
    cursor.execute("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS google_id VARCHAR(255) UNIQUE
    """)

    # Add oauth_provider field
    cursor.execute("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS oauth_provider VARCHAR(20)
    """)

    # Add profile_picture_url field
    cursor.execute("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS profile_picture_url TEXT
    """)

    # Create index on google_id
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_users_google_id ON users(google_id)
    """)

    conn.commit()
