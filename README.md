# DCA Bot - Martingale Trading Platform

A sophisticated cryptocurrency trading bot implementing a Martingale-style averaging strategy. Available as both a standalone bot and a multi-user SaaS platform.

## 🎯 Two Deployment Modes

### 1. Standalone Bot (Original)
Single-user bot running on your own infrastructure. Perfect for personal use.

- Deploy to Render, VPS, or run locally
- Configured via environment variables
- One bot per deployment
- See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)

### 2. SaaS Platform (New!)
Multi-user web platform with dashboard and bot management UI.

- **Web Dashboard**: Manage bots through a UI
- **Multi-User**: User registration and admin approval
- **Multiple Bots**: Each user can run multiple bots
- **Performance Charts**: Real-time metrics visualization
- **Admin Panel**: User management and registration control
- **Cost**: ~$22/month (Render + Database)

See [🚀 SaaS Platform](#-saas-platform) section below for details.

## Features

- **Martingale Strategy**: Systematic position averaging with EMA-based trend filtering
- **Volatility Protection**: Automatically pauses trading during high volatility
- **Telegram Notifications**: Real-time alerts for positions, profits, warnings
- **Risk Management**: Margin monitoring, position limits, liquidation protection
- **Multi-Symbol Support**: Trade multiple pairs simultaneously
- **Backtesting Framework**: Validate strategies on historical data
- **Cloud Ready**: Docker support and one-click deployment

## Quick Start (Standalone Mode)

### 1. Installation

```bash
git clone https://github.com/pehur00/dcabot.git
cd dcabot
pip install -r requirements.txt
```

### 2. Configuration

Create a `.env` file:

```bash
API_KEY=your_phemex_api_key
API_SECRET=your_phemex_api_secret
SYMBOL=BTCUSDT:Long:True
EMA_INTERVAL=1
TESTNET=True

# Optional: Telegram notifications
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### 3. Run Locally

```bash
dcabot-env/bin/python main.py
```

## 🚀 SaaS Platform

The SaaS platform transforms the standalone bot into a multi-user web application.

### Architecture

```
┌──────────────────────────────────────────────┐
│ Flask Web Dashboard (Render - $7/month)      │
│ • User authentication & registration         │
│ • Bot management UI                          │
│ • Trading pair configuration                 │
│ • Performance charts & analytics             │
│ • Admin panel                                │
└──────────────────────────────────────────────┘
              │
              ├─────────────────────────────────┐
              │                                 │
┌─────────────▼──────────┐   ┌─────────────────▼────────┐
│ Cron Scheduler (FREE)  │   │ PostgreSQL Database      │
│ • Runs every 5 minutes │   │ • Users & bots           │
│ • Executes all active  │   │ • Trading pairs          │
│   bots sequentially    │   │ • Metrics & logs         │
│ • Logs to database     │   │ • Trades history         │
└────────────────────────┘   └──────────────────────────┘
```

### Key Features

**Multi-User Management**
- User registration with admin approval
- Encrypted API credentials (Fernet encryption)
- Password hashing (bcrypt)
- Admin panel for user management

**Bot Dashboard**
- Create and manage multiple bots per user
- Configure trading pairs with different strategies
- Start/stop bots individually
- Real-time status monitoring

**Performance Analytics**
- Balance & Position overview charts
- Unrealized PnL tracking
- Margin level monitoring
- Trade history and activity logs

**Database-Driven Configuration**
- No environment variables per bot
- All configuration stored securely
- Easy bot cloning and management
- Automatic migration system

### Local Testing (SaaS Platform)

#### 1. Setup Local Database

```bash
# Start PostgreSQL (Docker)
docker run -d \
  --name dcabot-db \
  -e POSTGRES_USER=dcabot \
  -e POSTGRES_PASSWORD=dcabot_dev_password \
  -e POSTGRES_DB=dcabot_dev \
  -p 5435:5432 \
  postgres:15

# Set environment variables
export DATABASE_URL="postgresql://dcabot:dcabot_dev_password@localhost:5435/dcabot_dev"
export ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
export SECRET_KEY="dev-secret-key-change-in-production"

# Run database migrations
python saas/migrate.py
```

#### 2. Run Flask Web Server

```bash
# Terminal 1: Start Flask app
export FLASK_APP=saas.app
export FLASK_ENV=development
dcabot-env/bin/python -m flask run --port 3030

# Access at: http://localhost:3030
```

#### 3. Test Bot Execution

```bash
# Terminal 2: Execute all active bots once
export DATABASE_URL="postgresql://dcabot:dcabot_dev_password@localhost:5435/dcabot_dev"
python saas/execute_all_bots.py

# Or test a specific bot
export BOT_ID=1
python main.py
```

#### 4. Test Scripts

Located in `scripts/` directory:

```bash
# List and execute a specific bot
./scripts/test_bot_run.sh

# Continuous execution (simulates cron)
./scripts/run_bot_loop.sh
```

See [scripts/README.md](scripts/README.md) for details.

### Deployment Strategy

**Current Setup**:
- **Platform**: Render.com
- **Region**: Frankfurt (EU)
- **Branch**: `feature/saas-transformation`
- **Cost**: ~$22/month

**Services**:
1. **Web Service** (`dcabot-saas-web`)
   - Flask application with Gunicorn
   - Health checks and API endpoints
   - Automatic migrations on deploy
   - Cost: $7/month

2. **Cron Job** (`dcabot-saas-scheduler`)
   - Executes every 5 minutes
   - Runs all active bots sequentially
   - Logs results to database
   - Cost: FREE

3. **PostgreSQL Database** (Digital Ocean)
   - Stores users, bots, configurations
   - Tracks metrics and execution history
   - SSL-enabled connections
   - Cost: ~$15/month

**Migration System**:
- SQL files in `saas/migrations/`
- Automatic execution on deployment
- Tracks applied migrations in database
- See [docs/DATABASE_MIGRATIONS.md](docs/DATABASE_MIGRATIONS.md)

**Deployment Flow**:
```bash
# 1. Make changes
git add .
git commit -m "Add feature"

# 2. Push to GitHub
git push origin feature/saas-transformation

# 3. Render auto-deploys
# - Runs migrations
# - Builds app
# - Zero downtime
```

**Documentation**:
- **[Render Deployment Guide](docs/RENDER_DEPLOYMENT.md)** - Complete setup walkthrough
- **[Database Migrations](docs/DATABASE_MIGRATIONS.md)** - Schema management
- **[SaaS Platform Details](docs/SAAS.md)** - Architecture and implementation

## Strategy Overview

The bot implements a **Martingale averaging strategy**:

1. **Entry**: Opens positions when price is trending (EMA filter)
2. **Averaging**: Adds to losing positions with increasing size
3. **Profit Taking**: Systematically closes profitable positions
4. **Volatility Protection**: Pauses during high volatility
5. **Risk Management**: Maintains safe margin levels

See [docs/STRATEGY.md](docs/STRATEGY.md) for detailed explanation.

## Backtesting

Comprehensive backtesting framework to validate strategy performance:

```bash
# Basic backtest
dcabot-env/bin/python backtest/backtest.py \
  --symbol BTCUSDT \
  --days 30 \
  --balance 200 \
  --side Long

# Test multiple leverages
./test_leverages.sh BTCUSDT 30 200 Long

# Test top volume coins
dcabot-env/bin/python test_top_coins.py \
  --leverage 10 \
  --days 7 \
  --balance 200
```

Results include:
- 5-panel performance charts
- Balance history CSV
- Trade log CSV
- Detailed statistics

See [Backtesting section](#backtesting) in docs for more details.

## Documentation

### Platform Documentation
- **[SaaS Platform](docs/SAAS.md)** - Multi-user platform overview
- **[Render Deployment](docs/RENDER_DEPLOYMENT.md)** - Complete deployment guide
- **[Database Migrations](docs/DATABASE_MIGRATIONS.md)** - Schema management
- **[Local Testing](scripts/README.md)** - Development and testing

### Bot Documentation
- **[Strategy Explanation](docs/STRATEGY.md)** - How the Martingale strategy works
- **[Setup Guide](docs/SETUP.md)** - Local and remote installation
- **[Deployment Guide](docs/DEPLOYMENT.md)** - Deploy standalone bot
- **[Telegram Setup](docs/TELEGRAM_SETUP.md)** - Configure notifications

## Architecture

```
dcabot/
├── saas/                 # SaaS platform
│   ├── app.py           # Flask web application
│   ├── database.py      # Database utilities
│   ├── security.py      # Encryption & auth
│   ├── migrate.py       # Migration runner
│   ├── execute_all_bots.py  # Cron executor
│   ├── migrations/      # SQL migration files
│   └── templates/       # HTML templates
├── clients/             # Exchange API clients
├── strategies/          # Trading strategies
├── workflows/           # Execution workflows
├── notifications/       # Telegram notifier
├── indicators/          # Technical indicators
├── backtest/           # Backtesting framework
├── scripts/            # Testing & deployment scripts
└── docs/               # Documentation

```

## Configuration

Key strategy parameters (`strategies/MartingaleTradingStrategy.py`):

```python
CONFIG = {
    'leverage': 10,                   # Trading leverage
    'begin_size_of_balance': 0.006,   # Initial position: 0.6%
    'buy_until_limit': 0.05,          # Max position: 5%
    'profit_threshold': 0.003,        # Min profit: 0.3%
    'profit_pnl': 0.1,                # Target: 10% profit
    'max_margin_pct': 0.50,           # Margin cap: 50%
}
```

## Safety Features

- ✅ Testnet support for safe testing
- ✅ Rate limiting to prevent API bans
- ✅ Retry logic for failed requests
- ✅ Margin level monitoring
- ✅ Volatility detection and pausing
- ✅ Position size limits
- ✅ Emergency liquidation protection
- ✅ Dynamic position tapering
- ✅ Encrypted API credentials (SaaS)
- ✅ User authentication (SaaS)
- ✅ Admin approval system (SaaS)

## Requirements

- Python 3.8+
- Phemex account with API access
- (Optional) Telegram bot for notifications
- (SaaS) PostgreSQL database

## Risk Warning

⚠️ **WARNING**: Martingale strategies carry significant risk of large losses. This bot:
- Can experience extended drawdowns
- Requires sufficient capital for averaging
- Uses leverage (amplifies both gains and losses)
- May lose your entire trading account in extreme conditions

**Only use funds you can afford to lose completely.**

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Support

- **Issues**: Report bugs via GitHub Issues
- **Documentation**: See `docs/` directory
- **Strategy Questions**: See [STRATEGY.md](docs/STRATEGY.md)
- **Deployment Help**: See [RENDER_DEPLOYMENT.md](docs/RENDER_DEPLOYMENT.md)

## Changelog

See [CHANGELOG.md](docs/CHANGELOG.md) for version history.

## Disclaimer

This software is provided for educational purposes. Cryptocurrency trading carries significant risk. Past performance does not guarantee future results. The authors are not responsible for any financial losses incurred using this bot.

**Trade responsibly. Start small. Test thoroughly.**
