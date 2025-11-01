# Scripts Directory

This directory contains utility scripts for running and testing the DCA Bot SaaS platform.

## Bot Execution Scripts

### `start_local.sh`
Starts the Flask web application for local development.

**Usage:**
```bash
./scripts/start_local.sh
```

**What it does:**
- Sets up environment variables (DATABASE_URL, ENCRYPTION_KEY, etc.)
- Starts Flask on port 3030
- Enables debug mode for auto-reload
- Web UI available at http://localhost:3030

---

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
1. Shows bot details (name, exchange, trading pairs)
2. Asks for confirmation
3. Executes the bot once
4. Shows execution logs
5. Displays recent activity from database

**Perfect for:**
- Testing bot configuration
- Debugging execution issues
- Verifying API keys work
- Checking trading logic

---

### `run_bot_loop.sh`
Continuously executes all active bots every 5 minutes (matches production schedule).

**Usage:**
```bash
# Run with default 5 minute interval
./scripts/run_bot_loop.sh

# Run with custom interval (e.g., 60 seconds for testing)
./scripts/run_bot_loop.sh 60
```

**What it does:**
- Runs `saas/execute_all_bots.py` in a loop
- Executes all bots with status='running'
- Shows cycle number, timing, and results
- Press Ctrl+C to stop

**Use this when:**
- Testing continuous execution locally
- Simulating production behavior
- Running multiple bots simultaneously

---

### `run_bot.sh` (Legacy)
Original single-bot execution script from before SaaS transformation.

**Still useful for:**
- Running bot without database
- Quick testing with config.json
- Standalone bot execution

---

## Testing & Development Scripts

### `test_db_connection.py`
Tests database connectivity and queries sample data.

**Usage:**
```bash
export DATABASE_URL="postgresql://dcabot:dcabot_dev_password@localhost:5435/dcabot_dev"
dcabot-env/bin/python scripts/test_db_connection.py
```

---

### `test_top_coins.py`
Backtests the DCA strategy across multiple top cryptocurrencies.

**Usage:**
```bash
dcabot-env/bin/python scripts/test_top_coins.py --days 7 --leverage 5
```

**Options:**
- `--days`: Number of days to backtest
- `--leverage`: Leverage multiplier
- Tests strategy on top market cap coins

---

### `test_leverages.sh`
Tests different leverage settings across multiple timeframes.

**Usage:**
```bash
./scripts/test_leverages.sh
```

---

## Quick Start Guide

### 1. Start Local Development Environment

```bash
# Terminal 1: Start PostgreSQL (if not running)
docker-compose up -d

# Terminal 2: Start Flask Web UI
./scripts/start_local.sh
```

Open http://localhost:3030 in your browser.

### 2. Create a Bot

1. Register/login at http://localhost:3030
2. Click "Add New Bot"
3. Configure exchange, API keys, testnet mode
4. Add trading pairs (symbol, side, leverage, etc.)
5. Start the bot

### 3. Test Bot Execution

```bash
# List your bots
./scripts/test_bot_run.sh

# Execute bot ID 1
./scripts/test_bot_run.sh 1
```

### 4. Run Continuously (Optional)

```bash
# Run all active bots every 5 minutes
./scripts/run_bot_loop.sh

# Or run with 1 minute interval for testing
./scripts/run_bot_loop.sh 60
```

---

## Environment Variables

All bot execution scripts require these environment variables:

```bash
export DATABASE_URL="postgresql://dcabot:dcabot_dev_password@localhost:5435/dcabot_dev"
export ENCRYPTION_KEY="f5odR2dgOe8F4q_jo7hy70LIT5zFkt9y9TMkPaC6GYU="
export PYTHONPATH="${PWD}:${PYTHONPATH}"
```

These are automatically set by the execution scripts.

---

## Production vs Local

| Aspect | Local Development | Production (Render) |
|--------|------------------|---------------------|
| Web UI | `./scripts/start_local.sh` | Gunicorn + auto-deploy |
| Bot Execution | `./scripts/run_bot_loop.sh` | Render Cron Job (every 5 min) |
| Database | Docker PostgreSQL (port 5435) | Render PostgreSQL |
| Scheduling | Manual loop script | Automatic cron job |
| Logs | Console + database | Database + Render logs |

---

## Troubleshooting

**Port already in use:**
```bash
lsof -ti:3030 | xargs kill -9
```

**Database connection failed:**
```bash
docker-compose ps  # Check if PostgreSQL is running
docker-compose up -d  # Start if not running
```

**Import errors:**
```bash
export PYTHONPATH="${PWD}:${PYTHONPATH}"
```

**Flask not reloading:**
- Flask auto-reloads in debug mode
- If stuck, kill and restart: `lsof -ti:3030 | xargs kill -9; ./scripts/start_local.sh`

---

## Next Steps

1. ✅ Test bot execution locally with `./scripts/test_bot_run.sh`
2. ✅ Verify logs appear in Web UI at http://localhost:3030
3. ✅ Test continuous execution with `./scripts/run_bot_loop.sh 60`
4. 🚀 Deploy to Render when ready (see `docs/DEPLOYMENT_CHECKLIST.md`)
