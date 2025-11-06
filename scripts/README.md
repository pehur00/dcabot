# Scripts Directory

**Last Updated:** December 2024

This directory contains utility scripts for running, testing, and managing the DCABot SaaS platform.

---

## Quick Reference

| Script | Purpose | Usage |
|--------|---------|-------|
| `run_local_app.sh` | Start Flask web app | `./scripts/run_local_app.sh` |
| `run_migrations.sh` | Apply database migrations | `./scripts/run_migrations.sh` |
| `run_executor.sh` | Execute AI bots manually | `./scripts/run_executor.sh` |
| `run_all_bots.sh` | Execute all bots (Martingale + AI) | `./scripts/run_all_bots.sh` |
| `reset_bots.sh` | Reset AI bot data | `./scripts/reset_bots.sh` |
| `test_bot_run.sh` | Test single bot execution | `./scripts/test_bot_run.sh <bot_id>` |
| `run_bot_loop.sh` | Continuous execution loop | `./scripts/run_bot_loop.sh [interval_seconds]` |
| `start_local.sh` | Legacy Flask starter | `./scripts/start_local.sh` |
| `run_bot.sh` | Legacy standalone bot | `./scripts/run_bot.sh` |

---

## Web Application Scripts

### `run_local_app.sh` ⭐ **Primary Dev Server**
Starts the Flask web application for local development.

**Usage:**
```bash
./scripts/run_local_app.sh
```

**What it does:**
1. Loads environment variables from `.env.local` (Flask config)
2. Loads environment variables from `.env` (legacy bot credentials)
3. Sets `PYTHONPATH` to project root
4. Runs database migrations automatically
5. Starts Flask on port 3030 with debug mode

**Access:** http://localhost:3030

**Environment Variables Required:**
- `DATABASE_URL` - PostgreSQL connection string
- `ENCRYPTION_KEY` - Fernet encryption key
- `SECRET_KEY` - Flask session secret
- `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` - OAuth credentials

---

### `start_local.sh` (Legacy)
Alternative Flask starter script.

**Differences from `run_local_app.sh`:**
- Doesn't auto-run migrations
- Simpler setup (fewer env var checks)

---

## Database Scripts

### `run_migrations.sh`
Applies pending database migrations.

**Usage:**
```bash
# Run migrations
./scripts/run_migrations.sh

# Check migration status
./scripts/run_migrations.sh --status
```

**What it does:**
- Sets up database environment variables
- Runs `saas/migrate.py` to apply migrations
- Shows status of applied vs pending migrations

**Output:**
```
🚀 Starting database migrations...
✅ Migrations tracking table ready
📋 Found 2 pending migration(s)
📝 Applying migration: 017_add_ai_bot_trades.sql
✅ Successfully applied: 017_add_ai_bot_trades.sql
🎉 Database is now up to date!
```

---

## Bot Execution Scripts

### `run_executor.sh` ⭐ **AI Bots Only**
Executes all active AI trading bots once.

**Usage:**
```bash
./scripts/run_executor.sh
```

**What it does:**
1. Sets environment variables
2. Runs `saas/execute_ai_bots.py`
3. Executes all AI bots with `status='running'`
4. Logs decisions and trades to database

**Use this when:**
- Testing AI bot configuration
- Debugging AI bot logic
- Verifying API keys work
- Running bots manually without cron

---

### `run_all_bots.sh` ⭐ **All Bots (Martingale + AI)**
Executes both Martingale and AI trading bots once.

**Usage:**
```bash
./scripts/run_all_bots.sh
```

**What it does:**
1. Runs `saas/execute_all_bots.py` (Martingale bots)
2. Runs `saas/execute_ai_bots.py` (AI bots)
3. Sequential execution (Martingale first, then AI)

**Use this when:**
- Testing full system execution
- Simulating production cron behavior
- Running all bots together

---

### `run_bot_loop.sh` ⭐ **Continuous Execution**
Continuously executes all active bots at specified interval (simulates production).

**Usage:**
```bash
# Run with default 5 minute interval (matches production)
./scripts/run_bot_loop.sh

# Run with custom interval (e.g., 60 seconds for testing)
./scripts/run_bot_loop.sh 60
```

**What it does:**
- Runs `saas/execute_all_bots.py` in an infinite loop
- Executes all bots with `status='running'`
- Shows cycle number, timing, and results
- Press Ctrl+C to stop

**Use this when:**
- Testing continuous execution locally
- Simulating production Render cron behavior
- Running multiple bots simultaneously over time

