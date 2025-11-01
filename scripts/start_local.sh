#!/bin/bash
# Start DCA Bot SaaS locally
export DATABASE_URL="postgresql://dcabot:dcabot_dev_password@localhost:5435/dcabot_dev"
export ENCRYPTION_KEY="f5odR2dgOe8F4q_jo7hy70LIT5zFkt9y9TMkPaC6GYU="
export SECRET_KEY="local-dev-secret"
export DEBUG="True"
export PORT="3030"
export PYTHONPATH="${PWD}:${PYTHONPATH}"

echo "🚀 Starting DCA Bot SaaS..."
echo "📊 PostgreSQL: localhost:5435"
echo "🌐 Web UI: http://localhost:3030"
echo ""

dcabot-env/bin/python saas/app.py
