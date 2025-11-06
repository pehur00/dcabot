# Local Development Setup

**Last Updated:** November 6, 2025

Complete guide for setting up the DCABot platform for local development.

---

## Quick Start

### Prerequisites
- Python 3.10+
- PostgreSQL 14+
- Docker (for local PostgreSQL)
- Git

### 1. Clone Repository
```bash
git clone https://github.com/pehur00/dcabot
cd dcabot
```

### 2. Create Virtual Environment
```bash
python -m venv dcabot-env
source dcabot-env/bin/activate  # On Windows: dcabot-env\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt -r requirements-saas.txt
```

### 4. Start PostgreSQL
```bash
docker run -d --name dcabot-db \
  -e POSTGRES_USER=dcabot \
  -e POSTGRES_PASSWORD=dcabot_dev_password \
  -e POSTGRES_DB=dcabot_dev \
  -p 5435:5432 postgres:15
```

### 5. Create Environment Files

**Create `.env.local`** (Flask/SaaS configuration):
```bash
SECRET_KEY=local-dev-secret-key-change-in-production
DEBUG=True
PORT=3030
DATABASE_URL=postgresql://dcabot:dcabot_dev_password@localhost:5435/dcabot_dev
ENCRYPTION_KEY=<generate-with-command-below>
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
```

**Generate encryption key:**
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

**Create `.env`** (Optional - legacy standalone bot):
```bash
API_KEY=your-phemex-api-key
API_SECRET=your-phemex-api-secret
TESTNET=True
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
TELEGRAM_CHAT_ID=your-telegram-chat-id
```

### 6. Run Migrations
```bash
./scripts/run_migrations.sh
```

### 7. Start Web Application
```bash
./scripts/run_local_app.sh
```

Visit: **http://localhost:3030**

---

## Configuration

### Database Connection
Default local connection:
```
postgresql://dcabot:dcabot_dev_password@localhost:5435/dcabot_dev
```

**Test connection:**
```bash
psql postgresql://dcabot:dcabot_dev_password@localhost:5435/dcabot_dev -c "SELECT 1"
```

### Trading API Keys

**Important:** In the SaaS platform, API keys are provided through the web dashboard, NOT environment variables.

**For Martingale Bots:**
- Phemex API Key/Secret → Entered when creating bot

