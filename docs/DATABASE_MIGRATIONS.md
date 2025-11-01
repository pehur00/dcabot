# Database Migrations

This document describes the database migration strategy for the DCA Bot SaaS platform.

## Overview

Database migrations are managed through SQL files in `saas/migrations/` and tracked using the `saas/migrate.py` script. This approach is simple, version-controlled, and runs automatically on deployment.

## Migration Workflow

### 1. Creating a New Migration

When you need to change the database schema:

1. Create a new SQL file in `saas/migrations/` with a sequential number:
   ```
   saas/migrations/004_add_new_feature.sql
   ```

2. Write your migration SQL (supports any PostgreSQL syntax):
   ```sql
   -- Add new column
   ALTER TABLE bots ADD COLUMN description TEXT;

   -- Create new table
   CREATE TABLE IF NOT EXISTS bot_tags (
       id SERIAL PRIMARY KEY,
       bot_id INTEGER REFERENCES bots(id) ON DELETE CASCADE,
       tag VARCHAR(50) NOT NULL,
       created_at TIMESTAMP DEFAULT NOW()
   );

   -- Insert default data
   INSERT INTO settings (key, value) VALUES ('feature_enabled', 'true');
   ```

3. Test locally:
   ```bash
   export DATABASE_URL="postgresql://dcabot:dcabot_dev_password@localhost:5435/dcabot_dev"
   python saas/migrate.py
   ```

4. Commit and push:
   ```bash
   git add saas/migrations/004_add_new_feature.sql
   git commit -m "Add migration: description field and tags"
   git push
   ```

### 2. Automatic Deployment

When you push to Render:

