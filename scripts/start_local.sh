#!/bin/bash
# Start DCA Bot SaaS locally

# Load environment variables from .env.local if it exists
if [ -f .env.local ]; then
    echo "📝 Loading environment from .env.local"
    set -a
    source .env.local
    set +a
fi

# Set default environment variables (can be overridden by .env.local)
export DATABASE_URL="${DATABASE_URL:-postgresql://dcabot:dcabot_dev_password@localhost:5435/dcabot_dev}"
export ENCRYPTION_KEY="${ENCRYPTION_KEY:-f5odR2dgOe8F4q_jo7hy70LIT5zFkt9y9TMkPaC6GYU=}"
export SECRET_KEY="${SECRET_KEY:-local-dev-secret}"
export DEBUG="${DEBUG:-True}"
export PORT="${PORT:-3030}"
export PYTHONPATH="${PWD}:${PYTHONPATH}"

echo "🚀 Starting DCA Bot SaaS..."
echo "📊 PostgreSQL: localhost:5435"
echo "🌐 Web UI: http://localhost:3030"
echo ""

dcabot-env/bin/python saas/app.py