**Output:**
```
════════════════════════════════════════════════
Cycle #1 started at 2024-12-06 10:00:00
════════════════════════════════════════════════
Executing Martingale bots...
Executing AI bots...
════════════════════════════════════════════════
Cycle #1 completed (duration: 12.3s)
Next cycle in 5 minutes (10:05:00)
════════════════════════════════════════════════
```

---

### `run_bot.sh` (Legacy)
Original single-bot execution script from before SaaS transformation.

**Usage:**
```bash
./scripts/run_bot.sh
```

**Still useful for:**
- Running bot without database
- Quick testing with `config.json`
- Standalone bot execution (no SaaS platform)

---

## Testing Scripts

### `test_bot_run.sh` ⭐ **Recommended for Testing**
Executes a single bot once to test the execution system.

**Usage:**
```bash
# List all available bots
./scripts/test_bot_run.sh

# Execute a specific bot
./scripts/test_bot_run.sh 1
```

**What it does:**
1. Queries database for bot details (name, exchange, trading pairs)
2. Shows bot configuration
3. Asks for confirmation
4. Executes the bot once
5. Shows execution logs from stdout
6. Displays recent activity from database (`bot_logs` table)

**Perfect for:**
- Testing bot configuration after creation
- Debugging execution issues
- Verifying API keys work correctly
- Checking trading logic for specific bot

**Example Output:**
```
═══════════════════════════════════════════════
Bot #1: My Test Bot (Phemex Testnet)
═══════════════════════════════════════════════
Trading Pairs:
  • BTCUSDT (Long, 10x leverage)
  • ETHUSDT (Short, 5x leverage)

Execute this bot? (y/n): y

🚀 Executing bot...
[Execution logs...]

═══════════════════════════════════════════════
Recent Activity (Last 5 executions):
═══════════════════════════════════════════════
2024-12-06 10:00:00 | ✅ SUCCESS | Opened position BTCUSDT
2024-12-06 09:55:00 | ✅ SUCCESS | Added to ETHUSDT position
```

---

### `test_leverages.sh`
Tests different leverage settings across multiple timeframes.

**Usage:**
```bash
./scripts/test_leverages.sh
```

**Use for:**
- Backtesting strategy with various leverage levels
- Finding optimal leverage for risk/reward

---

### `test_db_connection.py`
Tests database connectivity and queries sample data.

**Usage:**
```bash
export DATABASE_URL="postgresql://dcabot:dcabot_dev_password@localhost:5435/dcabot_dev"
python scripts/test_db_connection.py
```

**Use for:**
- Verifying database connection works
- Testing database credentials
- Debugging connection issues

---

### `test_top_coins.py`
Backtests the Martingale strategy across multiple top cryptocurrencies.

**Usage:**
```bash
python scripts/test_top_coins.py --days 7 --leverage 10
```

**Options:**
- `--days` - Number of days to backtest (default: 7)
- `--leverage` - Leverage multiplier (default: 10)
- Tests strategy on top market cap coins (BTC, ETH, etc.)

**Use for:**
- Evaluating strategy performance across different symbols
- Identifying best-performing symbols

---

## Maintenance Scripts

### `reset_bots.sh`
Resets AI bot data (decisions, trades, performance history).

**Usage:**
```bash
./scripts/reset_bots.sh
```

**What it does:**
- Truncates `ai_decisions` table
- Truncates `ai_bot_trades` table
- Truncates `ai_model_performance` table
- Keeps bot configuration intact

**⚠️ WARNING:** This permanently deletes all AI bot history. Use with caution.

**Use this when:**
- Starting fresh after testing
- Clearing test data before production
- Resetting performance metrics

---

## Environment Setup

All bot execution scripts automatically set these environment variables:

```bash
export DATABASE_URL="postgresql://dcabot:dcabot_dev_password@localhost:5435/dcabot_dev"
export ENCRYPTION_KEY="your-encryption-key-here"
export PYTHONPATH="${PWD}:${PYTHONPATH}"
```

### Manual Environment Setup

If running Python scripts directly:

```bash
# Load Flask configuration
export $(cat .env.local | grep -v '^#' | xargs)

# Load bot credentials (legacy)
export $(cat .env | grep -v '^#' | xargs)

# Set Python path
export PYTHONPATH="${PWD}:${PYTHONPATH}"

# Run script
python saas/execute_ai_bots.py
```

---

## Quick Start Guide

### 1. Start Local Development Environment

