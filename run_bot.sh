#!/bin/bash

# Activate virtual environment and run the bot
# Usage: ./run_bot.sh

cd "$(dirname "$0")"

# Check if virtual environment exists
if [ ! -d "dcabot-env" ]; then
    echo "❌ Virtual environment not found. Creating it..."
    python3 -m venv dcabot-env
    echo "📦 Installing dependencies..."
    dcabot-env/bin/pip install -r requirements.txt
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "❌ .env file not found. Please create one based on .env.example"
    exit 1
fi

echo "🚀 Starting Martingale Trading Bot..."
echo "📊 Trading on: $(grep SYMBOL .env | cut -d'=' -f2)"
echo "🌐 Network: $(grep TESTNET .env | cut -d'=' -f2 | grep -q True && echo 'Testnet ✅' || echo 'Mainnet ⚠️')"
echo ""

# Activate and run
source dcabot-env/bin/activate
python main.py
