-- Migration 013: Add Virtual Balance Tracking for AI Bots
-- Date: 2025-11-05
-- Description: Add virtual balance columns to track isolated account values per AI bot

-- Add virtual balance to ai_bots table
ALTER TABLE ai_bots
ADD COLUMN IF NOT EXISTS virtual_balance DECIMAL(20, 8) DEFAULT 100.00,
ADD COLUMN IF NOT EXISTS initial_balance DECIMAL(20, 8) DEFAULT 100.00,
ADD COLUMN IF NOT EXISTS total_realized_pnl DECIMAL(20, 8) DEFAULT 0.00,
ADD COLUMN IF NOT EXISTS total_trades_executed INTEGER DEFAULT 0;

-- Add virtual balance snapshot to ai_model_performance table
ALTER TABLE ai_model_performance
ADD COLUMN IF NOT EXISTS virtual_balance DECIMAL(20, 8);

-- Index already exists: idx_ai_performance_bot on (ai_bot_id, snapshot_at DESC)

-- Create virtual balance history table for charting
CREATE TABLE IF NOT EXISTS ai_bot_balance_history (
    id SERIAL PRIMARY KEY,
    ai_bot_id INTEGER NOT NULL REFERENCES ai_bots(id) ON DELETE CASCADE,
    model_config_id INTEGER NOT NULL REFERENCES ai_model_configs(id),
    virtual_balance DECIMAL(20, 8) NOT NULL,
    balance_change DECIMAL(20, 8) DEFAULT 0,
    change_reason VARCHAR(50), -- 'api_cost', 'trade_pnl', 'trade_fee', 'initial'
    decision_id INTEGER REFERENCES ai_decisions(id),
    trade_id INTEGER REFERENCES trades(id),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_balance_history_bot_created
ON ai_bot_balance_history(ai_bot_id, created_at);

CREATE INDEX IF NOT EXISTS idx_balance_history_model_created
ON ai_bot_balance_history(model_config_id, created_at);

-- Seed initial balance history for existing AI bots
INSERT INTO ai_bot_balance_history (
    ai_bot_id, model_config_id, virtual_balance, balance_change, change_reason
)
SELECT
    ab.id,
    ab.model_config_id,
    100.00,
    100.00,
    'initial'
FROM ai_bots ab
WHERE NOT EXISTS (
    SELECT 1 FROM ai_bot_balance_history
    WHERE ai_bot_id = ab.id AND change_reason = 'initial'
);

COMMENT ON TABLE ai_bot_balance_history IS 'Tracks virtual balance changes over time for each AI bot (for charting)';
COMMENT ON COLUMN ai_bots.virtual_balance IS 'Current virtual balance for isolated performance tracking';
COMMENT ON COLUMN ai_bots.initial_balance IS 'Starting balance (default $100)';
COMMENT ON COLUMN ai_bots.total_realized_pnl IS 'Cumulative PnL from closed trades';
