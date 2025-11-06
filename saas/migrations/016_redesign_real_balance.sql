-- Migration 016: Redesign AI bots for real balance tracking
-- Date: 2025-11-05
-- Description: Remove virtual balance, use Phemex account balance instead
--              1 AI Bot = 1 Phemex Account = 1 AI Model

-- Remove virtual balance tracking from ai_bots
ALTER TABLE ai_bots
DROP COLUMN IF EXISTS virtual_balance CASCADE,
DROP COLUMN IF EXISTS initial_balance CASCADE,
DROP COLUMN IF EXISTS total_realized_pnl CASCADE,
DROP COLUMN IF EXISTS total_trades_executed CASCADE;

-- Drop balance history table (Phemex is source of truth for balance history)
DROP TABLE IF EXISTS ai_bot_balance_history CASCADE;

-- Add new columns for real balance tracking
ALTER TABLE ai_bots
ADD COLUMN IF NOT EXISTS testnet BOOLEAN DEFAULT true,
ADD COLUMN IF NOT EXISTS initial_balance_snapshot DECIMAL(20, 8),
ADD COLUMN IF NOT EXISTS snapshot_taken_at TIMESTAMP;

-- Update ai_model_performance to remove virtual_balance
ALTER TABLE ai_model_performance
DROP COLUMN IF EXISTS virtual_balance CASCADE;

-- Add index for testnet filtering
CREATE INDEX IF NOT EXISTS idx_ai_bots_testnet ON ai_bots(testnet);

-- Add comments
COMMENT ON COLUMN ai_bots.testnet IS 'Whether bot uses Phemex testnet (true) or mainnet (false)';
COMMENT ON COLUMN ai_bots.initial_balance_snapshot IS 'Snapshot of Phemex account balance when bot was created (for PnL calculation)';
COMMENT ON COLUMN ai_bots.snapshot_taken_at IS 'Timestamp when initial balance snapshot was taken';

-- Update table comment
COMMENT ON TABLE ai_bots IS 'AI trading bots - 1 bot = 1 Phemex account = 1 AI model. Each bot must have unique API credentials.';
