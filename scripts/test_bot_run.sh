#!/bin/bash
#
# Test Bot Execution Script
#
# This script executes a single bot once to test the SaaS bot execution system.
# It shows you exactly what happens when the bot runs, including logs and database updates.
#
# Usage:
#   ./scripts/test_bot_run.sh              # List all bots
#   ./scripts/test_bot_run.sh <bot_id>     # Run specific bot
#

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Setup environment
export DATABASE_URL="postgresql://dcabot:dcabot_dev_password@localhost:5435/dcabot_dev"
export ENCRYPTION_KEY="f5odR2dgOe8F4q_jo7hy70LIT5zFkt9y9TMkPaC6GYU="
export PYTHONPATH="${PWD}:${PYTHONPATH}"

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}🤖 DCA Bot Test Execution${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo

# Function to list all bots
list_bots() {
    echo -e "${YELLOW}📋 Available Bots:${NC}"
    dcabot-env/bin/python -c "
from saas.database import get_db
with get_db() as conn:
    cursor = conn.cursor()
    cursor.execute('''
        SELECT b.id, b.name, b.exchange, b.testnet, b.status, u.email,
               COUNT(tp.id) as pair_count
        FROM bots b
        JOIN users u ON b.user_id = u.id
        LEFT JOIN trading_pairs tp ON b.id = tp.bot_id AND tp.is_active = true
        GROUP BY b.id, b.name, b.exchange, b.testnet, b.status, u.email
        ORDER BY b.id
    ''')
    bots = cursor.fetchall()

    if not bots:
        print('  No bots found in database')
        exit(1)

    print()
    print('  ID  | Bot Name        | Exchange | Mode    | Status  | Email                | Pairs')
    print('  ' + '-' * 85)
    for bot in bots:
        bot_id, name, exchange, testnet, status, email, pair_count = bot
        mode = 'Testnet' if testnet else 'Mainnet'
        status_icon = '▶️ ' if status == 'running' else '⏸️ '
        # Truncate email if too long
        email_short = email[:20] if len(email) > 20 else email
        print(f'  {bot_id:<3} | {name:<15} | {exchange:<8} | {mode:<7} | {status_icon}{status:<6} | {email_short:<20} | {pair_count}')
    print()
"
}

# Function to show bot details
show_bot_details() {
    local bot_id=$1
    echo -e "${YELLOW}🔍 Bot Details (ID: $bot_id):${NC}"
    dcabot-env/bin/python -c "
from saas.database import get_db
bot_id = $bot_id

with get_db() as conn:
    cursor = conn.cursor()

    # Get bot info
    cursor.execute('''
        SELECT b.name, b.exchange, b.testnet, b.status, u.email
        FROM bots b
        JOIN users u ON b.user_id = u.id
        WHERE b.id = %s
    ''', (bot_id,))
    bot = cursor.fetchone()

    if not bot:
        print(f'  ❌ Bot {bot_id} not found')
        exit(1)

    name, exchange, testnet, status, email = bot
    mode = 'Testnet' if testnet else 'Mainnet'

    print(f'  Name:     {name}')
    print(f'  Exchange: {exchange}')
    print(f'  Mode:     {mode}')
    print(f'  Status:   {status}')
    print(f'  Owner:    {email}')

    # Get trading pairs
    cursor.execute('''
        SELECT symbol, side, leverage, ema_interval, automatic_mode, is_active
        FROM trading_pairs
        WHERE bot_id = %s
    ''', (bot_id,))
    pairs = cursor.fetchall()

    if pairs:
        print(f'\n  Trading Pairs:')
        for symbol, side, leverage, ema, auto, active in pairs:
            status_icon = '✓' if active else '✗'
            auto_text = 'Auto' if auto else 'Manual'
            print(f'    {status_icon} {symbol} | {side} | {leverage}x leverage | {ema}m EMA | {auto_text}')
    else:
        print('\n  ⚠️  No trading pairs configured')

    print()
"
}

# Function to execute bot
execute_bot() {
    local bot_id=$1

    echo -e "${GREEN}▶️  Executing Bot ID: $bot_id${NC}"
    echo

    # Record start time
    START_TIME=$(date +%s)

    # Execute the bot executor (which will run main.py with BOT_ID)
    export BOT_ID=$bot_id

    echo -e "${BLUE}━━━━━━━━━━━ Bot Execution Output ━━━━━━━━━━━${NC}"
    if dcabot-env/bin/python saas/execute_all_bots.py; then
        RESULT="✅ SUCCESS"
        RESULT_COLOR=$GREEN
    else
        RESULT="❌ FAILED"
        RESULT_COLOR=$RED
    fi
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    # Calculate execution time
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))

    echo
    echo -e "${RESULT_COLOR}$RESULT${NC} (${DURATION}s)"
    echo
}

# Function to show recent logs
show_recent_logs() {
    local bot_id=$1
    echo -e "${YELLOW}📊 Recent Bot Logs (Last 10):${NC}"
    dcabot-env/bin/python -c "
from saas.database import get_db
bot_id = $bot_id

with get_db() as conn:
    cursor = conn.cursor()
    cursor.execute('''
        SELECT created_at, level, message
        FROM bot_logs
        WHERE bot_id = %s
        ORDER BY created_at DESC
        LIMIT 10
    ''', (bot_id,))
    logs = cursor.fetchall()

    if logs:
        for created_at, level, message in logs:
            timestamp = created_at.strftime('%H:%M:%S')
            level_icon = '✅' if level == 'INFO' else '❌' if level == 'ERROR' else '⚠️'
            print(f'  {timestamp} {level_icon} {level:8} | {message}')
    else:
        print('  No logs yet')

    print()
"
}

# Main script logic
if [ -z "$1" ]; then
    # No bot ID provided - list all bots
    list_bots
    echo -e "${YELLOW}💡 Usage:${NC} ./scripts/test_bot_run.sh <bot_id>"
    echo
    exit 0
fi

BOT_ID=$1

# Show bot details
show_bot_details $BOT_ID

# Ask for confirmation
echo -e "${YELLOW}🚀 Ready to execute this bot?${NC}"
read -p "Press Enter to continue, or Ctrl+C to cancel... "
echo

# Execute the bot
execute_bot $BOT_ID

# Show results
show_recent_logs $BOT_ID

echo -e "${GREEN}✅ Test execution complete!${NC}"
echo
echo -e "${BLUE}💡 Next steps:${NC}"
echo "  • Check the Web UI at http://localhost:3030 to see updated logs"
echo "  • Run './scripts/test_bot_run.sh $BOT_ID' again to execute another cycle"
echo "  • Use './scripts/run_bot_loop.sh' to run continuously every 5 minutes"
echo
