# DCABot System Architecture

**Last Updated:** November 6, 2025

This document provides a comprehensive overview of the DCABot trading platform architecture, components, and design decisions.

> **Note:** For quick AI assistance context, see [../.claude/CLAUDE.md](../.claude/CLAUDE.md)

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Component Architecture](#component-architecture)
3. [Database Design](#database-design)
4. [Security Architecture](#security-architecture)
5. [Trading Strategies](#trading-strategies)
6. [Deployment Architecture](#deployment-architecture)
7. [Code Organization](#code-organization)

---

## System Overview

DCABot is a multi-user SaaS platform for cryptocurrency trading that implements two distinct trading approaches:

1. **AI Trading Bots**: LLM-powered decision making using multiple AI models (GLM, DeepSeek, Claude)
2. **Martingale Strategy**: Systematic averaging down with intelligent risk management

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      Users (Web Browser)                 │
└───────────────────────┬─────────────────────────────────┘
                        │ HTTPS
                        ▼
┌─────────────────────────────────────────────────────────┐
│              Flask Web Application (Gunicorn)            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │ Auth Routes  │  │  Bot Routes  │  │ Admin Routes │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │ AI Bot Routes│  │ API Endpoints│  │  Dashboard   │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
└───────────┬───────────────┬─────────────────┬──────────┘
            │               │                 │
            ▼               ▼                 ▼
┌──────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│   PostgreSQL     │ │  Phemex API     │ │   AI Model APIs │
│   Database       │ │  (Exchange)     │ │  (GLM, DeepSeek,│
│                  │ │                 │ │   Claude)       │
└──────────────────┘ └─────────────────┘ └─────────────────┘
            ▲               ▲                 ▲
            │               │                 │
┌───────────┴───────────┬───┴─────────────┬───┴──────────┐
│                       │                 │              │
│  ┌──────────────────┐ │ ┌─────────────┐ │ ┌──────────┐│
│  │ AI Bot Executor  │ │ │  Martingale │ │ │  Weekly  ││
│  │  (Cron: */5)     │ │ │   Executor  │ │ │ Backtest ││
│  │                  │ │ │ (Cron: */5) │ │ │(Cron:Sun)││
│  └──────────────────┘ │ └─────────────┘ │ └──────────┘│
│                                                         │
│              Background Services (Render)              │
└─────────────────────────────────────────────────────────┘
```

---

## Component Architecture

### 1. Flask Web Application

**Purpose**: Main user interface and API

**Key Components**:
- **Authentication**: Flask-Login + Google OAuth
- **Bot Management**: Create, configure, start/stop bots
- **Dashboards**: Real-time performance visualization (Chart.js)
- **Admin Panel**: User approval, system settings
- **API Endpoints**: RESTful API for data access

**Technology Stack**:
- Flask 3.0 (Web framework)
- Jinja2 (Template engine)
- Chart.js (Charting library)
- Gunicorn (Production server)

**File**: `saas/app.py` (1500+ lines)

---

### 2. AI Bot Executor

**Purpose**: Execute AI trading bot decisions every 5 minutes

**Execution Flow**:
```
1. Fetch all active AI bots from database
2. For each bot:
   a. Decrypt API keys (Phemex, AI model)
   b. Fetch real-time balance from Phemex
   c. Fetch market data (price, indicators, sentiment)
   d. Send data to AI model for decision
   e. Log decision with reasoning to database
   f. Execute trade on Phemex if recommended (confidence ≥ 70%)
   g. Update performance metrics
3. Log execution results
```

**Key Features**:
- Multi-model support (GLM, DeepSeek, Claude)
- Real balance tracking (no virtual construct)
- Position persistence across restarts
- Confidence threshold enforcement (70%)
- Multi-symbol support per bot

**Files**:
- `saas/execute_ai_bots.py` - Main executor
- `strategies/AITradingStrategy.py` - AI decision logic
- `data/market_data_fetcher.py` - Market data collection

---

### 3. Martingale Bot Executor

**Purpose**: Execute Martingale strategy bot decisions every 5 minutes

**Execution Flow**:
```
1. Fetch all active Martingale bots from database
2. For each bot:
   a. Decrypt Phemex API keys
   b. Retrieve account balance and positions
   c. For each trading pair:
      - Check volatility conditions
      - Check decline velocity
      - Calculate position size with tapering
      - Make decision (OPEN/ADD/HOLD/CLOSE)
      - Execute trades on Phemex
      - Update database with results
   d. Send Telegram notifications
3. Log execution metrics
```

**Key Features**:
- EMA-based entry filter (dip-buying strategy)
- Volatility protection (pauses during high volatility + fast declines)
- Dynamic position tapering (exponential)
- Margin protection (50% max)
- Decline velocity detection

**Files**:
- `saas/execute_all_bots.py` - Main executor
- `strategies/MartingaleTradingStrategy.py` - Core logic
- `indicators/volatility.py` - Volatility calculations

---

### 4. Market Data Fetcher

**Purpose**: Fetch comprehensive market data for AI bots

**Data Sources**:
1. **Technical Data (Binance API)**:
   - Current price
   - EMAs (20 1m, 50 5m, 100 1h)
   - RSI-14
   - Volume trends
   - Price changes (24h, 1h)

2. **Sentiment Data**:
   - Fear & Greed Index (alternative.me)
   - Future: News headlines (CoinDesk, CryptoPanic)

**Output Format**:
```python
{
    "symbol": "BTCUSDT",
    "current_price": 68500.00,
    "ema20_1m": 68450,
    "ema50_5m": 68300,
    "ema100_1h": 68000,
    "rsi": 65,
    "volume_trend": "INCREASING",
    "trend": "1m bullish, 5m bullish, above 1h EMA100",
    "sentiment": "Fear & Greed: 72/100 (GREED)",
    "change_24h": +2.5,
    "change_1h": +0.8
}
```

**File**: `data/market_data_fetcher.py`

---

### 5. Phemex Client

**Purpose**: Unified interface for Phemex exchange API

**Key Methods**:
- `get_account_balance()` - Fetch account balance
- `get_position_for_symbol()` - Get current position
- `place_order()` - Place new order
- `close_position()` - Close existing position
- `get_market_data()` - Fetch market prices
- `check_volatility()` - Calculate volatility metrics
- `get_trade_history()` - Fetch trade history

**Features**:
- Testnet/mainnet support
- Rate limiting (10 req/sec)
- Retry with exponential backoff
- Error handling and logging
- Type conversion (Decimal → float)

**File**: `clients/PhemexClient.py`

---

### 6. Database Layer

**Purpose**: PostgreSQL connection and query abstraction

**Key Functions**:
- User management (CRUD)
- Bot configuration (CRUD)
- Trading pairs management
- Execution logging
- Performance metrics storage
- Migration runner

**Features**:
- Parameterized queries (SQL injection prevention)
- Connection pooling
- Transaction support
- Migration tracking

**File**: `saas/database.py`

---

## Database Design

### Schema Overview

```
Users & Authentication
├── users (user accounts, OAuth)
└── schema_migrations (migration tracking)

Martingale Bots
├── bots (bot configuration)
├── trading_pairs (symbol/side/leverage per bot)
├── trades (trade history)
├── bot_logs (execution logs)
├── bot_metrics (performance snapshots)
└── execution_metrics (execution timestamps)

AI Trading Bots
├── ai_model_configs (model specifications)
├── ai_bots (bot configuration with unique Phemex credentials)
├── ai_decisions (decision history with reasoning)
├── ai_bot_trades (trade execution log with PnL - migration 017)
└── ai_model_performance (performance snapshots)

Backtesting
├── backtest_configs (symbols to test weekly)
├── backtest_results (weekly backtest outcomes)
└── backtest_trades (detailed trade log)
```

### Key Design Decisions

**1. Encrypted API Keys**:
- All API keys encrypted with Fernet before storage
- Encryption key stored in environment variable
- Decrypted only when needed for API calls

**2. Real Balance Tracking (AI Bots)**:
- Architecture: 1 Bot = 1 Phemex Account = 1 AI Model
- No virtual balance construct (removed in migration 016)
- `initial_balance_snapshot` saved when bot created
- PnL calculated as: `current_phemex_balance - initial_balance_snapshot`
- Trade execution logged in `ai_bot_trades` table (migration 017)

**3. Migration System**:
- SQL-based migrations (not ORM)
- Sequential naming (`001_`, `002_`, etc.)
- Tracked in `schema_migrations` table
- Auto-run on deployment
- Idempotent (use `IF NOT EXISTS`)

**See [DATABASE_MIGRATIONS.md](DATABASE_MIGRATIONS.md) for details.**

---

## Security Architecture

### Authentication
- **Password hashing**: PBKDF2-SHA256 with salt
- **Session management**: Flask-Login
- **OAuth 2.0**: Google authentication
- **Admin approval**: New users require approval

### Encryption
- **API Keys**: Fernet symmetric encryption
- **Database connections**: SSL/TLS required
- **HTTPS**: All web traffic encrypted

### Input Validation
- **SQL Injection**: Parameterized queries only
- **XSS Prevention**: HTML escaping in templates
- **Path Traversal**: Pattern detection and blocking
- **CSRF Protection**: Flask built-in CSRF tokens

**Files**:
- `saas/security.py` - Encryption utilities
- `saas/validation.py` - OWASP security controls (460 lines)

---

## Trading Strategies

### AI Trading Strategy

**Decision Process**:
```
Market Data → AI Model → Decision → Trade Execution
     ↓           ↓           ↓              ↓
 Technical   GLM/DeepSeek  BUY/SELL/    Phemex API
 + Sentiment  + Claude     HOLD with    (automated)
 + News                    reasoning
```

**AI Prompt Structure**:
```
TECHNICAL ANALYSIS:
- Current Price: $68,500
- EMA20 (1m): $68,450
- EMA50 (5m): $68,300
- EMA100 (1h): $68,000
- RSI-14: 65
- Volume Trend: INCREASING
- Price Change 24h: +2.5%

MARKET SENTIMENT:
- Fear & Greed Index: 72/100 (GREED)

CURRENT POSITION:
- Side: Long
- Entry Price: $67,000
- Current PnL: +2.24%

TRADING RULES:
- Max Leverage: 10x
- Max Position Size: 5% of balance
- Confidence Threshold: 70% to execute

TASK: Analyze and decide BUY/SELL/HOLD with confidence % and reasoning
```

**Response Format**:
```json
{
  "decision": "BUY",
  "confidence": 75,
  "reasoning": "Strong bullish setup with aligned EMAs...",
  "risk_level": "MEDIUM",
  "stop_loss": 67500.0,
  "take_profit": 70000.0
}
```

---

### Martingale Strategy

**Core Logic**:
1. **Entry**: Price < EMA100 (Long) or > EMA100 (Short)
2. **Add to Position**: When down 4%, increase size exponentially
3. **Position Tapering**: `taper_factor = ((max_margin - current_margin) / max_margin) ** 2`
4. **Profit Taking**: Close when ≥ 0.3% profit or 10% PnL

**Safety Mechanisms**:
```python
# Volatility Protection
if high_volatility and (decline_velocity in ["FAST_DECLINE", "CRASH"]):
    PAUSE_TRADING  # Dangerous!
elif high_volatility and (decline_velocity in ["SLOW_DECLINE", "MODERATE_DECLINE"]):
    CONTINUE_TRADING  # Safe for averaging

# Margin Protection
if current_margin_pct >= 50%:
    BLOCK_NEW_POSITIONS  # Never hit hard cap
elif current_margin_pct >= 40%:
    position_size *= 0.04  # 4% of normal size
```

**See [STRATEGY.md](STRATEGY.md) for detailed explanation.**

---

## Deployment Architecture

### Render.com Services

```
render.yaml (Blueprint)
├── dcabot-saas-web (Web Service) - $7/month
│   ├── Build: pip install + migrations
│   ├── Start: gunicorn -w 4 -b 0.0.0.0:$PORT saas.app:app
│   └── Auto-deploy on push to feature/saas-transformation
│
├── dcabot-saas-scheduler (Cron Job) - FREE
│   ├── Schedule: */5 * * * * (every 5 minutes)
│   ├── Command: python saas/execute_all_bots.py
│   └── Executes all active Martingale bots
│
├── dcabot-ai-executor (Cron Job) - FREE
│   ├── Schedule: */5 * * * * (every 5 minutes)
│   ├── Command: python saas/execute_ai_bots.py
│   └── Executes all active AI bots
│
└── dcabot-weekly-backtests (Cron Job) - FREE
    ├── Schedule: 0 2 * * 0 (Sunday 2 AM UTC)
    ├── Command: python saas/run_weekly_backtests.py
    └── Runs backtests for top symbols
```

### External Dependencies

- **PostgreSQL Database**: Managed database (Digital Ocean, AWS RDS, etc.)
- **Phemex API**: Cryptocurrency exchange
- **AI Model APIs**: GLM (z.ai), DeepSeek, Anthropic (Claude)
- **Binance API**: Market data source
- **Alternative.me API**: Fear & Greed Index

**See [RENDER_DEPLOYMENT.md](RENDER_DEPLOYMENT.md) for deployment guide.**

---

## Code Organization

### Project Structure

```
dcabot/
├── saas/                        # SaaS Platform
│   ├── app.py                   # Flask routes (1500+ lines)
│   ├── database.py              # Database layer (800+ lines)
│   ├── execute_all_bots.py      # Martingale executor (400+ lines)
│   ├── execute_ai_bots.py       # AI bot executor (450+ lines)
│   ├── security.py              # Encryption utilities
│   ├── validation.py            # OWASP security (460 lines)
│   ├── timezone_utils.py        # Timezone conversion
│   ├── migrations/              # SQL migration files
│   │   ├── 001_initial_schema.sql
│   │   ├── 012_create_ai_bot_tables.sql
│   │   └── 016_redesign_real_balance.sql
│   └── templates/               # Jinja2 HTML templates
│       ├── ai_bots_dashboard.html
│       ├── dashboard.html
│       └── base.html
│
├── strategies/                  # Trading Strategy Logic
│   ├── TradingStrategy.py       # Abstract base class
│   ├── MartingaleTradingStrategy.py  # Martingale logic (600+ lines)
│   └── AITradingStrategy.py     # AI decision logic (450+ lines)
│
├── data/                        # Data Collection
│   └── market_data_fetcher.py   # Technical + sentiment data (400+ lines)
│
├── clients/                     # Exchange Clients
│   ├── PhemexClient.py          # Phemex API wrapper (800+ lines)
│   └── BybitClient*.py          # Bybit (not actively used)
│
├── indicators/                  # Technical Indicators
│   └── volatility.py            # ATR, Bollinger, decline velocity
│
├── notifications/               # Notification Services
│   └── TelegramNotifier.py      # Telegram alerts
│
├── backtest/                    # Backtesting Framework
│   └── backtest.py              # Backtest engine (1000+ lines)
│
├── scripts/                     # Helper Scripts
│   ├── run_bot.sh
│   ├── test_bot_run.sh
│   └── README.md
│
└── docs/                        # Documentation
    ├── ARCHITECTURE.md          # This file
    ├── RENDER_DEPLOYMENT.md
    ├── LOCAL_SETUP.md
    ├── DATABASE_MIGRATIONS.md
    ├── STRATEGY.md
    └── ROADMAP.md
```

### Key File Locations

**Strategy Decision Making**:
- `strategies/MartingaleTradingStrategy.py:46-172` - manage_position()
- `strategies/AITradingStrategy.py:84-297` - get_ai_decision()

**Volatility & Risk Management**:
- `indicators/volatility.py:171-266` - calculate_decline_velocity()
- `indicators/volatility.py:269-329` - is_high_volatility()

**Trade Execution**:
- `clients/PhemexClient.py:425-489` - place_order()
- `clients/PhemexClient.py:491-523` - close_position()

**AI Bot System**:
- `saas/execute_ai_bots.py:252-407` - execute_decision()
- `saas/database.py:600-650` - log_ai_bot_trade()
- `data/market_data_fetcher.py:44-195` - fetch_market_data()

---

## Migration System

### How Migrations Work

1. **Create Migration**: Add new SQL file `saas/migrations/NNN_description.sql`
2. **Test Locally**: `python saas/migrate.py`
3. **Commit & Push**: Git tracks migration files
4. **Auto-Deploy**: Render runs migrations during build phase
5. **Tracking**: Applied migrations stored in `schema_migrations` table

**Migration Principles**:
- Idempotent (use `IF NOT EXISTS`)
- Sequential numbering
- No edits after deployment
- Rollback via new migration

**See [DATABASE_MIGRATIONS.md](DATABASE_MIGRATIONS.md) for details.**

---

## Performance Considerations

### Database Optimization
- Indexed columns: user_id, bot_id, symbol, created_at
- Connection pooling
- Prepared statements (parameterized queries)

### API Rate Limiting
- Phemex: 10 requests/second (with rate limiter)
- AI Models: Varies by provider
- Retry with exponential backoff

### Caching Strategy
- No caching currently (future enhancement)
- Future: Redis for session storage, market data

---

## Monitoring & Observability

### Logs
- **Web App**: Render logs (`render logs -s dcabot-saas-web --tail`)
- **Executors**: Cron job logs (`render logs -s dcabot-ai-executor --tail`)
- **Database**: `bot_logs`, `ai_decisions` tables

### Metrics Tracked
- Bot execution count per cycle
- Trade execution success/failure rate
- API costs per AI model
- Performance metrics (balance, PnL, win rate)
- Execution timestamps (for auto-refresh)

### Health Checks
- `/health` endpoint - Returns system status
- Database connectivity check
- Active bot count

---

## Future Enhancements

### Planned Improvements
1. **WebSocket Support**: Real-time updates without polling
2. **Redis Caching**: Session storage, market data caching
3. **Enhanced Monitoring**: Datadog/Sentry integration
4. **Multi-Exchange Support**: Binance, Bybit, OKX
5. **Advanced Backtesting**: Integrated into web dashboard

**See [ROADMAP.md](ROADMAP.md) for full roadmap.**

---

**End of Architecture Documentation**
