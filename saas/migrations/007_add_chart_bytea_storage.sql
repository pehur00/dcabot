-- Migration 007: Add bytea column for chart storage
-- This allows storing chart images directly in the database for ephemeral filesystem environments (Render)

-- Add bytea column to store chart image data
ALTER TABLE backtest_results
ADD COLUMN IF NOT EXISTS chart_data BYTEA;

-- Add comment for documentation
COMMENT ON COLUMN backtest_results.chart_data IS 'PNG chart image stored as bytea for ephemeral filesystem compatibility';

-- Create index for faster queries when serving charts
CREATE INDEX IF NOT EXISTS idx_backtest_results_chart_data_not_null
ON backtest_results(id) WHERE chart_data IS NOT NULL;
