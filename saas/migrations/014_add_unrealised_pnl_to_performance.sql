-- Migration 014: Add unrealised_pnl column to ai_model_performance
-- Created: 2025-11-06
-- Reason: Track unrealized PnL from open positions in performance snapshots

ALTER TABLE ai_model_performance
ADD COLUMN IF NOT EXISTS unrealised_pnl NUMERIC(20,8) DEFAULT 0;

COMMENT ON COLUMN ai_model_performance.unrealised_pnl IS 'Total unrealized PnL from all open positions at snapshot time';
