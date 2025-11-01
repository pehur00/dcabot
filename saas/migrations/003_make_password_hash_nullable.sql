-- Migration: Make password_hash nullable for OAuth users
-- Date: 2025-11-01
-- Description: Allow password_hash to be NULL for OAuth-based users who don't use password authentication

-- Make password_hash nullable
ALTER TABLE users ALTER COLUMN password_hash DROP NOT NULL;
