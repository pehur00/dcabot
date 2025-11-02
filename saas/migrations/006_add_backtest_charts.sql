-- Migration: Add chart paths to backtest_results
-- Date: 2025-11-02
-- Description: Store chart image paths for displaying backtest results visually

-- Add chart path columns
ALTER TABLE backtest_results
ADD COLUMN IF NOT EXISTS chart_balance_path VARCHAR(500),
ADD COLUMN IF NOT EXISTS chart_position_path VARCHAR(500),
ADD COLUMN IF NOT EXISTS chart_price_path VARCHAR(500);

-- Add comments
COMMENT ON COLUMN backtest_results.chart_balance_path IS 'Path to balance progression chart';
COMMENT ON COLUMN backtest_results.chart_position_path IS 'Path to position size chart';
COMMENT ON COLUMN backtest_results.chart_price_path IS 'Path to price and entry/exit chart';
