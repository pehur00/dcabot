-- Migration 018: Switch to OpenRouter-only with dynamic model sync
-- Date: 2025-11-06
-- Description: Remove old provider-specific models and configurations, prepare for OpenRouter-only approach

-- 1. Add OpenRouter API key to users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS openrouter_api_key TEXT;

-- 2. Add columns to ai_model_configs for dynamic model data
ALTER TABLE ai_model_configs ADD COLUMN IF NOT EXISTS context_length INTEGER DEFAULT 0;
ALTER TABLE ai_model_configs ADD COLUMN IF NOT EXISTS category VARCHAR(50) DEFAULT 'general';
ALTER TABLE ai_model_configs ADD COLUMN IF NOT EXISTS performance_tier VARCHAR(20) DEFAULT 'standard';
ALTER TABLE ai_model_configs ADD COLUMN IF NOT EXISTS synced_at TIMESTAMP;

-- 3. Increase precision of cost columns to accommodate higher prices (up to $999,999,999,999)
ALTER TABLE ai_model_configs ALTER COLUMN cost_per_1m_input TYPE DECIMAL(20, 8);
ALTER TABLE ai_model_configs ALTER COLUMN cost_per_1m_output TYPE DECIMAL(20, 8);

-- 4. Drop the ai_api_key column from ai_bots (will use user's openrouter_api_key instead)
-- Note: Keeping this column for now to preserve existing bot data during migration
-- ALTER TABLE ai_bots DROP COLUMN IF EXISTS ai_api_key;
-- Instead, we'll add a comment for future cleanup
COMMENT ON COLUMN ai_bots.ai_api_key IS 'DEPRECATED: Will be removed in future migration. Use users.openrouter_api_key instead.';

-- 5. Mark old provider models as inactive (don't delete yet for safety)
UPDATE ai_model_configs
SET is_active = false
WHERE provider IN ('z.ai', 'deepseek', 'anthropic', 'google');

-- 6. Add comment to explain the change
COMMENT ON TABLE ai_model_configs IS 'AI model configurations. Models are synced daily from OpenRouter API. Old provider-specific models (z.ai, deepseek, anthropic, google) are marked inactive.';

-- 7. Create index for faster model queries
CREATE INDEX IF NOT EXISTS idx_ai_models_category ON ai_model_configs(category, is_active);
CREATE INDEX IF NOT EXISTS idx_ai_models_provider_active ON ai_model_configs(provider, is_active);
CREATE INDEX IF NOT EXISTS idx_ai_models_synced ON ai_model_configs(synced_at DESC) WHERE is_active = true;
