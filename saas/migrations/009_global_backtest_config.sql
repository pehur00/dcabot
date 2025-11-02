-- Migration: Global Backtest Configuration
-- Purpose: Move from per-symbol config to single global configuration
-- This simplifies backtest management and ensures consistent strategy parameters

-- Create global_backtest_config table for shared strategy parameters
CREATE TABLE IF NOT EXISTS global_backtest_config (
    id SERIAL PRIMARY KEY,

    -- Strategy parameters (from MartingaleTradingStrategy CONFIG)
    profit_pnl DECIMAL(10, 6) NOT NULL DEFAULT 0.1,           -- 10% profit target to close full position
    profit_threshold DECIMAL(10, 6) NOT NULL DEFAULT 0.003,   -- 0.3% min profit of balance before closing
    buy_until_limit DECIMAL(10, 6) NOT NULL DEFAULT 0.02,     -- 2% max position size before profit-taking
    max_margin_pct DECIMAL(10, 6) DEFAULT 0.50,               -- 50% max margin usage (prevents liquidations)
    begin_size_of_balance DECIMAL(10, 6) NOT NULL DEFAULT 0.006,  -- 0.6% initial order size

    -- Partial close thresholds
    close_threshold_high DECIMAL(10, 4) NOT NULL DEFAULT 10.0,  -- Close 50% when position > 10% of balance
    close_threshold_mid DECIMAL(10, 4) NOT NULL DEFAULT 7.5,    -- Close 33% when position > 7.5% of balance
    close_pct_high DECIMAL(10, 4) NOT NULL DEFAULT 0.5,         -- 50% close at high threshold
    close_pct_mid DECIMAL(10, 4) NOT NULL DEFAULT 0.33,         -- 33% close at mid threshold

    -- Metadata
    name VARCHAR(100) NOT NULL DEFAULT 'Default',
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert default configuration (matching current strategy CONFIG)
INSERT INTO global_backtest_config (
    name, description,
    profit_pnl, profit_threshold, buy_until_limit, max_margin_pct,
    begin_size_of_balance,
    close_threshold_high, close_threshold_mid,
    close_pct_high, close_pct_mid,
    is_active
) VALUES (
    'Default Strategy',
    'Standard Martingale strategy parameters matching MartingaleTradingStrategy CONFIG',
    0.1,        -- profit_pnl: 10% to close full position
    0.003,      -- profit_threshold: 0.3% of balance minimum
    0.02,       -- buy_until_limit: 2% of balance max position
    0.50,       -- max_margin_pct: 50% max margin usage
    0.006,      -- begin_size_of_balance: 0.6% initial order
    10.0,       -- close_threshold_high: 10% position size
    7.5,        -- close_threshold_mid: 7.5% position size
    0.5,        -- close_pct_high: Close 50%
    0.33,       -- close_pct_mid: Close 33%
    true        -- is_active
);

-- Remove per-symbol strategy columns from backtest_configs
-- These are now in global_backtest_config
ALTER TABLE backtest_configs DROP COLUMN IF EXISTS profit_pnl;
ALTER TABLE backtest_configs DROP COLUMN IF EXISTS max_margin_pct;
ALTER TABLE backtest_configs DROP COLUMN IF EXISTS profit_threshold;
ALTER TABLE backtest_configs DROP COLUMN IF EXISTS buy_until_limit;
ALTER TABLE backtest_configs DROP COLUMN IF EXISTS close_threshold_high;
ALTER TABLE backtest_configs DROP COLUMN IF EXISTS close_threshold_mid;
ALTER TABLE backtest_configs DROP COLUMN IF EXISTS close_pct_high;
ALTER TABLE backtest_configs DROP COLUMN IF EXISTS close_pct_mid;

-- Add foreign key to reference global config (optional, for future per-symbol overrides)
ALTER TABLE backtest_configs
ADD COLUMN IF NOT EXISTS config_id INTEGER REFERENCES global_backtest_config(id) DEFAULT 1;

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_global_backtest_config_active
ON global_backtest_config(is_active);

COMMENT ON TABLE global_backtest_config IS
'Global configuration for backtest strategy parameters. Simplifies management by using shared settings across all symbols.';

COMMENT ON COLUMN global_backtest_config.profit_pnl IS
'Profit percentage to close full position (e.g., 0.1 = 10%)';

COMMENT ON COLUMN global_backtest_config.max_margin_pct IS
'Maximum margin usage as percentage of balance (e.g., 0.50 = 50%)';

COMMENT ON COLUMN global_backtest_config.buy_until_limit IS
'Maximum position size before profit-taking as percentage of balance (e.g., 0.02 = 2%)';
