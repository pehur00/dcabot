# Environment Variables Guide

How environment variables work in different deployment scenarios.

## Overview

The bot uses environment variables for configuration. It supports two loading methods:
1. **`.env` file** - For local development
2. **Direct injection** - For Docker/Render/production

## How It Works

**In `main.py`:**
```python
# Tries to load .env file if it exists (local dev)
# If no .env file, uses env vars from system (Docker/Render)
load_dotenv()
```

**Priority order:**
1. System environment variables (always take precedence)
2. `.env` file values (fallback for local dev)

## Local Development

### Setup

1. Copy the example file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your values:
   ```bash
   nano .env
   ```

3. Run the bot:
   ```bash
   ./run_bot.sh
   ```

### Security

- `.env` is in `.gitignore` (never committed)
- Contains secrets (API keys, tokens)
- Keep it local only

## Docker Deployment

### Option 1: Docker Run (Direct injection)

```bash
docker run -d \
  -e API_KEY=your_key \
  -e API_SECRET=your_secret \
  -e SYMBOL=BTCUSDT:Long:True \
  -e EMA_INTERVAL=1 \
  -e TESTNET=False \
  -e TELEGRAM_BOT_TOKEN=your_token \
  -e TELEGRAM_CHAT_ID=your_chat_id \
  martingale-bot
```

**✅ No `.env` file needed** - Variables passed directly

### Option 2: Docker Compose (env_file)

Create `docker-compose.yml`:
```yaml
version: '3.8'

services:
  bot:
    build: .
    env_file:
      - .env.production  # Use separate file for production
    restart: unless-stopped
```

Create `.env.production` (NOT committed):
```bash
API_KEY=your_mainnet_key
API_SECRET=your_mainnet_secret
SYMBOL=BTCUSDT:Long:True
EMA_INTERVAL=1
TESTNET=False
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id
```

Run:
```bash
docker-compose up -d
```

### Option 3: Docker with .env file (Not recommended)

If you must use `.env` in Docker:

```dockerfile
# Add to Dockerfile
COPY .env /app/.env
```

**⚠️ Security risk:** Secrets baked into image

## Render.com Deployment

Environment variables are set in the Render dashboard:

1. Go to your service → **Environment**
2. Add each variable:
   - `API_KEY` = `your_phemex_api_key`
   - `API_SECRET` = `your_phemex_api_secret`
   - `SYMBOL` = `BTCUSDT:Long:True`
   - `EMA_INTERVAL` = `1`
   - `TESTNET` = `False`
   - `TELEGRAM_BOT_TOKEN` = `your_bot_token`
   - `TELEGRAM_CHAT_ID` = `your_chat_id`

3. Click **Save Changes**

**✅ No `.env` file needed** - Render injects variables into container

### Updating Variables

1. Change in Render dashboard
2. Service auto-redeploys with new values
3. No code changes needed

## VPS Deployment

### Option 1: System Environment Variables

Add to `~/.bashrc` or `/etc/environment`:
```bash
export API_KEY=your_key
export API_SECRET=your_secret
export SYMBOL=BTCUSDT:Long:True
```

Then:
```bash
source ~/.bashrc
python main.py
```

### Option 2: .env File on Server

Upload `.env` to server (securely):
```bash
scp .env user@server:/path/to/dcabot/.env
```

### Option 3: Systemd with Environment

In `/etc/systemd/system/tradingbot.service`:
```ini
[Service]
Environment="API_KEY=your_key"
Environment="API_SECRET=your_secret"
Environment="SYMBOL=BTCUSDT:Long:True"
EnvironmentFile=/path/to/.env  # Or use file
```

## Environment Variable Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `API_KEY` | ✅ Yes | - | Phemex API key |
| `API_SECRET` | ✅ Yes | - | Phemex API secret |
| `SYMBOL` | ✅ Yes | - | Trading pairs (see format below) |
| `EMA_INTERVAL` | No | `1` | EMA calculation interval (minutes) |
| `TESTNET` | No | `False` | Use testnet (`True`) or mainnet (`False`) |
| `TELEGRAM_BOT_TOKEN` | No | - | Telegram bot token (optional) |
| `TELEGRAM_CHAT_ID` | No | - | Telegram chat ID (optional) |