**For AI Bots:**
- Phemex API Key/Secret → Per bot (unique account per model)
- OpenRouter API Key → Entered when creating bot (get free key from https://openrouter.ai/keys)
  - Single API key provides access to 400+ AI models (GPT-4o, Claude, Gemini, DeepSeek, Qwen3, etc.)
  - Budget models available from $0.20/1M tokens
  - Many models have free tiers for testing

**Telegram Notifications (Optional):**
- Create bot with @BotFather on Telegram
- Get Chat ID from @userinfobot
- Configure in User Settings page

**Security:** All API keys are encrypted with Fernet before storage.

---

## Running the Platform

### Start Web App
```bash
./scripts/run_local_app.sh
# Visit: http://localhost:3030
```

**What it does:**
- Loads `.env.local` and `.env` files
- Sets PYTHONPATH
- Runs migrations automatically
- Starts Flask with debug mode

### Run Bot Executors

**AI bots only:**
```bash
./scripts/run_executor.sh
```

**All bots (Martingale + AI):**
```bash
./scripts/run_all_bots.sh
```

**Continuous execution (simulates production):**
```bash
./scripts/run_bot_loop.sh
# Or with custom interval:
./scripts/run_bot_loop.sh 60  # 60 seconds
```

### Run Migrations
```bash
./scripts/run_migrations.sh          # Apply pending migrations
./scripts/run_migrations.sh --status # Check status
```

---

## Testing Workflow

### 1. Create a Bot
1. Register/login at http://localhost:3030
2. Click "Add New Bot"
3. Configure bot with Phemex API credentials (testnet recommended)
4. Add trading pairs (symbol, side, leverage)
5. Start the bot

### 2. Test Execution
```bash
# Test single bot
./scripts/test_bot_run.sh 1

# Run all bots once
./scripts/run_all_bots.sh

# Continuous execution loop
./scripts/run_bot_loop.sh 60
```

### 3. Check Logs
- **Web UI:** http://localhost:3030/dashboard
- **Console:** Output from executor scripts
- **Database:** `bot_logs`, `ai_decisions` tables

---

## Project Structure

```
dcabot/
├── saas/                              # SaaS web application
│   ├── app.py                         # Flask routes
│   ├── database.py                    # Database helpers
│   ├── execute_all_bots.py            # Martingale executor
│   ├── execute_ai_bots.py             # AI bot executor
│   ├── security.py                    # Encryption utilities
│   ├── validation.py                  # Input validation
│   ├── timezone_utils.py              # Timezone handling
│   ├── migrations/                    # SQL migration files
│   └── templates/                     # HTML templates
├── strategies/
│   ├── MartingaleTradingStrategy.py   # Martingale logic
│   └── AITradingStrategy.py           # AI decision logic
├── data/
│   └── market_data_fetcher.py         # Market data + sentiment
├── clients/
│   └── PhemexClient.py                # Phemex API wrapper
├── indicators/
│   └── volatility.py                  # Volatility calculations
├── notifications/
│   └── TelegramNotifier.py            # Telegram alerts
├── scripts/                           # Helper scripts
│   ├── run_local_app.sh
│   ├── run_migrations.sh
│   ├── run_executor.sh
│   └── test_bot_run.sh
└── docs/                              # Documentation
    ├── ARCHITECTURE.md
    ├── ROADMAP.md
    └── RENDER_DEPLOYMENT.md
```

---

## Troubleshooting

### "No module named 'saas'" Error
**Fix:** Run from project root or use helper scripts
```bash
# ❌ WRONG:
cd saas && python app.py

# ✅ CORRECT:
./scripts/run_local_app.sh
```

### Database Connection Failed
**Check PostgreSQL:**
```bash
docker ps | grep dcabot-db
# If not running:
docker start dcabot-db

# Test connection:
psql postgresql://dcabot:dcabot_dev_password@localhost:5435/dcabot_dev
```

### Port Already in Use
```bash
# Find process using port 3030:
lsof -ti:3030 | xargs kill -9

# Restart app:
./scripts/run_local_app.sh
```

### Migration Errors
```bash
# Check status:
./scripts/run_migrations.sh --status

# View applied migrations:
psql $DATABASE_URL -c "SELECT * FROM schema_migrations ORDER BY applied_at DESC;"
```

### Flask Not Reloading
```bash
# Kill and restart:
lsof -ti:3030 | xargs kill -9
./scripts/run_local_app.sh
```

---

## Database Management

### Reset Local Database
```bash
# Stop containers
docker stop dcabot-db
docker rm dcabot-db

# Recreate
docker run -d --name dcabot-db \
  -e POSTGRES_USER=dcabot \
  -e POSTGRES_PASSWORD=dcabot_dev_password \
  -e POSTGRES_DB=dcabot_dev \
  -p 5435:5432 postgres:15

# Run migrations
./scripts/run_migrations.sh
```

### Manual Database Access
```bash
# Connect with psql
psql postgresql://dcabot:dcabot_dev_password@localhost:5435/dcabot_dev

# List tables
\dt

# Describe table
\d+ users

# Query data
SELECT * FROM bots WHERE status = 'running';
```

---

## Environment Variables Reference

### `.env.local` (Flask Configuration)
| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection | `postgresql://dcabot:dcabot_dev_password@localhost:5435/dcabot_dev` |
| `ENCRYPTION_KEY` | Fernet encryption key | Generated with Fernet.generate_key() |
| `SECRET_KEY` | Flask session secret | Any random string |
| `DEBUG` | Flask debug mode | `True` for local, `False` for production |
| `PORT` | Flask port | `3030` |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID | From Google Console |
| `GOOGLE_CLIENT_SECRET` | Google OAuth secret | From Google Console |

### `.env` (Legacy Standalone Bot)
| Variable | Description |
|----------|-------------|
| `API_KEY` | Phemex API key (deprecated - use dashboard) |
| `API_SECRET` | Phemex API secret (deprecated - use dashboard) |
| `TESTNET` | Phemex testnet flag |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token |
| `TELEGRAM_CHAT_ID` | Telegram chat ID |

---

## Next Steps

1. ✅ Start local development environment
2. ✅ Create your first bot in the dashboard
3. ✅ Test execution with `./scripts/test_bot_run.sh`
4. ✅ Monitor results in web dashboard
5. 🚀 Deploy to production (see [RENDER_DEPLOYMENT.md](RENDER_DEPLOYMENT.md))

---

## Additional Resources

- [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture details
- [RENDER_DEPLOYMENT.md](RENDER_DEPLOYMENT.md) - Production deployment
- [DATABASE_MIGRATIONS.md](DATABASE_MIGRATIONS.md) - Migration system
- [STRATEGY.md](STRATEGY.md) - Trading strategy details
- [scripts/README.md](../scripts/README.md) - Helper scripts reference

---

**Last Updated:** November 6, 2025
**Status:** ✅ Production Ready
