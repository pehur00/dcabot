#!/bin/bash
# Reset AI bots - clear historical data but keep configurations

cd "$(dirname "$0")/.."

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Run the Python script
PYTHONPATH=. dcabot-env/bin/python saas/reset_bots.py "$@"
