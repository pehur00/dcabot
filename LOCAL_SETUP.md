# Local Development Setup - AI Trading Bot

## Quick Start 🚀

The Flask app is now running successfully! All setup is complete.

### Access the Application

**URL:** http://localhost:3030

The app is currently running in debug mode with auto-reload enabled.

---

## Helper Scripts

### 1. Run Migrations
```bash
./run_migrations.sh          # Apply pending migrations
./run_migrations.sh --status # Check migration status
```

### 2. Start Flask App
```bash
./run_local_app.sh           # Start the Flask web app on port 3030
```

The script automatically:
- Loads `.env.local` (Flask configuration)
- Loads `.env` (bot/API credentials)
- Sets PYTHONPATH correctly
- Runs migrations on startup

### 3. Stop Flask App
```bash
# Press Ctrl+C in the terminal where it's running
# Or find and kill the process:
ps aux | grep "python.*saas.app" | grep -v grep | awk '{print $2}' | xargs kill
```

---

## Configuration Files

### `.env.local` (Flask/SaaS Configuration)
```bash
SECRET_KEY=local-dev-secret-key-change-in-production
DEBUG=True
PORT=3030
DATABASE_URL=postgresql://dcabot:dcabot_dev_password@localhost:5435/dcabot_dev
ENCRYPTION_KEY=your-encryption-key-here
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
```

**Note:** Actual credentials are in your local `.env.local` file (not committed to Git)

### `.env` (Bot/Trading Configuration)
```bash
# Phemex API Credentials (for standalone bot mode)
API_KEY=your-phemex-api-key
API_SECRET=your-phemex-api-secret
TESTNET=True

# AI Model API Keys (for executor)
ZHIPU_API_KEY=your-zhipu-api-key
DEEPSEEK_API_KEY=your-deepseek-api-key
ANTHROPIC_API_KEY=your-anthropic-api-key

# Telegram Notifications
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
TELEGRAM_CHAT_ID=your-telegram-chat-id
```

**Note:** Actual credentials are in your local `.env` file (not committed to Git)

---

## Database

### Connection String
```
postgresql://dcabot:dcabot_dev_password@localhost:5435/dcabot_dev
```

### Status Check
```bash
nc -z localhost 5435 && echo "✅ PostgreSQL running" || echo "❌ PostgreSQL not running"
```

### Manual Connection (psql)
```bash
psql postgresql://dcabot:dcabot_dev_password@localhost:5435/dcabot_dev
```

---

## AI Bot Features (Phase 4 - NEW!)

### Create AI Trading Bot
1. Navigate to http://localhost:3030
2. Click "🤖 AI Bots" in navigation
3. Click "Create AI Bot(s)"
4. Fill out the form:
   - **Bot Configuration:** Name, symbol, side, leverage, position size
   - **Select AI Models:** Check multiple models (GLM-4.5-Air, DeepSeek-Chat, etc.)
   - **Exchange Credentials:** Phemex API key/secret, testnet checkbox
   - **AI API Keys:** Provider-specific keys (z.ai, DeepSeek, Anthropic)
5. Submit - Creates N bot instances (one per selected model)

### Dashboard Features
- **Multi-line chart:** Shows all model performance on single chart
- **Filters:** View all models or specific model
- **Time ranges:** 24h, 72h, 7d, 30d
- **Tabs:** POSITIONS, COMPLETED TRADES, MODELCHAT, LEADERBOARD
- **Leaderboard:** Aggregated stats per model

### Virtual Balance Tracking
- Each AI bot starts with $100 virtual balance
- Tracks:
  - API costs (deducted per decision)
  - Trade PnL (profit/loss per trade)
  - Trade fees (exchange fees)
- Balance history stored for charting

---

## Sentiment Data Sources

### 4 Free Data Sources
1. **Fear & Greed Index** (alternative.me)
   - Crypto market sentiment (0-100)

2. **LunarCrush** (Twitter/Social)
   - Social sentiment from Twitter/social media
   - Free tier API

3. **Reddit** (r/CryptoCurrency, r/Bitcoin)
   - Keyword-based sentiment analysis
   - No authentication required

