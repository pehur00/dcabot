-- Migration 015: Add AI position sizing and leverage decisions to ai_decisions
-- Date: 2025-11-05
-- Description: Store AI's position_size_pct and leverage choices for analysis

ALTER TABLE ai_decisions
ADD COLUMN IF NOT EXISTS position_size_pct DECIMAL(5, 4),
ADD COLUMN IF NOT EXISTS leverage_used INTEGER;

COMMENT ON COLUMN ai_decisions.position_size_pct IS 'AI decided position size as % of balance (e.g., 0.03 = 3%)';
COMMENT ON COLUMN ai_decisions.leverage_used IS 'AI decided leverage multiplier (e.g., 3 = 3x)';
