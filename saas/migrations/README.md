# Database Migrations

This directory contains database migrations for the DCA Bot SaaS platform.

## How It Works

Migrations run **automatically** when the Flask app starts:
1. The migration runner checks which migrations have been applied
2. Runs any pending migrations in order
3. Tracks completed migrations in the `schema_migrations` table

## Migration File Format

Migrations are Python files with a specific format:

```python
"""
Migration: Brief description
Date: YYYY-MM-DD
"""

description = "Longer description of what this migration does"

def upgrade(conn):
    """
    Apply the migration

    Args:
        conn: psycopg2 database connection
    """
    cursor = conn.cursor()

    # Your migration SQL here
    cursor.execute("""
        ALTER TABLE users ADD COLUMN new_field VARCHAR(255)
    """)

    conn.commit()
```

## Naming Convention

Migrations must be named with a 3-digit prefix and descriptive name:

- `001_add_password_reset_tokens.py`
- `002_add_oauth_fields.py`
- `003_your_migration_name.py`

## Creating a New Migration

1. Create a new file in `saas/migrations/`
2. Use the next available number (e.g., `003_`)
3. Follow the format above
4. The migration will run automatically on next app startup

## Existing Migrations

| Version | Description | Date |
|---------|-------------|------|
| 001 | Add password reset tokens table | 2025-11-01 |
| 002 | Add Google OAuth fields to users | 2025-11-01 |

## Checking Migration Status

Migrations are tracked in the `schema_migrations` table:

```sql
SELECT * FROM schema_migrations ORDER BY applied_at;
```

## Production Deployment

**Migrations run automatically** when the app starts, so:

1. Push your code with new migrations
2. Deploy to Render.com
3. Migrations run during startup
4. App starts normally

No manual intervention needed!

## Troubleshooting

### Migration Failed

If a migration fails:
1. Check the error logs
2. Fix the migration file
3. Manually remove the failed migration from `schema_migrations` if needed:
   ```sql
   DELETE FROM schema_migrations WHERE version = '003_your_migration';
   ```
4. Restart the app

### Skipping a Migration

To mark a migration as already applied without running it:

```sql
INSERT INTO schema_migrations (version, description)
VALUES ('003_your_migration', 'Description');
```

### Re-running a Migration

1. Delete the record from `schema_migrations`
2. Restart the app

```sql
DELETE FROM schema_migrations WHERE version = '003_your_migration';
```

## Best Practices

1. **Test locally first** - Run migrations in development before production
2. **Make migrations idempotent** - Use `IF NOT EXISTS`, `IF EXISTS`, etc.
3. **One change per migration** - Don't combine unrelated changes
4. **Never edit existing migrations** - Create a new migration to fix issues
5. **Backup before production** - Always backup the database before deploying

## Migration Safety

The migration system includes safety features:

- **Transaction support** - Each migration runs in a transaction
- **Error handling** - App continues even if migrations fail (allows manual fix)
- **Tracking** - Prevents running the same migration twice
- **Ordered execution** - Migrations run in numeric order