4. **CryptoPanic** (News)
   - Recent news headlines
   - Free tier API

---

## Testing the AI Bot System

### Manual Executor Run
```bash
# Load environment variables
export $(cat .env.local | grep -v '^#' | xargs)
export $(cat .env | grep -v '^#' | xargs)

# Run AI bot executor (processes all active bots)
./dcabot-env/bin/python saas/execute_ai_bots.py
```

This will:
1. Fetch all active AI bots from database
2. For each bot:
   - Decrypt API keys
   - Fetch market data (price, indicators, sentiment)
   - Send to AI model for decision
   - Log decision to database
   - Update virtual balance (deduct API cost)
   - Execute trade if recommended (and automatic_mode=True)

### Check Logs
```bash
# Flask app logs (shows requests, errors)
tail -f logs/app.log

# AI executor logs (shows bot decisions)
# Printed to stdout when running execute_ai_bots.py
```

---

## Project Structure

```
dcabot/
├── saas/                              # SaaS web application
│   ├── app.py                         # Flask routes (main app)
│   ├── ai_bot_routes.py               # AI bot routes (NEW)
│   ├── database.py                    # Database helpers
│   ├── migrate.py                     # Migration runner
│   ├── execute_ai_bots.py             # AI bot executor (cron job)
│   ├── templates/
│   │   ├── ai_bot_form.html           # Multi-model creation form (NEW)
│   │   └── ai_bots_dashboard.html     # Multi-line chart dashboard (NEW)
│   ├── static/
│   │   ├── images/logos/              # Model logos (NEW)
│   │   │   ├── zhipu.svg
│   │   │   ├── deepseek.svg
│   │   │   └── anthropic.svg
│   │   └── css/style.css
│   └── migrations/
│       ├── 012_create_ai_bot_tables.sql        (NEW)
│       └── 013_add_virtual_balance_tracking.sql (NEW)
├── strategies/
│   └── AITradingStrategy.py           # AI decision logic
├── data/
│   └── market_data_fetcher.py         # Market data + sentiment (enhanced)
├── .env.local                         # Flask configuration
├── .env                               # Bot/API credentials
├── run_local_app.sh                   # Helper: Start Flask (NEW)
└── run_migrations.sh                  # Helper: Run migrations (NEW)
```

---

## Troubleshooting

### "No module named 'saas'" Error
**Fix:** Run from project root (`dcabot/`) or use the helper scripts
```bash
# ❌ Wrong (from inside saas/)
cd saas && python app.py

# ✅ Correct (from project root)
./run_local_app.sh
```

### Database Connection Failed
**Check PostgreSQL:**
```bash
nc -z localhost 5435
# Should output: Connection to localhost port 5435 [tcp/dttl] succeeded!
```

**Check credentials:**
```bash
psql postgresql://dcabot:dcabot_dev_password@localhost:5435/dcabot_dev
```

### Migration Errors
**View status:**
```bash
./run_migrations.sh --status
```

**Manually run specific migration:**
```bash
export $(cat .env.local | grep -v '^#' | xargs)
./dcabot-env/bin/python saas/migrate.py
```

### Port Already in Use
**Find process using port 3030:**
```bash
lsof -ti:3030
# Kill it:
lsof -ti:3030 | xargs kill -9
```

---

## Next Steps

1. ✅ **Dependencies installed** (psycopg2-binary 2.9.11 for Python 3.13)
2. ✅ **Migrations applied** (AI bot tables created)
3. ✅ **Flask app running** (http://localhost:3030)
4. ⏳ **Test AI bot creation** (Create your first multi-model bot)
5. ⏳ **Run executor** (Generate test data for dashboard)
6. ⏳ **Deploy to production** (Merge to main, deploy to Render)

---

## Key Credentials (Development)

All credentials are stored in your local `.env` and `.env.local` files (not committed to Git).

**Required for AI Bots:**
- Phemex API credentials (testnet or mainnet)
- AI model API keys (Zhipu, DeepSeek, Anthropic)
- Optional: Telegram bot credentials for notifications

---

**Last Updated:** November 5, 2025
**Feature Branch:** `feature/ai-glm-trading-bot`
**Status:** ✅ Ready for Testing
