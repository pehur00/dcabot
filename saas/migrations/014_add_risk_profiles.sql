-- Migration 014: Add risk profiles and AI autonomy
-- Allows AI to make intelligent decisions about leverage, position size, and symbol selection

-- Update DeepSeek model name to V3
UPDATE ai_model_configs
SET name = 'DeepSeek-V3'
WHERE provider = 'deepseek' AND model_identifier = 'deepseek-chat';

-- Add risk profile to ai_bots
ALTER TABLE ai_bots
ADD COLUMN IF NOT EXISTS risk_profile VARCHAR(20) DEFAULT 'moderate'
    CHECK (risk_profile IN ('conservative', 'moderate', 'aggressive', 'custom'));

-- Add allowed symbols (AI chooses which to trade)
ALTER TABLE ai_bots
ADD COLUMN IF NOT EXISTS allowed_symbols TEXT[] DEFAULT ARRAY['BTCUSDT'];

-- Rename columns to reflect they are LIMITS not fixed values
DO $$
BEGIN
    -- Rename leverage to max_leverage (if not already renamed)
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'ai_bots' AND column_name = 'leverage'
    ) THEN
        ALTER TABLE ai_bots RENAME COLUMN leverage TO max_leverage;
    END IF;

    -- max_position_size already has "max" prefix, keep as is
END $$;

-- Add comments explaining the new approach
COMMENT ON COLUMN ai_bots.risk_profile IS 'Risk profile: conservative (1-2x, 1-3%), moderate (2-5x, 2-5%), aggressive (5-10x, 3-10%), custom (user-defined)';
COMMENT ON COLUMN ai_bots.allowed_symbols IS 'Array of symbols AI can trade (e.g., {BTCUSDT, ETHUSDT}). AI decides which to trade and when.';
COMMENT ON COLUMN ai_bots.max_leverage IS 'Maximum leverage AI can use (AI decides actual leverage per trade with reasoning)';
COMMENT ON COLUMN ai_bots.max_position_size IS 'Maximum position size as % of balance (AI decides actual size per trade with reasoning)';
COMMENT ON COLUMN ai_bots.symbol IS 'DEPRECATED: Now AI chooses from allowed_symbols. This field kept for backward compatibility.';
COMMENT ON COLUMN ai_bots.side IS 'DEPRECATED: Now AI decides Long/Short per trade. This field kept for backward compatibility.';
