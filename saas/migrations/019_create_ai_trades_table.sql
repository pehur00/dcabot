-- Migration 019: Create ai_trades table
-- Created: 2025-11-06
-- Reason: Track all executed trades for AI bots (renamed from 017 to run after portfolio_multi_symbol)

CREATE TABLE IF NOT EXISTS ai_trades (
    id SERIAL PRIMARY KEY,
    ai_bot_id INTEGER NOT NULL REFERENCES ai_bots(id) ON DELETE CASCADE,
    ai_decision_id INTEGER REFERENCES ai_decisions(id) ON DELETE SET NULL,
    portfolio_decision_id UUID REFERENCES ai_portfolio_decisions(id) ON DELETE SET NULL,

    -- Trade details
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,  -- 'Buy' or 'Sell'
    action VARCHAR(20) NOT NULL,  -- 'BUY', 'SELL', 'REDUCE', 'CLOSE'
    quantity NUMERIC(20,8) NOT NULL,
    price NUMERIC(20,8) NOT NULL,

    -- Position tracking
    position_value_usd NUMERIC(20,8),
    leverage INTEGER,
    reduce_only BOOLEAN DEFAULT FALSE,

    -- Fees and costs
    trading_fee NUMERIC(20,8),

    -- Order details
    order_id VARCHAR(100),  -- Phemex order ID
    order_type VARCHAR(20) DEFAULT 'Market',

    -- Balance tracking
    balance_before NUMERIC(20,8),
    balance_after NUMERIC(20,8),

    -- Timestamps
    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Additional data
    details JSONB
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_ai_trades_bot_id ON ai_trades(ai_bot_id);
CREATE INDEX IF NOT EXISTS idx_ai_trades_symbol ON ai_trades(symbol);
CREATE INDEX IF NOT EXISTS idx_ai_trades_executed_at ON ai_trades(executed_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_trades_decision_id ON ai_trades(ai_decision_id);

-- Comments
COMMENT ON TABLE ai_trades IS 'All executed trades for AI trading bots';
COMMENT ON COLUMN ai_trades.action IS 'AI decision type: BUY, SELL, REDUCE, CLOSE';
COMMENT ON COLUMN ai_trades.side IS 'Order side: Buy or Sell';
COMMENT ON COLUMN ai_trades.reduce_only IS 'Whether this was a reduce-only order (position exit)';