### SYMBOL Format

**Single symbol:**
```
SYMBOL=BTCUSDT:Long:True
```

**Multiple symbols:**
```
SYMBOL=BTCUSDT:Long:True,ETHUSDT:Short:False,ADAUSDT:Long:True
```

**Format:** `SYMBOL:SIDE:AUTO`
- `SYMBOL`: Trading pair (e.g., BTCUSDT)
- `SIDE`: `Long` or `Short`
- `AUTO`: `True` (auto-opens positions) or `False` (manual)

## Testing Environment Variables

### Local Test

```bash
# Check what's loaded
source dcabot-env/bin/activate
python3 -c "
import os
from dotenv import load_dotenv
load_dotenv()
print('API_KEY:', os.getenv('API_KEY')[:20] + '...')
print('TESTNET:', os.getenv('TESTNET'))
print('SYMBOL:', os.getenv('SYMBOL'))
print('Telegram:', 'Enabled' if os.getenv('TELEGRAM_BOT_TOKEN') else 'Disabled')
"
```

### Docker Test

```bash
docker run --rm \
  -e API_KEY=test \
  -e API_SECRET=test \
  -e SYMBOL=BTCUSDT:Long:True \
  martingale-bot \
  python3 -c "import os; print(os.getenv('API_KEY'))"
```

## Troubleshooting

### Local: Variables not loading

**Problem:** `None` values for env vars

**Solutions:**
1. Check `.env` file exists: `ls -la .env`
2. Verify format (no spaces around `=`): `API_KEY=value`
3. Check for quotes (not needed): `API_KEY=value` not `API_KEY="value"`
4. Restart terminal/IDE after editing `.env`

### Docker: Variables not injected

**Problem:** Bot crashes with missing env vars

**Solutions:**
1. Check Docker run command has all `-e` flags
2. Verify `docker-compose.yml` has `env_file` or `environment`
3. Test: `docker exec container env | grep API_KEY`

### Render: Variables not set

**Problem:** Deployment fails or bot can't connect

**Solutions:**
1. Go to Environment tab in Render
2. Verify all required variables are set
3. Check for typos in variable names
4. Re-deploy after adding variables

## Security Best Practices

1. **Never commit `.env` to git**
   - Already in `.gitignore`
   - Double-check: `git status`

2. **Use different keys per environment**
   - Testnet keys for testing
   - Mainnet keys for production
   - Separate keys per deployment

3. **Rotate keys regularly**
   - Generate new API keys monthly
   - Update in all deployments

4. **Limit API permissions**
   - Trading only (no withdrawals)
   - IP whitelist if possible

5. **Encrypt secrets in production**
   - Use Render's secret management
   - Or AWS Secrets Manager
   - Or HashiCorp Vault

## Multiple Environments

### Typical setup:

```
.env                    # Local dev (testnet)
.env.production        # Production (mainnet) - NOT committed
.env.staging           # Staging server - NOT committed
.env.example           # Template - committed to repo
```

### Switching environments:

```bash
# Development
cp .env.development .env
./run_bot.sh

# Production
cp .env.production .env
./run_bot.sh
```

## Quick Reference

| Scenario | Method | File Needed |
|----------|--------|-------------|
| Local Dev | `.env` file | ✅ `.env` |
| Docker Run | `-e` flags | ❌ None |
| Docker Compose | `env_file` | ✅ `.env.production` |
| Render.com | Dashboard | ❌ None |
| VPS (systemd) | `Environment=` | Optional |

## Need Help?

- Check variable is set: `echo $API_KEY`
- View all env vars: `env | grep -E 'API|TELEGRAM|SYMBOL'`
- Test loading: See "Testing Environment Variables" above
- Check logs for "Loaded environment variables" message
