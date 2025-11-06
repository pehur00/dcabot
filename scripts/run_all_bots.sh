#!/bin/bash
# Unified Bot Executor - Runs ALL active bots (Martingale + AI)
# Part 1: Martingale/DCA strategy bots
# Part 2: AI trading bots

set -e

echo "🤖 Running Unified Bot Executor (Martingale + AI)..."
echo ""

# Load environment variables
export $(cat .env.local | grep -v '^#' | xargs)
export $(cat .env | grep -v '^#' | xargs)

# Run executor
./dcabot-env/bin/python saas/execute_all_bots.py

echo ""
echo "✅ Executor completed"
echo "💡 Check dashboard at http://localhost:3030/bots to see results"
