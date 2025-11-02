-- Migration: Add timezone and country fields to users
-- Date: 2025-11-02
-- Description: Add timezone and country_code columns to support timezone-aware date display

-- Add country_code column (ISO 3166-1 alpha-2 country code)
ALTER TABLE users
ADD COLUMN IF NOT EXISTS country_code VARCHAR(2);

-- Add timezone column (IANA timezone identifier)
ALTER TABLE users
ADD COLUMN IF NOT EXISTS timezone VARCHAR(50) DEFAULT 'UTC';

-- Add comment for documentation
COMMENT ON COLUMN users.country_code IS 'ISO 3166-1 alpha-2 country code (e.g., US, GB, DE)';
COMMENT ON COLUMN users.timezone IS 'IANA timezone identifier (e.g., America/New_York, Europe/London)';

-- Create index for timezone queries
CREATE INDEX IF NOT EXISTS idx_users_timezone ON users(timezone);
