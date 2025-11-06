# DCABot - Multi-User Cryptocurrency Trading Platform

**Last Updated:** November 6, 2025

A SaaS platform for cryptocurrency trading with two powerful strategies:
- **AI Trading Bots** - LLM-powered decision making (GLM, DeepSeek, Claude, Gemini)
- **Martingale Strategy** - EMA-based dip-buying with intelligent risk management

**Status:** Production on Render.com | **Branch:** `feature/saas-transformation`

---

## Table of Contents

- [Quick Start](#quick-start)
- [Key Features](#key-features)
- [Architecture Overview](#architecture-overview)
- [Trading Strategies](#trading-strategies)
- [Local Development](#local-development)
- [Production Deployment](#production-deployment)
- [Configuration](#configuration)
- [Documentation](#documentation)
- [Cost Breakdown](#cost-breakdown)
- [Risk Warning](#risk-warning)

---

## Quick Start

### Prerequisites
- Python 3.10+
- PostgreSQL 14+ (local or managed)
- Phemex account (testnet recommended for testing)
- Git and GitHub account (for deployment)

### Local Development Setup

```bash
# 1. Clone and create virtual environment
git clone https://github.com/pehur00/dcabot
cd dcabot
python -m venv dcabot-env
source dcabot-env/bin/activate  # On Windows: dcabot-env\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt -r requirements-saas.txt

# 3. Start PostgreSQL
docker run -d --name dcabot-db \
  -e POSTGRES_USER=dcabot \
  -e POSTGRES_PASSWORD=dcabot_dev_password \
  -e POSTGRES_DB=dcabot_dev \
  -p 5435:5432 postgres:15

# 4. Create environment files
cp .env.example .env.local
# Edit .env.local with your configuration:
# - DATABASE_URL=postgresql://dcabot:dcabot_dev_password@localhost:5435/dcabot_dev
# - SECRET_KEY=your-secret-key-here
# - ENCRYPTION_KEY=<generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">
# - GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET (for OAuth)

# 5. Run migrations
./scripts/run_migrations.sh

# 6. Start web application
./scripts/run_local_app.sh
# Visit: http://localhost:3030
```

**See [docs/LOCAL_SETUP.md](docs/LOCAL_SETUP.md) for detailed instructions.**

### Deploy to Production

```bash
git push origin feature/saas-transformation
```

Render Blueprint (`render.yaml`) automatically deploys all services:
- Web Service ($7/month) - Flask dashboard
- AI Bot Executor (FREE) - Runs every 5 minutes
- Martingale Executor (FREE) - Runs every 5 minutes

**See [docs/RENDER_DEPLOYMENT.md](docs/RENDER_DEPLOYMENT.md) for complete deployment guide.**

---

## Key Features

### AI Trading Bots
- **Multi-Model Support**: Compare GLM-4.5-Air ($2.50/mo), DeepSeek ($3.50/mo), Claude ($150/mo), Gemini side-by-side
- **Real Balance Tracking**: Each bot uses dedicated Phemex account (1 Bot = 1 Account = 1 AI Model)
- **Comprehensive Analysis**: Technical indicators + sentiment data (Fear & Greed Index)
- **Live Execution**: Automated trading every 5 minutes with confidence threshold (70%)
- **Performance Tracking**: Model-specific colored dashboards with PnL, trade history, and decision logs
- **Trade Logging**: Complete audit trail of all trades with entry/exit prices, PnL, and fees

### Martingale Strategy
- **EMA-Based Entry**: Only enters when price is below/above EMA100 (dip-buying strategy)
- **Intelligent Averaging**: Adds to positions systematically when down 4%
- **Volatility Protection**: Pauses during dangerous market conditions (CRASH/FAST_DECLINE)
- **Dynamic Position Sizing**: Exponential tapering prevents margin exhaustion
- **Decline Velocity Detection**: Distinguishes crashes from safe pullbacks
- **Margin Protection**: 50% hard cap with pre-order validation

### Platform Features
- **Multi-User SaaS**: User registration with Google OAuth
- **Web Dashboard**: Real-time performance visualization with Chart.js
- **Encrypted Credentials**: Fernet encryption for all API keys
- **Auto-Migrations**: Database schema updates on every deploy
- **Telegram Notifications**: Real-time alerts per user
- **Multi-Symbol Trading**: Trade multiple pairs independently per bot
- **Timezone Support**: Display times in 50+ country timezones

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                 Flask Web Application                    │
│  • Google OAuth Authentication                           │
│  • Bot Management (Create, Configure, Start/Stop)       │
│  • Real-time Dashboards (Chart.js)                      │
│  • Admin Panel (User Approval)                          │
│  • Cost: $7/month (Render Starter)                      │
└────────────┬───────────────────────┬────────────────────┘
             │                       │
    ┌────────▼────────┐    ┌────────▼────────┐
    │ AI Bot Executor │    │ Martingale Bot  │
    │  (Cron: */5)    │    │  Executor       │
    │  FREE           │    │  (Cron: */5)    │
    └────────┬────────┘    └────────┬────────┘
             │                       │
             └───────────┬───────────┘
                         │
            ┌────────────▼────────────┐
            │  PostgreSQL Database    │
            │  • Users & bots config  │
            │  • Trade history        │
            │  • Performance metrics  │
            │  Cost: ~$15/month       │
            └─────────────────────────┘
```

**See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed architecture.**

---

## Trading Strategies

### AI Trading Bots

**How it works:**
1. Fetch market data every 5 minutes (price, EMAs, RSI, volume, Fear & Greed Index)
2. Send comprehensive prompt to AI model for analysis
3. AI returns decision: BUY/SELL/HOLD with confidence % and reasoning
4. Execute trade if confidence ≥ 70% and `automatic_mode` is enabled
5. Log decision and trade to database
6. Track performance metrics per model

**Architecture:** 1 Bot = 1 Phemex Account = 1 AI Model (true isolation)

**AI Prompt includes:**
- Technical indicators (EMAs, RSI, volume trends, price changes)
- Market sentiment (Fear & Greed Index)
- Current position details (size, PnL, entry price)
- Trading rules (max position size, leverage, stop-loss)

**Decision threshold:** Confidence ≥ 70% required to execute

### Martingale Strategy

**How it works:**
1. **Entry**: Open position when price < EMA100 (Long) or > EMA100 (Short)
2. **Averaging**: Add to position when down 4%, increasing size exponentially
3. **Profit Taking**: Close when ≥ 0.3% profit or 10% PnL target reached
4. **Risk Management**: 50% margin cap with dynamic position tapering

**Key Parameters:**
```python
CONFIG = {
    'buy_until_limit': 0.02,           # Max 2% of balance in position
    'profit_threshold': 0.003,         # Min 0.3% profit to close
    'profit_pnl': 0.1,                 # 10% PnL target
    'leverage': 10,                    # 10x leverage
    'begin_size_of_balance': 0.006,    # Start with 0.6% of balance
    'max_margin_pct': 0.50,            # Max 50% margin
    'buy_below_percentage': 0.04,      # Buy when down 4%
}
```

**Safety Features:**
- Volatility protection (pauses during CRASH/FAST_DECLINE)
- Decline velocity detection (safe during SLOW/MODERATE declines)
- Dynamic position tapering (exponential decrease as margin increases)
- Margin level monitoring (stops at 50% to prevent liquidation)
- Pre-order validation (checks margin before placing orders)

**See [docs/STRATEGY.md](docs/STRATEGY.md) for detailed strategy explanation.**

---

## Local Development

### Running the Application

```bash
# Start web application
./scripts/run_local_app.sh
# Visit: http://localhost:3030

# Run migrations
./scripts/run_migrations.sh

# Execute AI bots manually (for testing)
./scripts/run_executor.sh

# Execute all bots (Martingale + AI) manually
./run_all_bots.sh
```

### Helper Scripts

All scripts are located in `/scripts` directory:
- `run_local_app.sh` - Start Flask app on port 3030
- `run_migrations.sh` - Apply database migrations
- `test_bot_run.sh` - Test single bot execution
- `run_bot_loop.sh` - Continuous execution loop (simulates production)

**See [scripts/README.md](scripts/README.md) for complete script documentation.**

### Testing

```bash
# Test single bot
./scripts/test_bot_run.sh <bot_id>

# Run continuous execution (5 minute interval)
./scripts/run_bot_loop.sh

# Test with custom interval (60 seconds)
./scripts/run_bot_loop.sh 60
```

### Project Structure

```
dcabot/
├── README.md                    # This file
├── render.yaml                  # Render Blueprint (automated deployment)
├── saas/                        # SaaS Platform
│   ├── app.py                   # Flask routes & authentication
│   ├── database.py              # PostgreSQL layer
│   ├── execute_all_bots.py      # Martingale executor (cron)
│   ├── execute_ai_bots.py       # AI bot executor (cron)
│   ├── security.py              # Encryption & auth
│   ├── validation.py            # OWASP input validation
│   ├── migrations/              # SQL migration files
│   └── templates/               # HTML templates
├── strategies/
│   ├── MartingaleTradingStrategy.py  # Martingale logic
│   └── AITradingStrategy.py          # AI model integration
├── data/
│   └── market_data_fetcher.py   # Technical + sentiment data
├── clients/
│   └── PhemexClient.py          # Phemex API wrapper
├── indicators/
│   └── volatility.py            # ATR, Bollinger, decline velocity
├── notifications/
│   └── TelegramNotifier.py      # Telegram alerts
├── backtest/
│   └── backtest.py              # Backtesting framework
├── scripts/                     # Helper scripts
│   ├── run_local_app.sh
│   ├── run_migrations.sh
│   ├── test_bot_run.sh
│   └── README.md
└── docs/                        # Documentation
    ├── ARCHITECTURE.md          # System architecture
    ├── ROADMAP.md               # Future plans
    └── RENDER_DEPLOYMENT.md     # Deployment guide
```

---

## Production Deployment

### Render Blueprint Deployment

The project uses Render Blueprint (`render.yaml`) for automated deployment:

**Services:**
- **Web Service** ($7/month) - Flask dashboard and API
- **AI Bot Executor** (FREE) - Runs every 5 minutes
- **Martingale Executor** (FREE) - Runs every 5 minutes
- **Weekly Backtests** (FREE) - Runs Sunday 2 AM UTC

**Deployment Steps:**
1. Push code to `feature/saas-transformation` branch
2. Render auto-detects `render.yaml` blueprint
3. Migrations run during build phase
4. All services deploy automatically
5. No manual configuration needed

**See [docs/RENDER_DEPLOYMENT.md](docs/RENDER_DEPLOYMENT.md) for complete guide.**

### Environment Variables (Production)

Required environment variables in Render:

```bash
DATABASE_URL=postgresql://user:pass@host:port/db?sslmode=require
SECRET_KEY=<auto-generated-by-render>
ENCRYPTION_KEY=<fernet-key>
FLASK_ENV=production
DEBUG=False
```

**Generate encryption key:**
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Monitoring

```bash
# View web service logs
render logs -s dcabot-saas-web --tail

# View AI executor logs
render logs -s dcabot-ai-executor --tail

# View Martingale executor logs
render logs -s dcabot-saas-scheduler --tail

# Check service status
render services list
```

---

## Configuration

### API Keys (Stored in Database, Encrypted)

All API keys are entered through the web dashboard and encrypted before storage:

**For Martingale Bots:**
- Phemex API Key/Secret → Entered when creating bot

**For AI Bots:**
- Phemex API Key/Secret → Per bot (unique account per model)
- GLM API Key → User Settings page
- DeepSeek API Key → User Settings page
- Claude API Key → User Settings page
- Gemini API Key → User Settings page

**Telegram (Optional):**
- Bot Token + Chat ID → User Settings page

**Security:** All credentials encrypted with Fernet before database storage.

### Database Migration System

Migrations are SQL-based and run automatically on deployment:
- Sequential naming: `001_`, `002_`, `003_`, etc.
- Tracked in `schema_migrations` table
- Idempotent (use `IF NOT EXISTS`)
- No edits after deployment (create new migration)

**See [docs/DATABASE_MIGRATIONS.md](docs/DATABASE_MIGRATIONS.md) for details.**

---

## Documentation

### Essential Reading
1. [ARCHITECTURE.md](docs/ARCHITECTURE.md) - System architecture and components
2. [RENDER_DEPLOYMENT.md](docs/RENDER_DEPLOYMENT.md) - Production deployment guide
3. [LOCAL_SETUP.md](docs/LOCAL_SETUP.md) - Local development setup
4. [STRATEGY.md](docs/STRATEGY.md) - Trading strategy details

### Advanced Topics
- [DATABASE_MIGRATIONS.md](docs/DATABASE_MIGRATIONS.md) - Schema management system
- [ROADMAP.md](docs/ROADMAP.md) - Future features and enhancements
- [scripts/README.md](scripts/README.md) - Helper script documentation

### Setup Guides
- [TELEGRAM_SETUP.md](docs/TELEGRAM_SETUP.md) - Configure Telegram notifications
- [GLM_SIGNUP_GUIDE.md](docs/GLM_SIGNUP_GUIDE.md) - Sign up for GLM API
- [GOOGLE_OAUTH_SETUP.md](saas/GOOGLE_OAUTH_SETUP.md) - Configure Google OAuth

---

## Cost Breakdown

| Component | Type | Cost |
|-----------|------|------|
| Web Service | Render Starter | $7/month |
| Cron Jobs (3x) | Render Free tier | $0/month |
| PostgreSQL | External (managed) | ~$15/month |
| **Total Infrastructure** | | **~$22/month** |
| AI Bot (GLM-4.5-Flash) | z.ai | **FREE** |
| AI Bot (GLM-4.5-Air) | z.ai | $2.50/month |
| AI Bot (DeepSeek-Chat) | DeepSeek | $3.50/month |
| AI Bot (Claude-3.5-Sonnet) | Anthropic | ~$150/month |

**Total: $22-180/month depending on AI models used**

---

## Risk Warning

**IMPORTANT**: Both trading strategies carry significant risk:

- **AI Trading Bots**: Relies on LLM decision quality; no guarantee of profitability
- **Martingale Strategy**: Can experience extended drawdowns; may lose entire account in extreme conditions
- **Leverage**: Amplifies both gains and losses (10x leverage = 10x risk)
- **Cryptocurrency**: Highly volatile asset class with 24/7 markets

**Only use funds you can afford to lose completely.**

### Best Practices
1. **Start with testnet** - Use Phemex testnet before risking real funds
2. **Start small** - Use only 10-20% of your trading capital initially
3. **Monitor frequently** - Check positions and logs daily
4. **Set API restrictions** - Disable withdrawals on Phemex API keys
5. **Use Telegram alerts** - Stay informed of all trading actions
6. **Keep reserves** - Don't allocate 100% of account balance to bots
7. **Test thoroughly** - Backtest strategies before going live

---

## Support

- **Issues**: [GitHub Issues](https://github.com/pehur00/dcabot/issues)
- **Documentation**: `docs/` directory
- **Render Logs**: `render logs -s <service-name> --tail`

---

## Repository Information

**Repository:** https://github.com/pehur00/dcabot

**Branches:**
- `main` - Standalone bot (legacy, deprecated)
- `feature/saas-transformation` - Production SaaS platform (active)
- `feature/ai-glm-trading-bot` - AI bot development (merged)

**Key Dependencies:**
- Flask 3.0.0, PostgreSQL 14+
- pandas 2.2.0, numpy 1.26.3
- pytz 2023.3 (timezone support)
- cryptography 41.0.7 (encryption)

---

## License

MIT License - see [LICENSE](LICENSE) file for details.

---

**Trade responsibly. Start small. Test thoroughly.**
