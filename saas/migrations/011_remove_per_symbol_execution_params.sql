-- Migration: Remove leverage, days, balance from per-symbol configs
-- Date: 2025-11-02
-- Description: These parameters are now global-only, not per-symbol

-- Remove execution parameters from backtest_configs (now in global config only)
ALTER TABLE backtest_configs
DROP COLUMN IF EXISTS leverage,
DROP COLUMN IF EXISTS days,
DROP COLUMN IF EXISTS balance;

-- Add comment to clarify this table's purpose
COMMENT ON TABLE backtest_configs IS 'Per-symbol backtest configurations. Execution parameters (leverage, days, balance) and strategy parameters are defined globally in global_backtest_config.';
