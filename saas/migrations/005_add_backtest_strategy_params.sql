-- Migration: Add strategy parameters to backtest_configs
-- Date: 2025-11-02
-- Description: Add all strategy configuration parameters to backtest_configs table

-- Add strategy parameter columns to backtest_configs
ALTER TABLE backtest_configs
ADD COLUMN IF NOT EXISTS days INTEGER DEFAULT 7,
ADD COLUMN IF NOT EXISTS balance DECIMAL(20,8) DEFAULT 200.0,
ADD COLUMN IF NOT EXISTS source VARCHAR(50) DEFAULT 'binance',
ADD COLUMN IF NOT EXISTS profit_pnl DECIMAL(10,6) DEFAULT 0.1,
ADD COLUMN IF NOT EXISTS max_margin_pct DECIMAL(10,6),
ADD COLUMN IF NOT EXISTS profit_threshold DECIMAL(10,6) DEFAULT 0.003,
ADD COLUMN IF NOT EXISTS buy_until_limit DECIMAL(10,6) DEFAULT 0.02,
ADD COLUMN IF NOT EXISTS close_threshold_high DECIMAL(10,4) DEFAULT 10.0,
ADD COLUMN IF NOT EXISTS close_threshold_mid DECIMAL(10,4) DEFAULT 7.5,
ADD COLUMN IF NOT EXISTS close_pct_high DECIMAL(10,4) DEFAULT 0.5,
ADD COLUMN IF NOT EXISTS close_pct_mid DECIMAL(10,4) DEFAULT 0.33;

-- Add comments to document each parameter
COMMENT ON COLUMN backtest_configs.days IS 'Number of days to backtest (e.g., 1, 7, 30, 90)';
COMMENT ON COLUMN backtest_configs.interval IS 'Candle interval in minutes (always use 1 for 1-minute candles)';
COMMENT ON COLUMN backtest_configs.source IS 'Data source (binance recommended)';
COMMENT ON COLUMN backtest_configs.balance IS 'Initial balance in USDT (default: 200)';
COMMENT ON COLUMN backtest_configs.side IS 'Position side (Long or Short)';
COMMENT ON COLUMN backtest_configs.leverage IS 'Leverage multiplier (default: 10)';
COMMENT ON COLUMN backtest_configs.profit_pnl IS 'Profit-taking threshold as decimal (default: 0.1 = 10%)';
COMMENT ON COLUMN backtest_configs.max_margin_pct IS 'Maximum margin usage cap (e.g., 0.40 = 40% max). NULL = no cap';
COMMENT ON COLUMN backtest_configs.profit_threshold IS 'Price movement threshold to start considering profit-taking (default: 0.003 = 0.3%)';
COMMENT ON COLUMN backtest_configs.buy_until_limit IS 'Maximum position size as % of balance (default: 0.02 = 2%)';
COMMENT ON COLUMN backtest_configs.close_threshold_high IS 'Position size % to trigger first reduction (default: 10.0%)';
COMMENT ON COLUMN backtest_configs.close_threshold_mid IS 'Position size % to trigger second reduction (default: 7.5%)';
COMMENT ON COLUMN backtest_configs.close_pct_high IS 'How much to close at first threshold (default: 0.5 = 50%)';
COMMENT ON COLUMN backtest_configs.close_pct_mid IS 'How much to close at second threshold (default: 0.33 = 33%)';
