#!/bin/bash
# Run the Flask app locally with .env.local configuration

echo "🚀 Starting DCA Bot SaaS locally..."
echo ""

# Load .env.local variables
export $(cat .env.local | grep -v '^#' | xargs)

# Also load .env for bot-specific variables (like ZHIPU_API_KEY)
export $(cat .env | grep -v '^#' | xargs)

echo "📊 Database: ${DATABASE_URL}"
echo "🔑 Encryption: Loaded"
echo "🌐 Port: ${PORT:-5000}"
echo ""

# Run Flask app from project root (so 'saas' module is found)
./dcabot-env/bin/python -m saas.app
