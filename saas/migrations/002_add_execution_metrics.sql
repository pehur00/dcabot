-- Migration: Add execution metrics table for tracking bot performance over time
-- This table stores snapshots of each bot execution including balance, positions, and outcomes

CREATE TABLE IF NOT EXISTS execution_metrics (
    id SERIAL PRIMARY KEY,
    bot_id INTEGER NOT NULL REFERENCES bots(id) ON DELETE CASCADE,
    symbol VARCHAR(20) NOT NULL,
    executed_at TIMESTAMP NOT NULL DEFAULT NOW(),

    -- Account-level metrics
    total_balance DECIMAL(20, 8),  -- Total account balance at execution time

    -- Position metrics (NULL if no position)
    position_size DECIMAL(20, 8),  -- Size of position in contracts/coins
    position_value DECIMAL(20, 8), -- USD value of position
    unrealized_pnl DECIMAL(20, 8), -- Current unrealized profit/loss
    unrealized_pnl_pct DECIMAL(10, 4), -- Unrealized PnL percentage
    margin_level DECIMAL(10, 4),   -- Margin level (distance to liquidation)
    entry_price DECIMAL(20, 8),    -- Average entry price
    current_price DECIMAL(20, 8),  -- Current market price
    leverage INTEGER,               -- Leverage used
    side VARCHAR(10),               -- Long or Short

    -- Execution results
    action VARCHAR(20) NOT NULL,   -- managed, skipped, error, opened, closed, added, reduced
    conclusion TEXT,                -- Detailed outcome description

    -- Technical indicators (for context)
    ema_200 DECIMAL(20, 8),
    ema_50 DECIMAL(20, 8),

    -- Performance tracking
    execution_time_ms INTEGER,      -- How long the execution took

    created_at TIMESTAMP DEFAULT NOW()
);

-- Create indexes for fast queries
CREATE INDEX IF NOT EXISTS idx_bot_metrics ON execution_metrics (bot_id, executed_at DESC);
CREATE INDEX IF NOT EXISTS idx_symbol_metrics ON execution_metrics (bot_id, symbol, executed_at DESC);

-- Add comment for documentation
COMMENT ON TABLE execution_metrics IS 'Tracks detailed execution metrics for each bot run including balance, position details, and outcomes for graphing and analysis';