```bash
# Terminal 1: Start PostgreSQL (if not running)
docker run -d --name dcabot-db \
  -e POSTGRES_USER=dcabot \
  -e POSTGRES_PASSWORD=dcabot_dev_password \
  -e POSTGRES_DB=dcabot_dev \
  -p 5435:5432 postgres:15

# Terminal 2: Start Flask Web UI
./scripts/run_local_app.sh
```

Open http://localhost:3030 in your browser.

---

### 2. Create a Bot

1. Register/login at http://localhost:3030
2. Click "Add New Bot"
3. Configure:
   - Exchange: Phemex
   - API credentials
   - Testnet mode (recommended for testing)
4. Add trading pairs:
   - Symbol: BTCUSDT
   - Side: Long
   - Leverage: 10x
   - Auto Mode: Yes
5. Start the bot

---

### 3. Test Bot Execution

```bash
# List your bots
./scripts/test_bot_run.sh

# Execute bot ID 1
./scripts/test_bot_run.sh 1
```

---

### 4. Run Continuously (Optional)

```bash
# Run all active bots every 5 minutes (matches production)
./scripts/run_bot_loop.sh

# Or run with 1 minute interval for faster testing
./scripts/run_bot_loop.sh 60
```

---

## Production vs Local

| Aspect | Local Development | Production (Render) |
|--------|------------------|---------------------|
| Web UI | `./scripts/run_local_app.sh` | Gunicorn + auto-deploy |
| Bot Execution | `./scripts/run_bot_loop.sh` | Render Cron Jobs (every 5 min) |
| Database | Docker PostgreSQL (port 5435) | Managed PostgreSQL |
| Scheduling | Manual loop script | Automatic cron schedule |
| Logs | Console + database | Database + Render logs |
| Migrations | `./scripts/run_migrations.sh` | Auto-run during build |

---

## Troubleshooting

### Port Already in Use
```bash
lsof -ti:3030 | xargs kill -9
./scripts/run_local_app.sh
```

---

### Database Connection Failed
```bash
# Check if PostgreSQL is running
docker ps | grep dcabot-db

# Start if not running
docker start dcabot-db

# Test connection
psql postgresql://dcabot:dcabot_dev_password@localhost:5435/dcabot_dev -c "SELECT 1"
```

---

### Import Errors ("No module named 'saas'")
```bash
# Always run scripts from project root
cd /path/to/dcabot
./scripts/run_local_app.sh

# NOT from inside scripts/
cd scripts && ./run_local_app.sh  # ❌ Wrong!
```

---

### Flask Not Reloading
Flask auto-reloads in debug mode when files change. If stuck:
```bash
lsof -ti:3030 | xargs kill -9
./scripts/run_local_app.sh
```

---

### Migration Errors
```bash
# Check migration status
./scripts/run_migrations.sh --status

# View last few migrations
psql $DATABASE_URL -c "SELECT * FROM schema_migrations ORDER BY applied_at DESC LIMIT 5;"
```

---

### Bot Not Executing
**Check:**
1. Bot status is "running" (not "stopped")
2. Database connection works
3. API keys are valid
4. Trading pair has `automatic_mode = TRUE`

**Debug:**
```bash
# Test single bot execution
./scripts/test_bot_run.sh 1

# Check recent logs
psql $DATABASE_URL -c "SELECT * FROM bot_logs ORDER BY created_at DESC LIMIT 10;"
```

---

## Script Maintenance

### Adding New Scripts
1. Create script in `/scripts` directory
2. Make executable: `chmod +x scripts/your_script.sh`
3. Add description to this README
4. Test from project root: `./scripts/your_script.sh`

### Environment Variables
All scripts should:
- Load `.env.local` for Flask/SaaS configuration
- Set `PYTHONPATH` to project root
- Handle missing environment variables gracefully

**Template:**
```bash
#!/bin/bash
set -e  # Exit on error

# Get project root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Load environment
if [ -f ".env.local" ]; then
    export $(cat .env.local | grep -v '^#' | xargs)
fi

# Set Python path
export PYTHONPATH="${PROJECT_ROOT}:${PYTHONPATH}"

# Run command
./dcabot-env/bin/python saas/your_script.py
```

---

## Next Steps

1. ✅ Test bot execution locally with `./scripts/test_bot_run.sh`
2. ✅ Verify logs appear in Web UI at http://localhost:3030
3. ✅ Test continuous execution with `./scripts/run_bot_loop.sh 60`
4. 🚀 Deploy to Render when ready (see [docs/RENDER_DEPLOYMENT.md](../docs/RENDER_DEPLOYMENT.md))

---

**Last Updated:** December 2024
