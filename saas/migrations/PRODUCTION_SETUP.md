# Production Migration Setup - One-Time Only

## What This Does

Marks migration 001 as already applied on production, so when you deploy the auto-migration system, it will only run migration 002 (OAuth changes).

## Steps to Run on Production

### Method 1: Render.com Shell (Recommended)

1. Go to https://dashboard.render.com/
2. Select your `dcabot-saas-web` service
3. Click the **"Shell"** tab
4. Run this command:

```bash
python -c "
from saas.database import get_db

with get_db() as conn:
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO schema_migrations (version, description, applied_at)
        VALUES (\'001_initial_schema\', \'Initial database schema with all core tables\', CURRENT_TIMESTAMP)
        ON CONFLICT (version) DO NOTHING
    ''')
    conn.commit()

    # Verify
    cursor.execute('SELECT version, applied_at FROM schema_migrations')
    for row in cursor.fetchall():
        print(f'✓ {row[0]} applied at {row[1]}')
"
```

5. You should see output like:
   ```
   ✓ 001_initial_schema applied at 2025-11-01 22:15:00
   ```

### Method 2: Direct Database Access

If you have direct database access, run the SQL file:

```bash
psql $DATABASE_URL -f saas/migrations/MARK_001_AS_APPLIED.sql
```

## Verification

After running, verify the migration was recorded:

```sql
SELECT * FROM schema_migrations;
```

You should see:
```
 version          | description                              | applied_at
------------------+------------------------------------------+------------------------
 001_initial_schema | Initial database schema with all core tables | 2025-11-01 22:15:00
```

## What Happens Next

When you deploy the code with the auto-migration system:

1. App starts
2. Migration system checks `schema_migrations` table
3. Sees migration 001 is already applied ✓
4. Runs migration 002 (OAuth) automatically ✓
5. App starts normally ✓

## Troubleshooting

**Error: relation "schema_migrations" does not exist**

The migration system will create this table automatically on first run. This is normal.

**Error: duplicate key value violates unique constraint**

Migration 001 is already marked as applied. This is safe to ignore.

## After This One-Time Setup

You'll never need to manually run migrations again! All future migrations will run automatically on deploy.
