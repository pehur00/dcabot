-- Migration 013: Fix ai_decisions.trade_id to support UUID strings
-- Created: 2025-11-06
-- Reason: Phemex returns UUID strings for order IDs, not integers

-- Drop the foreign key constraint
ALTER TABLE ai_decisions
DROP CONSTRAINT IF EXISTS ai_decisions_trade_id_fkey;

-- Change trade_id from INTEGER to VARCHAR(100) to support UUID strings
ALTER TABLE ai_decisions
ALTER COLUMN trade_id TYPE VARCHAR(100);

-- Add comment explaining the change
COMMENT ON COLUMN ai_decisions.trade_id IS 'Phemex order ID (UUID string from API response)';