1. **Render builds your app** and runs `buildCommand`:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt -r requirements-saas.txt
   python saas/migrate.py  # ← Migrations run here
   ```

2. **Migration script**:
   - Creates `schema_migrations` table if needed
   - Checks which migrations have been applied
   - Runs only new/pending migrations
   - Records each successful migration
   - Fails the build if any migration fails (safe!)

3. **App starts** only if migrations succeed

This ensures your database is always up-to-date before the new code runs.

## Migration Commands

### Run Pending Migrations
```bash
export DATABASE_URL="postgresql://..."
python saas/migrate.py
```

Output:
```
🚀 Starting database migrations...
📁 Migrations directory: /path/to/saas/migrations
✅ Migrations tracking table ready
📋 Found 2 pending migration(s)
📝 Applying migration: 004_add_new_feature.sql
✅ Successfully applied: 004_add_new_feature.sql
✅ Successfully applied 1/1 migration(s)
🎉 Database is now up to date!
```

### Check Migration Status
```bash
python saas/migrate.py --status
```

Output:
```
📊 Migration Status:
============================================================
✅ Applied       001_initial_schema.sql
✅ Applied       002_add_execution_metrics.sql
✅ Applied       003_add_admin_and_approval.sql
⏳ Pending       004_add_new_feature.sql
============================================================
Total: 4 migrations (3 applied, 1 pending)
```

## Migration Tracking

Migrations are tracked in the `schema_migrations` table:

```sql
CREATE TABLE schema_migrations (
    version VARCHAR(255) PRIMARY KEY,    -- Filename (e.g., "001_initial_schema.sql")
    applied_at TIMESTAMP DEFAULT NOW()   -- When it was applied
);
```

**Important**: Do NOT manually modify this table. Let the migration script manage it.

## Best Practices

### ✅ DO

1. **Name migrations sequentially**: `001_`, `002_`, `003_`, etc.
2. **Use descriptive names**: `003_add_admin_and_approval.sql`
3. **Make migrations idempotent**: Use `IF NOT EXISTS`, `IF EXISTS`, etc.
   ```sql
   ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT FALSE;
   ```
4. **Test locally first**: Always test migrations on your local database
5. **One feature per migration**: Keep migrations focused
6. **Include rollback info**: Comment how to undo changes
   ```sql
   -- To rollback: ALTER TABLE users DROP COLUMN is_admin;
   ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT FALSE;
   ```

### ❌ DON'T

1. **Don't edit applied migrations**: Once deployed, create a new migration instead
2. **Don't skip numbers**: Migrations run in alphabetical order
3. **Don't delete old migrations**: They're part of your history
4. **Don't rely on data existing**: Another migration might have changed it

## Example Migrations

### Adding a Column
```sql
-- 005_add_bot_description.sql
ALTER TABLE bots ADD COLUMN IF NOT EXISTS description TEXT;
```

### Creating a Table
```sql
-- 006_create_notifications.sql
CREATE TABLE IF NOT EXISTS notifications (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    message TEXT NOT NULL,
    read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications(user_id);
```

### Data Migration
```sql
-- 007_migrate_old_settings.sql
-- Move settings from env to database
INSERT INTO settings (key, value)
SELECT 'bot_interval', '5'
WHERE NOT EXISTS (SELECT 1 FROM settings WHERE key = 'bot_interval');
```

### Updating Existing Data
```sql
-- 008_normalize_emails.sql
UPDATE users SET email = LOWER(email) WHERE email != LOWER(email);
```

## Rollback Strategy

Migrations don't support automatic rollback. If you need to undo a migration:

1. **Create a new migration** to reverse the changes:
   ```sql
   -- 009_rollback_description.sql
   ALTER TABLE bots DROP COLUMN IF EXISTS description;
   ```

2. **For production emergencies**, you can manually:
   ```sql
   -- Remove from tracking (allows re-running)
   DELETE FROM schema_migrations WHERE version = '005_add_bot_description.sql';

   -- Manually undo changes
   ALTER TABLE bots DROP COLUMN description;
   ```

## Local Development

### Reset Local Database
```bash
# Drop and recreate database
psql -h localhost -p 5435 -U dcabot -c "DROP DATABASE dcabot_dev;"
psql -h localhost -p 5435 -U dcabot -c "CREATE DATABASE dcabot_dev;"

# Run all migrations
export DATABASE_URL="postgresql://dcabot:dcabot_dev_password@localhost:5435/dcabot_dev"
python saas/migrate.py
```

### Test Migration Locally
```bash
# Check what will run
python saas/migrate.py --status

# Run migrations
python saas/migrate.py

# Verify database
psql -h localhost -p 5435 -U dcabot dcabot_dev -c "\dt"  # List tables
psql -h localhost -p 5435 -U dcabot dcabot_dev -c "\d+ users"  # Describe table
```

## Production Deployment

### Render Deployment Flow

1. **Developer pushes code**:
   ```bash
   git push origin feature/saas-transformation
   ```

2. **Render detects changes** and starts build

3. **Build phase**:
   ```bash
   pip install dependencies
   python saas/migrate.py  # ← Migrations run
   ```
   - If migration fails → Build stops, old version keeps running ✅
   - If migration succeeds → Build continues

4. **Deploy phase**:
   ```bash
   gunicorn starts with new code
   ```

5. **Health checks** confirm app is running

### Zero-Downtime Deployments

Migrations run during build, before traffic switches to new version:
- Old version keeps running during migration
- New version only starts after successful migration
- Database changes are compatible with old code (additive)

**Example safe migration**:
```sql
-- ✅ SAFE: Adding optional column (old code ignores it)
ALTER TABLE bots ADD COLUMN description TEXT;

-- ❌ UNSAFE: Dropping column (old code will error)
-- ALTER TABLE bots DROP COLUMN name;  -- Don't do this!
```

## Troubleshooting

### Migration Failed on Render

**Symptom**: Build fails with migration error

**Solution**:
1. Check Render build logs for error message
2. Fix the SQL in migration file
3. Push the fix:
   ```bash
   git add saas/migrations/XXX_failed_migration.sql
   git commit -m "Fix migration error"
   git push
   ```
4. Render will retry with fixed migration

### Migration Runs Twice

**Symptom**: Migration appears to run multiple times

**Explanation**: This is safe! The migration script:
1. Checks `schema_migrations` table
2. Only runs migrations not in the table
3. Skips already-applied migrations

### Local Database Out of Sync

**Symptom**: Local database different from production

**Solution**:
```bash
# Check what's missing
python saas/migrate.py --status

# Run pending migrations
python saas/migrate.py
```

## FAQ

**Q: Can I edit an old migration file?**
A: No, once deployed. Create a new migration instead.

**Q: What if I need to run migrations manually?**
A: SSH into Render and run `python saas/migrate.py`

**Q: Can migrations run in parallel?**
A: No, they run sequentially in alphabetical order.

**Q: What if migration takes >10 minutes?**
A: Split it into multiple smaller migrations or run manually.

**Q: How do I see which migrations ran?**
A: Query `SELECT * FROM schema_migrations ORDER BY applied_at;`

## Summary

The migration system is designed to be:
- ✅ **Simple**: Just SQL files
- ✅ **Safe**: Fails fast, doesn't break production
- ✅ **Automatic**: Runs on every deploy
- ✅ **Trackable**: Git history + database tracking
- ✅ **Idempotent**: Can run multiple times safely

For questions or issues, check the migration logs or create an issue.
