#!/bin/bash
# AI Bot Executor - Runs all active AI bots
# This fetches market data, sends to AI models, and logs decisions

set -e

echo "🤖 Running AI Bot Executor..."
echo ""

# Load environment variables
export $(cat .env.local | grep -v '^#' | xargs)
export $(cat .env | grep -v '^#' | xargs)

# Run executor
./dcabot-env/bin/python saas/execute_ai_bots.py

echo ""
echo "✅ Executor completed"
echo "💡 Check dashboard at http://localhost:3030/ai-bots to see results"
