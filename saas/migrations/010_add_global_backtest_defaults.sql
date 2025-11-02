-- Migration: Add default leverage, days, and balance to global config
-- Date: 2025-11-02
-- Description: Move leverage, days, and balance from per-symbol to global settings

-- Add default backtest execution parameters to global config
ALTER TABLE global_backtest_config
ADD COLUMN IF NOT EXISTS leverage INTEGER DEFAULT 10,
ADD COLUMN IF NOT EXISTS days INTEGER DEFAULT 7,
ADD COLUMN IF NOT EXISTS balance DECIMAL(20, 8) DEFAULT 200.0;

-- Update existing global configs with default values
UPDATE global_backtest_config
SET leverage = 10,
    days = 7,
    balance = 200.0
WHERE leverage IS NULL OR days IS NULL OR balance IS NULL;

-- Add NOT NULL constraints after setting defaults
ALTER TABLE global_backtest_config
ALTER COLUMN leverage SET NOT NULL,
ALTER COLUMN days SET NOT NULL,
ALTER COLUMN balance SET NOT NULL;

-- Add comments
COMMENT ON COLUMN global_backtest_config.leverage IS 'Default leverage for all backtests (e.g., 10 = 10x leverage)';
COMMENT ON COLUMN global_backtest_config.days IS 'Default backtest period in days (e.g., 7 = last 7 days)';
COMMENT ON COLUMN global_backtest_config.balance IS 'Default starting balance for backtests in USD (e.g., 200.0 = $200)';
