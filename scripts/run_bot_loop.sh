#!/bin/bash
#
# Continuous Bot Execution Loop
#
# This script runs the bot executor continuously, executing all active bots
# every 5 minutes (matching the production Render cron schedule).
#
# Usage:
#   ./scripts/run_bot_loop.sh        # Run with 5 minute interval (default)
#   ./scripts/run_bot_loop.sh 60     # Run with 1 minute interval (for testing)
#

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get interval from argument or default to 300 seconds (5 minutes)
INTERVAL=${1:-300}
INTERVAL_MIN=$((INTERVAL / 60))

# Setup environment
export DATABASE_URL="postgresql://dcabot:dcabot_dev_password@localhost:5435/dcabot_dev"
export ENCRYPTION_KEY="f5odR2dgOe8F4q_jo7hy70LIT5zFkt9y9TMkPaC6GYU="
export PYTHONPATH="${PWD}:${PYTHONPATH}"

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}🔄 DCA Bot Continuous Execution Loop${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo
echo -e "${YELLOW}⏰ Interval:${NC} ${INTERVAL}s (${INTERVAL_MIN} minute(s))"
echo -e "${YELLOW}🌐 Web UI:${NC} http://localhost:3030"
echo -e "${YELLOW}🛑 Stop:${NC} Press Ctrl+C"
echo
echo -e "${GREEN}Starting execution loop...${NC}"
echo

CYCLE=0

# Function to run on exit
cleanup() {
    echo
    echo -e "${YELLOW}🛑 Stopping execution loop...${NC}"
    echo -e "${GREEN}✅ Completed $CYCLE execution cycle(s)${NC}"
    echo
    exit 0
}

# Trap Ctrl+C
trap cleanup SIGINT SIGTERM

while true; do
    CYCLE=$((CYCLE + 1))
    START_TIME=$(date +%s)
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}🤖 Cycle #${CYCLE} - ${TIMESTAMP}${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo

    # Execute all active bots
    if dcabot-env/bin/python saas/execute_all_bots.py; then
        RESULT="✅ SUCCESS"
        RESULT_COLOR=$GREEN
    else
        RESULT="❌ FAILED"
        RESULT_COLOR=$RED
    fi

    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))

    echo
    echo -e "${RESULT_COLOR}${RESULT}${NC} (execution took ${DURATION}s)"
    echo

    # Calculate next run time
    NEXT_RUN=$((INTERVAL - DURATION))
    if [ $NEXT_RUN -lt 0 ]; then
        NEXT_RUN=0
    fi

    if [ $NEXT_RUN -gt 0 ]; then
        NEXT_RUN_TIME=$(date -v+${NEXT_RUN}S '+%H:%M:%S' 2>/dev/null || date -d "+${NEXT_RUN} seconds" '+%H:%M:%S' 2>/dev/null || echo "in ${NEXT_RUN}s")
        echo -e "${YELLOW}⏳ Next run at: ${NEXT_RUN_TIME}${NC}"
        echo
        sleep $NEXT_RUN
    fi
done
