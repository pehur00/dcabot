-- Mark migration 001 as applied on production
-- Run this ONCE on production database before deploying the auto-migration system

-- This tells the migration system that migration 001 (initial schema) is already applied
-- so it will only run migration 002 (OAuth) on the next deploy

INSERT INTO schema_migrations (version, description, applied_at)
VALUES ('001_initial_schema', 'Initial database schema with all core tables', CURRENT_TIMESTAMP)
ON CONFLICT (version) DO NOTHING;

-- Verify it was added
SELECT * FROM schema_migrations ORDER BY version;
