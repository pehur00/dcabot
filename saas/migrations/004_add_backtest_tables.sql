-- Migration: Add backtest tables and weekly performance tracking
-- Date: 2025-11-02
-- Description: Tables for storing weekly backtest results to display on front page
--
-- This migration adds:
-- - backtest_configs: Which symbols to test weekly
-- - backtest_results: Weekly backtest outcomes with metrics
-- - backtest_trades: Detailed trade logs for each backtest
-- - Default symbol configuration (10 major symbols)

-- Stores which symbols to test weekly
CREATE TABLE IF NOT EXISTS backtest_configs (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(50) NOT NULL UNIQUE,
    side VARCHAR(10) NOT NULL,
    leverage INTEGER DEFAULT 10,
    interval INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT true,
    category VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Stores weekly backtest outcomes
CREATE TABLE IF NOT EXISTS backtest_results (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(50) NOT NULL,
    side VARCHAR(10) NOT NULL,
    leverage INTEGER NOT NULL,
    interval INTEGER NOT NULL,
    test_period_days INTEGER NOT NULL,
    start_date TIMESTAMP NOT NULL,
    end_date TIMESTAMP NOT NULL,
    initial_balance DECIMAL(20,8) NOT NULL,
    final_balance DECIMAL(20,8) NOT NULL,
    profit_loss DECIMAL(20,8) NOT NULL,
    profit_loss_pct DECIMAL(10,4) NOT NULL,
    max_drawdown_pct DECIMAL(10,4),
    total_trades INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    losing_trades INTEGER DEFAULT 0,
    win_rate DECIMAL(5,2),
    max_position_size DECIMAL(20,8),
    max_margin_used_pct DECIMAL(5,2),
    liquidation_occurred BOOLEAN DEFAULT false,
    executed_at TIMESTAMP DEFAULT NOW(),
    execution_duration_seconds INTEGER,
    data_source VARCHAR(50),
    status VARCHAR(20) DEFAULT 'completed',
    error_message TEXT
);

-- Detailed trade log for each backtest
CREATE TABLE IF NOT EXISTS backtest_trades (
    id SERIAL PRIMARY KEY,
    backtest_result_id INTEGER REFERENCES backtest_results(id) ON DELETE CASCADE,
    trade_number INTEGER NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    action VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,
    price DECIMAL(20,8) NOT NULL,
    quantity DECIMAL(20,8) NOT NULL,
    position_size DECIMAL(20,8),
    balance DECIMAL(20,8),
    pnl DECIMAL(20,8),
    margin_level DECIMAL(10,4)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_backtest_configs_active ON backtest_configs(is_active);
CREATE INDEX IF NOT EXISTS idx_backtest_configs_category ON backtest_configs(category);
CREATE INDEX IF NOT EXISTS idx_backtest_results_symbol ON backtest_results(symbol);
CREATE INDEX IF NOT EXISTS idx_backtest_results_executed_at ON backtest_results(executed_at DESC);
CREATE INDEX IF NOT EXISTS idx_backtest_results_status ON backtest_results(status);
CREATE INDEX IF NOT EXISTS idx_backtest_results_symbol_executed ON backtest_results(symbol, executed_at DESC);
CREATE INDEX IF NOT EXISTS idx_backtest_trades_result_id ON backtest_trades(backtest_result_id);

-- Unique constraint: one backtest per symbol/side/leverage per day
CREATE UNIQUE INDEX IF NOT EXISTS idx_backtest_results_unique_daily
ON backtest_results(symbol, side, leverage, (executed_at::date));

-- Trigger for updated_at on backtest_configs
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'update_backtest_configs_updated_at') THEN
        CREATE TRIGGER update_backtest_configs_updated_at BEFORE UPDATE ON backtest_configs
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;
END $$;

-- Insert default symbols to test weekly (idempotent)
INSERT INTO backtest_configs (symbol, side, leverage, interval, category) VALUES
    ('BTCUSDT', 'Long', 10, 1, 'major'),
    ('ETHUSDT', 'Long', 10, 1, 'major'),
    ('SOLUSDT', 'Long', 10, 1, 'major'),
    ('BNBUSDT', 'Long', 10, 1, 'major'),
    ('ADAUSDT', 'Long', 10, 1, 'altcoin'),
    ('DOGEUSDT', 'Long', 10, 1, 'altcoin'),
    ('AVAXUSDT', 'Long', 10, 1, 'altcoin'),
    ('MATICUSDT', 'Long', 10, 1, 'altcoin'),
    ('u1000PEPEUSDT', 'Long', 10, 1, 'meme'),
    ('SHIBUSDT', 'Long', 10, 1, 'meme')
ON CONFLICT (symbol) DO NOTHING;
