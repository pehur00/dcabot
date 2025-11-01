-- Add admin and approval fields to users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_approved BOOLEAN DEFAULT TRUE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS requested_at TIMESTAMP DEFAULT NOW();

-- Create settings table for global configuration
CREATE TABLE IF NOT EXISTS settings (
    key VARCHAR(255) PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Insert default setting for registration
INSERT INTO settings (key, value) VALUES ('registration_enabled', 'true')
ON CONFLICT (key) DO NOTHING;

-- Update existing users to be approved and first user to be admin
UPDATE users SET is_approved = TRUE WHERE is_approved IS NULL;
UPDATE users SET is_admin = TRUE WHERE id = 1;  -- First user becomes admin
