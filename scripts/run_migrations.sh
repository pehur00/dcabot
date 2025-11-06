#!/bin/bash
# Run database migrations with .env.local configuration

echo "🔄 Running database migrations..."
echo ""

# Load .env.local variables
export $(cat .env.local | grep -v '^#' | xargs)

echo "📊 Database: ${DATABASE_URL}"
echo ""

# Run migrations from project root (so 'saas' module is found)
./dcabot-env/bin/python saas/migrate.py "$@"
