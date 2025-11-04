-- Migration 012: Create AI Bot Tables
-- Date: 2025-11-04
-- Description: Add tables for multi-model AI trading bot system

-- Table 1: AI Model Configurations
CREATE TABLE IF NOT EXISTS ai_model_configs (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    api_endpoint TEXT NOT NULL,
    model_identifier VARCHAR(100) NOT NULL,
    cost_per_1m_input DECIMAL(10, 6),
    cost_per_1m_output DECIMAL(10, 6),
    logo_url TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(provider, model_identifier)
);

-- Seed AI model configurations
INSERT INTO ai_model_configs (name, provider, api_endpoint, model_identifier, cost_per_1m_input, cost_per_1m_output, logo_url, is_active)
VALUES
    ('GLM-4.5-Air', 'z.ai', 'https://api.z.ai/api/paas/v4/chat/completions', 'glm-4.5-air', 0.20, 1.10, '/static/logos/zhipu.png', true),
    ('GLM-4.5-Flash', 'z.ai', 'https://api.z.ai/api/paas/v4/chat/completions', 'glm-4.5-flash', 0.0, 0.0, '/static/logos/zhipu.png', true),
    ('DeepSeek-Chat', 'deepseek', 'https://api.deepseek.com/v1/chat/completions', 'deepseek-chat', 0.27, 1.10, '/static/logos/deepseek.png', true),
    ('Claude-3.5-Sonnet', 'anthropic', 'https://api.anthropic.com/v1/messages', 'claude-3-5-sonnet-20241022', 3.00, 15.00, '/static/logos/anthropic.png', false)
ON CONFLICT (provider, model_identifier) DO NOTHING;

-- Table 2: AI Bots
CREATE TABLE IF NOT EXISTS ai_bots (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    model_config_id INTEGER NOT NULL REFERENCES ai_model_configs(id),
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL CHECK (side IN ('Long', 'Short')),
    leverage INTEGER DEFAULT 5,
    max_position_size DECIMAL(10, 6) DEFAULT 0.03,
    is_active BOOLEAN DEFAULT true,
    automatic_mode BOOLEAN DEFAULT true,

    -- API keys (encrypted)
    exchange_api_key TEXT NOT NULL,
    exchange_api_secret TEXT NOT NULL,
    ai_api_key TEXT NOT NULL,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(user_id, name)
);

CREATE INDEX IF NOT EXISTS idx_ai_bots_user_active ON ai_bots(user_id, is_active);
CREATE INDEX IF NOT EXISTS idx_ai_bots_model ON ai_bots(model_config_id);

-- Table 3: AI Decisions
CREATE TABLE IF NOT EXISTS ai_decisions (
    id SERIAL PRIMARY KEY,
    ai_bot_id INTEGER NOT NULL REFERENCES ai_bots(id) ON DELETE CASCADE,
    symbol VARCHAR(20) NOT NULL,

    -- Market data at decision time
    current_price DECIMAL(20, 8),
    ema20_1m DECIMAL(20, 8),
    ema50_5m DECIMAL(20, 8),
    ema100_1h DECIMAL(20, 8),
    rsi_14 DECIMAL(5, 2),
    volume_trend VARCHAR(50),
    trend_description TEXT,

    -- AI Decision
    decision VARCHAR(10) NOT NULL CHECK (decision IN ('BUY', 'SELL', 'HOLD')),
    confidence INTEGER CHECK (confidence >= 0 AND confidence <= 100),
    reasoning TEXT NOT NULL,
    risk_level VARCHAR(10) CHECK (risk_level IN ('LOW', 'MEDIUM', 'HIGH')),
    stop_loss DECIMAL(20, 8),
    take_profit DECIMAL(20, 8),

    -- Action taken
    action_taken VARCHAR(20) DEFAULT 'PENDING' CHECK (action_taken IN ('PENDING', 'EXECUTED', 'SKIPPED', 'MANUAL_OVERRIDE')),
    skip_reason TEXT,
    trade_id INTEGER REFERENCES trades(id) ON DELETE SET NULL,

    -- Model performance
    input_tokens INTEGER,
    output_tokens INTEGER,
    api_cost DECIMAL(10, 6),
    response_time_ms INTEGER,

    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ai_decisions_bot ON ai_decisions(ai_bot_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_decisions_action ON ai_decisions(action_taken, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_decisions_symbol ON ai_decisions(symbol, created_at DESC);

-- Table 4: AI Model Performance Snapshots
CREATE TABLE IF NOT EXISTS ai_model_performance (
    id SERIAL PRIMARY KEY,
    ai_bot_id INTEGER NOT NULL REFERENCES ai_bots(id) ON DELETE CASCADE,
    model_config_id INTEGER NOT NULL REFERENCES ai_model_configs(id),

    -- Snapshot metrics
    balance DECIMAL(20, 8),
    pnl_percentage DECIMAL(10, 4),
    pnl_amount DECIMAL(20, 8),
    total_trades INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    losing_trades INTEGER DEFAULT 0,
    win_rate DECIMAL(5, 2),

    -- Position info
    open_positions INTEGER DEFAULT 0,
    total_position_value DECIMAL(20, 8),

    -- Cost tracking
    total_api_cost DECIMAL(10, 4) DEFAULT 0,
    total_api_calls INTEGER DEFAULT 0,

    snapshot_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ai_performance_bot ON ai_model_performance(ai_bot_id, snapshot_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_performance_model ON ai_model_performance(model_config_id, snapshot_at DESC);

-- Add comment for tracking
COMMENT ON TABLE ai_model_configs IS 'Configuration for AI models (GLM, DeepSeek, Claude, etc.)';
COMMENT ON TABLE ai_bots IS 'User AI trading bots with model selection';
COMMENT ON TABLE ai_decisions IS 'Logged AI decisions with reasoning and market data';
COMMENT ON TABLE ai_model_performance IS 'Performance snapshots for AI model comparison';
