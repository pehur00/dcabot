-- Migration: Add OAuth support columns
-- Date: 2025-11-01
-- Description: Add Google OAuth columns to users table

-- Add OAuth columns to users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS google_id VARCHAR(255) UNIQUE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS oauth_provider VARCHAR(20);
ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_picture_url TEXT;

-- Add index for google_id
CREATE INDEX IF NOT EXISTS idx_users_google_id ON users(google_id);
