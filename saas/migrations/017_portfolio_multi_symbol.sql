-- Migration 017: Portfolio-Level Trading (Multi-Symbol Support)
-- Allows one bot to trade multiple symbols with portfolio-level decisions
--
-- Changes:
-- 1. Add symbols array to ai_bots (JSONB)
-- 2. Migrate existing symbol data to symbols array
-- 3. Keep symbol column for backward compatibility (deprecated)

-- Add symbols array column (JSONB for flexibility)
ALTER TABLE ai_bots
ADD COLUMN IF NOT EXISTS symbols JSONB DEFAULT '[]'::jsonb;

-- Migrate existing symbol data to symbols array
-- Convert single symbol to array: "BTCUSDT" -> ["BTCUSDT"]
UPDATE ai_bots
SET symbols = jsonb_build_array(symbol)
WHERE symbols = '[]'::jsonb AND symbol IS NOT NULL;

-- Add comment for deprecated column
COMMENT ON COLUMN ai_bots.symbol IS 'DEPRECATED: Use symbols array instead. Kept for backward compatibility.';

-- Add index for symbols array (GIN index for JSONB)
CREATE INDEX IF NOT EXISTS idx_ai_bots_symbols ON ai_bots USING GIN (symbols);

-- Update ai_decisions to support portfolio-level decisions
-- Add portfolio_decision_id to group decisions made together
ALTER TABLE ai_decisions
ADD COLUMN IF NOT EXISTS portfolio_decision_id UUID;

-- Add index for portfolio decisions
CREATE INDEX IF NOT EXISTS idx_ai_decisions_portfolio ON ai_decisions (portfolio_decision_id);

-- Create portfolio_decisions table to track portfolio-level decisions
CREATE TABLE IF NOT EXISTS ai_portfolio_decisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ai_bot_id INTEGER NOT NULL REFERENCES ai_bots(id) ON DELETE CASCADE,
    decision_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Portfolio context
    total_balance DECIMAL(20, 8),
    available_balance DECIMAL(20, 8),
    used_balance DECIMAL(20, 8),

    -- Portfolio decision
    portfolio_action TEXT, -- 'REBALANCE', 'HOLD_ALL', 'LIQUIDATE', 'EXPAND'
    risk_assessment TEXT,
    reasoning TEXT,

    -- AI model metrics
    input_tokens INTEGER,
    output_tokens INTEGER,
    api_cost DECIMAL(10, 6),
    response_time_ms INTEGER,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Add index for bot lookups
CREATE INDEX IF NOT EXISTS idx_portfolio_decisions_bot ON ai_portfolio_decisions (ai_bot_id);
CREATE INDEX IF NOT EXISTS idx_portfolio_decisions_time ON ai_portfolio_decisions (decision_time DESC);

-- Link existing decisions to their bot's first portfolio decision (for migration)
-- This is for backward compatibility only
-- New portfolio decisions will be linked properly by the executor
