# DCABot - Agent Memory Bank

Last Updated: 2025-11-02 (Timezone Support & SaaS Architecture)

## Project Overview

**DCABot** is a **multi-user SaaS platform** for cryptocurrency trading that implements a **Martingale strategy** (not pure DCA) with intelligent risk management. Users can create and manage multiple trading bots through a web interface, with each bot automatically managing positions on Phemex exchange with advanced volatility protection and decline velocity detection.

**Architecture**: Multi-user SaaS Web Application + Scheduled Bot Executor
**Repository**: https://github.com/pehur00/dcabot
**Deployment**: Render.com (~$22/month: Web Service + PostgreSQL + Cron Job)
**Database**: PostgreSQL (Render Managed)
**Exchange**: Phemex (testnet and mainnet support)

## Core Strategy: Martingale Trading

### Philosophy
- **Average down** on losing positions to lower entry price
- **Increase position size** as price moves against you
- **Profit from mean reversion** when price recovers
- **Risk management** is critical - can blow up account if not careful

### Volatility Protection Behavior (IMPORTANT!)

**The bot uses NUANCED volatility protection - it doesn't always stop on high volatility:**

1. **High Volatility + CRASH/FAST_DECLINE** → ❌ **STOP** - Dangerous, skip all trades
2. **High Volatility + SLOW/MODERATE DECLINE** → ✅ **CONTINUE** - Safe for averaging

**Why?** Slow, steady declines are IDEAL for Martingale averaging, even with elevated volatility. The decline velocity check protects against sudden crashes (where you'd average into a freefall), not gradual declines (where averaging works well).

**Expected Telegram Behavior:**
- You WILL receive "High Volatility Alert" notifications
- Bot MAY still buy if decline velocity is safe (SLOW_DECLINE)
- This is CORRECT behavior, not a bug!

**Code Reference:** `strategies/MartingaleTradingStrategy.py:133-148`

### Key Parameters (strategies/MartingaleTradingStrategy.py)
```python
CONFIG = {
    'buy_until_limit': 0.02,           # Max 2% of balance in position
    'profit_threshold': 0.003,         # Min 0.3% profit to close
    'profit_pnl': 0.1,                 # 10% PnL target for full close
    'leverage': 10,                    # 10x leverage
    'begin_size_of_balance': 0.006,    # Start with 0.6% of balance
    'strategy_filter': 'EMA',          # EMA-based filtering
    'buy_below_percentage': 0.04,      # Buy when down 4%
    'max_margin_pct': 0.50,            # Max 50% margin usage (liquidation protection)
}
```

## Architecture

```
dcabot/
├── main.py                          # Entry point, orchestrates execution
├── strategies/
│   ├── TradingStrategy.py           # Abstract base class
│   └── MartingaleTradingStrategy.py # Core Martingale logic
├── workflows/
│   ├── Workflow.py                  # Abstract workflow base
│   └── MartingaleTradingWorkflow.py # Execution workflow
├── clients/
│   ├── TradingClient.py             # Abstract exchange client
│   └── PhemexClient.py              # Phemex API implementation
├── indicators/
│   └── volatility.py                # Volatility & decline velocity indicators
├── notifications/
│   └── TelegramNotifier.py          # Telegram alert system
├── utils/
│   └── retry.py                     # Retry logic & rate limiting
├── .env                             # Local config (not committed)
└── requirements.txt                 # Python dependencies
```

## Key Components

### 1. PhemexClient (clients/PhemexClient.py)
**Purpose**: Interface with Phemex exchange API

**Key Methods**:
- `get_position_for_symbol()` - Fetch current position
- `get_ticker_info()` - Get current bid/ask prices
- `get_account_balance()` - Get total and used balance
- `get_ema()` - Calculate EMA indicators
- `check_volatility()` - Analyze market volatility + decline velocity
- `place_order()` - Execute buy/sell orders
- `close_position()` - Close positions
- `cancel_all_open_orders()` - Cancel pending orders
- `set_leverage()` - Set position leverage

**Important Details**:
- Uses retry decorator with exponential backoff (3 retries)
- Rate limited to 10 requests/second
- Exceptions are re-raised to propagate to error handler

### 2. MartingaleTradingStrategy (strategies/MartingaleTradingStrategy.py)
**Purpose**: Core trading logic and decision making

**Key Methods**:
- `manage_position()` - Main decision engine (lines 46-172)
- `manage_profitable_position()` - Handle profit-taking
- `add_to_position()` - Add to losing positions (averaging down)
- `open_new_position()` - Start new positions
- `is_valid_position()` - Check if position management is needed

**Decision Flow**:
1. Check volatility and decline velocity
2. If position profitable → Take profits (partial or full)
3. If position losing → Add to position (with conditions)
4. If no position → Open new position (if automatic mode)

**Critical Logic** (lines 131-170):
```python
# Only add to position if:
margin_level < 2  # Critical margin (always add)
OR
(
  NOT dangerous_decline AND (
    (is_safe_decline AND position < 1.5x limit) OR  # Allow more on slow declines
    (not high_volatility AND standard_rules)
  )
)
```

### 3. Volatility Indicators (indicators/volatility.py)

**Traditional Indicators**:
- `calculate_atr()` - Average True Range
- `calculate_bollinger_bands()` - Bollinger Bands
- `calculate_historical_volatility()` - Historical volatility
- `is_high_volatility()` - Detects high volatility conditions

**Decline Velocity Detection** (NEW - lines 171-266):
**Purpose**: Distinguish between safe pullbacks and dangerous crashes

**Metrics**:
- **ROC-5**: Short-term rate of change (detects crashes)
- **ROC-15**: Medium-term rate of change (detects trend)
- **ROC-30**: Long-term rate of change (detects direction)
- **Smoothness Ratio**: ROC-5 / ROC-15 (jerky vs smooth)
- **Volume Ratio**: Recent volume / avg volume (panic selling detection)

**Velocity Score** (0-100):
- **0-20**: `SLOW_DECLINE` 🟢 - Safe for averaging down
- **20-40**: `MODERATE_DECLINE` 🟡 - Acceptable
- **40-70**: `FAST_DECLINE` 🟠 - Risky, be cautious
- **70-100**: `CRASH` 🔴 - Dangerous, avoid adding

**Strategy Integration**:
- **Slow/Moderate declines**: Allow 50% more position size (safer)
- **Fast declines/Crashes**: Pause additions (except margin critical)
- **Prevents blow-ups**: Avoids adding during flash crashes

### 4. Telegram Notifier (notifications/TelegramNotifier.py)

**Unified Position Updates** (notify_position_update):
- **OPENED** 🟢 - New position created
- **ADDED** 🔵 - Added to existing position
- **REDUCED** 🟡 - Partial position close
- **CLOSED** 🔴/🟢 - Full close (red=loss, green=profit)

**Alert Types**:
- `notify_position_update()` - All position changes
- `notify_high_volatility()` - High volatility detected
- `notify_decline_velocity_alert()` - Dangerous decline detected
- `notify_margin_warning()` - Margin level < 1.5
- `notify_error()` - Strategy execution errors
- `notify_bot_started()` - Bot startup (only if BOT_STARTUP=true)

**Position Update Details**:
```json
{
  "action": "ADDED",
  "symbol": "BTCUSDT",
  "side": "Buy (Long)",
  "qty": 0.123,
  "price": 50000,
  "position_size": 0.456,        // Total position size in BTC
  "position_value": 22800,       // Total USD value
  "position_pct": 2.28,          // % of account balance
  "balance": 1000000
}
```

### 5. Workflow (workflows/MartingaleTradingWorkflow.py)
**Purpose**: Orchestrate strategy execution

**Execution Steps**:
1. Prepare strategy (cancel orders, set leverage)
2. Retrieve information (position, price, EMAs, balance)
3. Validate position with `is_valid_position()`
4. If valid → `manage_position()`
5. If invalid → Log reason and skip

**Skip Reasons** (lines 48-77):
- No position - waiting for price > EMA200 (Long)
- No position - waiting for price < EMA200 (Short)
- Position exists with safe margin level (>= 2.0)
- Long position with price <= EMA200 (safe, no action)
- Short position with price >= EMA200 (safe, no action)

## Recent Enhancements (Oct 2025)

### 1. Decimal/Float Type Compatibility Fixes (Commits: 75b38d8, d722553, e899745) - **LATEST**
**Why**: Phemex API returns `Decimal` types for numeric values (balances, prices, positions), causing TypeErrors when used with Python `float` arithmetic
**What**: Comprehensive type conversion in all calculation functions
**Fixes**:
- `calculate_order_quantity()`: Convert all input parameters to float before calculations and tapering
- `check_margin_limit()`: Convert order_qty, current_price, total_balance to float
- `retrieve_information()`: Convert all API values to float immediately after retrieval (balances, prices, EMAs)
**Impact**:
- Bot no longer crashes with "unsupported operand type(s) for *: 'decimal.Decimal' and 'float'" errors
- All arithmetic operations work correctly throughout the strategy
- Type consistency maintained across entire calculation chain
**Files**: MartingaleTradingStrategy.py

### 2. Dynamic Position Size Tapering (Commit: 0253ad3)
**Why**: Prevent margin exhaustion and liquidations by gradually reducing order sizes as margin usage increases
**What**: Exponential tapering that scales down order quantities as you approach the margin cap
**Formula**: `taper_factor = ((max_margin_pct - current_margin_pct) / max_margin_pct) ** 2`
**Features**:
- **Exponential reduction**: At 0% margin = 100% size, 25% = 56%, 40% = 4%, 50% = 0%
- **More trades, smaller sizes**: Instead of 10 large adds, get 20+ smaller ones
- **Never hits hard cap**: Gradually approaches but never reaches 50% margin
- **Better price averaging**: More entry points = better average entry price
- **Volatility buffer**: Maintains room to survive normal price fluctuations
**Impact**:
- Solves the "XLM liquidation problem" where bot hit margin cap with no buffer
- Prevents getting liquidated right before favorable price moves
- More resilient to slow declines and sideways chop
- Applied to both live bot and backtest for consistency
**Files**: MartingaleTradingStrategy.py (calculate_order_quantity), backtest.py

### 2. 1h EMA100 Dip-Buying Filter + 50% Margin Protection (Commit: 765796e)
**Why**: Prevent liquidations and improve entry timing by buying dips instead of breakouts
**What**: Reversed entry strategy to buy BELOW 1h EMA100 with 50% margin cap
**Features**:
- **1h EMA100 Filter**: Long positions only open when price < 1h EMA100 (buy dips, not strength)
- **Margin Protection**: max_margin_pct = 0.50 prevents using more than 50% of balance as margin
- **No EMA Conflicts**: Removed 1min EMA200 requirement for new positions (was blocking deep dip entries)
- **Liquidation Prevention**: Pre-order validation blocks trades that would exceed margin cap
- **Telegram Alerts**: Notifies when orders are skipped due to margin protection
**Impact**:
- Buys genuine dips with upside potential (mean reversion advantage)
- Prevents early liquidations during crashes
- Better entry prices for Martingale averaging
- Allows entries during deep dips below both 1min EMA200 and 1h EMA100
**Backtest**:
- Added liquidation simulation (tracks when margin_level ≤ 1.0)
- Support for testing margin cap with --max-margin-pct flag
- Improved charts showing 1h EMA100 and position margin usage
**Files**: MartingaleTradingStrategy.py, MartingaleTradingWorkflow.py, TradingStrategy.py, backtest.py, README.md

### 3. Removed 1h EMA200 Requirement (Commit: c38a213)
**Why**: Strategy now uses configured `EMA_INTERVAL` for all EMAs instead of forcing 1h timeframe
**Impact**: More flexible and responsive to chosen interval
**Files**: MartingaleTradingStrategy.py, MartingaleTradingWorkflow.py

### 4. Enhanced Position Notifications (Commit: c38a213)
**Why**: Users needed complete position details for all actions
**What**: Unified notification system with action types (OPENED/ADDED/REDUCED/CLOSED)
**Details**: Shows position size, value, % of balance for all updates
**Files**: TelegramNotifier.py, MartingaleTradingStrategy.py

### 5. Decline Velocity Detection (Commit: 6079bcd)
**Why**: Martingale can blow up during fast crashes; slow declines are better for averaging
**What**: Multi-factor analysis to distinguish safe pullbacks from dangerous crashes
**Features**:
- Rate of change across 3 timeframes
- Smoothness ratio (jerky vs steady decline)
- Volume spike detection
- Velocity score (0-100)
- 4 decline types: SLOW/MODERATE/FAST/CRASH
**Impact**: Prevents adding during crashes, allows more position size during slow declines
**Files**: volatility.py, PhemexClient.py, MartingaleTradingStrategy.py, TelegramNotifier.py

### 6. Error Propagation Fix (Commit: 46ba5cd)
**Why**: Critical errors (invalid symbols, order failures) weren't triggering Telegram notifications
**What**: Re-raise exceptions after logging in PhemexClient methods
**Impact**: Users now get Telegram alerts for all critical failures
**Files**: PhemexClient.py (place_order, close_position, cancel_orders, set_leverage)

### 7. Improved Skip Logging (Commit: 5e81be1)
**Why**: Log message "wrong EMA side and margin level >= 200%" was confusing
**What**: Dynamic, context-aware skip reasons that explain exactly why
**Impact**: Users understand why bot is waiting
**Files**: MartingaleTradingWorkflow.py

## Configuration

### Environment Variables

**Required**:
- `API_KEY` - Phemex API key
- `API_SECRET` - Phemex API secret
- `SYMBOL` - Trading config (format: `SYMBOL:SIDE:AUTO`)
- `EMA_INTERVAL` - EMA interval in minutes (1, 5, 15, 30, 60, etc.)
- `TESTNET` - Use testnet (True) or mainnet (False)

**Optional**:
- `TELEGRAM_BOT_TOKEN` - Telegram bot token for notifications
- `TELEGRAM_CHAT_ID` - Telegram chat ID to receive alerts
- `BOT_STARTUP` - Send startup notification (True/False, default: False)

**Symbol Format Examples**:
```bash
SYMBOL=BTCUSDT:Long:True              # Auto-trade BTC Long
SYMBOL=ETHUSDT:Short:False            # Manual ETH Short
SYMBOL=BTCUSDT:Long:True,ETHUSDT:Short:True  # Multiple symbols
```

### Local Development (.env)
```bash
API_KEY=your_key_here
API_SECRET=your_secret_here
SYMBOL=ADAUSDT:Long:True
EMA_INTERVAL=1
TESTNET=True
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=545494173
BOT_STARTUP=False
```

### Docker/Render (bot.env or environment variables)
Same variables, but injected directly (no .env file in container)

## Current Architecture (SaaS Platform)

### Deployment Overview
**Type**: Multi-service SaaS Application
**Deployment**: Render.com
**Total Cost**: ~$22/month
**Blueprint**: render.yaml

### Services
```
Render.com:
├── dcabot-saas-web (Flask Web Service) - $7/month
│   ├── Flask 3.0 web application
│   ├── User authentication (Flask-Login + Google OAuth)
│   ├── Bot management dashboard
│   ├── Performance metrics API
│   ├── Timezone-aware date display
│   └── Auto-migrations on deploy
│
├── dcabot-saas-scheduler (Cron Job) - FREE
│   ├── Runs every 5 minutes (*/5 * * * *)
│   ├── Executes ALL active user bots
│   └── Writes metrics to database
│
└── PostgreSQL Database (Managed) - $15/month
    ├── User accounts with hashed passwords
    ├── Bot configurations (encrypted API keys)
    ├── Trading pairs per bot
    ├── Trade history
    ├── Execution logs
    ├── Performance metrics
    └── Backtest results
```

### How It Works
1. **User Registration**: Users sign up via web interface (with admin approval) or Google OAuth
2. **Bot Creation**: Users create bots with Phemex API credentials (encrypted with Fernet)
3. **Trading Pair Setup**: Configure symbols, leverage, side (Long/Short), automatic mode
4. **Scheduled Execution**: Cron job runs every 5 minutes and executes all active bots
5. **Real-time Monitoring**: Web dashboard shows bot status, trades, logs, and performance charts
6. **Timezone Support**: All timestamps displayed in user's local timezone

### Local Development
```bash
# Setup virtual environment
python3 -m venv dcabot-env
source dcabot-env/bin/activate
pip install -r requirements.txt
pip install -r requirements-saas.txt

# Start local PostgreSQL (Docker)
docker-compose up -d

# Run migrations
export DATABASE_URL="postgresql://dcabot:dcabot_dev_password@localhost:5435/dcabot_dev"
python saas/migrate.py

# Start web server
python saas/app.py

# Test bot execution
python saas/execute_all_bots.py
```

### Deployment Process
1. Push to GitHub main branch
2. Render detects changes and triggers build
3. Database migrations run automatically during build
4. If migrations succeed → new version deploys
5. If migrations fail → build stops, old version continues running
6. Both web service and cron job restart with new code

### Render CLI Access
```bash
render login
render services list
render logs -s dcabot-saas-web --tail
render logs -s dcabot-saas-scheduler --tail
```

### Documentation
- **Complete Guide**: `docs/SAAS.md` - Architecture, deployment, schema, troubleshooting
- **Deployment Guide**: `docs/RENDER_DEPLOYMENT.md` - Step-by-step deployment to Render
- **Branch**: `feature/saas-transformation` (separate from main)

### Key Files (SaaS only)
- `saas/app.py` - Flask web application with OWASP security controls
- `saas/validation.py` - Comprehensive input validation (SQL/XSS/Path traversal prevention)
- `saas/database.py` - PostgreSQL utilities
- `saas/security.py` - API key encryption (Fernet) + password hashing (PBKDF2-SHA256)
- `saas/execute_all_bots.py` - Cron executor for all bots
- `saas/migrate.py` - Database migration runner
- `saas/migrations/` - SQL migration files (version-controlled)
- `saas/templates/` - Jinja2 templates with professional dark theme
- `saas/static/css/style.css` - Trading platform-inspired UI (731 lines)
- `requirements-saas.txt` - SaaS-specific dependencies
- `render.yaml` - Render Blueprint (SaaS services only)

### Database Migration Strategy

**IMPORTANT**: This project uses SQL-based migrations, NOT seed scripts or ORM migrations.

**How Migrations Work**:
1. **Migration Files**: SQL files in `saas/migrations/` with sequential naming (001_, 002_, 003_)
2. **Automatic Execution**: Migrations run automatically during app startup/deployment
3. **Tracking**: `schema_migrations` table tracks which migrations have been applied
4. **Idempotent**: All migrations use `IF NOT EXISTS` / `IF EXISTS` / `ON CONFLICT DO NOTHING`

**Migration File Format**:
```sql
-- Migration: Brief description
-- Date: YYYY-MM-DD
-- Description: Detailed explanation

-- Table creation
CREATE TABLE IF NOT EXISTS table_name (...);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_name ON table_name(column);

-- Default/seed data (IMPORTANT: Put seed data IN migrations, not separate scripts)
INSERT INTO table_name (col1, col2) VALUES
    ('value1', 'value2'),
    ('value3', 'value4')
ON CONFLICT (unique_column) DO NOTHING;
```

**Naming Convention**:
- `001_initial_schema.sql` - Complete initial schema
- `002_add_oauth_columns.sql` - OAuth support
- `003_make_password_hash_nullable.sql` - Password hash nullable
- `004_add_backtest_tables.sql` - Next migration (backtest tables + seed data)

**Key Principles**:
- ✅ **DO**: Put seed/default data in migrations using `INSERT ... ON CONFLICT DO NOTHING`
- ✅ **DO**: Use `IF NOT EXISTS` for CREATE TABLE/INDEX
- ✅ **DO**: Test migrations locally before pushing
- ✅ **DO**: Make migrations idempotent (can run multiple times safely)
- ❌ **DON'T**: Create separate seed scripts (put data in migrations)
- ❌ **DON'T**: Edit existing migrations after deployment (create new migration)
- ❌ **DON'T**: Skip version numbers

**Testing Migrations Locally**:
```bash
export DATABASE_URL="postgresql://dcabot:password@localhost:5435/dcabot_dev"
python saas/migrate.py          # Run pending migrations
python saas/migrate.py --status # Check migration status
```

**Deployment Flow**:
1. Create migration file in `saas/migrations/`
2. Test locally with `python saas/migrate.py`
3. Commit and push to GitHub
4. Render auto-deploys and runs migrations during build phase
5. If migration fails → build stops, old version keeps running
6. If migration succeeds → new version starts

**Example: 001_initial_schema.sql**:
- Creates all tables (users, bots, trading_pairs, trades, bot_logs, etc.)
- Creates all indexes
- Inserts default settings: `INSERT INTO settings (key, value) VALUES ('registration_enabled', 'true') ON CONFLICT (key) DO NOTHING;`
- This is the pattern to follow: everything in one migration file

**Documentation**:
- `saas/migrations/README.md` - Migration system details
- `docs/DATABASE_MIGRATIONS.md` - Complete migration guide

### Recent SaaS Enhancements (November 2025)

#### 1. Timezone Support (November 2) - **LATEST**
**Why**: All timestamps were displayed in UTC, confusing for international users
**What**: Complete timezone support with auto-detection and user preferences
**Database Changes**:
- Migration `008_add_user_timezone_country.sql`:
  - Added `timezone` column (IANA timezone identifier, default: 'UTC')
  - Added `country_code` column (ISO 3166-1 alpha-2 country code)
  - Created index on timezone for efficient queries
**Backend Features**:
- `saas/timezone_utils.py`: Timezone conversion utilities
  - Country-to-timezone mapping (50+ countries)
  - Timezone validation using pytz
  - Timezone-aware datetime conversion
  - Jinja2 template filters for easy formatting
- Registration auto-detects browser timezone via JavaScript
- User class includes timezone attribute
- Settings page for changing timezone preferences
**Template Filters**:
- `user_timezone`: Format datetime in user's timezone with custom format
- `user_date`: Format date only
- `user_time`: Format time only
- `user_datetime_short`: Format datetime in short format (YYYY-MM-DD HH:MM)
- `timezone_offset`: Get UTC offset (e.g., '+01:00', '-05:00')
**Templates Updated**:
- `bot_detail.html`: All timestamps (created, last run, logs, trades) now timezone-aware
- `backtest_detail.html`: Test dates and execution timestamps timezone-aware
- `settings.html`: New settings page for timezone configuration
- `register.html`: Auto-detects and captures user timezone
- `base.html`: Added Settings link to navigation
**Impact**: Users see all dates/times in their local timezone, improving UX for international users
**Files**:
- Migration: `saas/migrations/008_add_user_timezone_country.sql`
- Utilities: `saas/timezone_utils.py`
- Backend: `saas/app.py` (User class, load_user, register, oauth, settings route)
- Templates: `bot_detail.html`, `backtest_detail.html`, `settings.html`, `register.html`, `base.html`

#### 2. Auto-Refresh & Detailed Logging (Commits: 7e4c1de, a70f20f)
**Enhanced Bot Execution Logging** (Commit: a70f20f):
**Why**: Generic "Nothing changed" messages didn't explain bot decision-making
**What**: Added detailed reasoning for all scenarios where no action is taken
**Features**:
- Position holding reasons with specific thresholds and percentages
- EMA alignment checks with actual price comparisons
- Market condition explanations (volatility, decline velocity)
- Manual mode indicators
**Examples**:
- Before: `"Nothing changed"`
- After: `"Holding position - position at limit (2.0% of balance); position in profit, waiting for dip"`
- After: `"Not opening position - price $150.25 above 1h EMA100 $148.50 (waiting for dip)"`
**Impact**: Full transparency into bot decision-making for monitoring and debugging
**Files**: `strategies/MartingaleTradingStrategy.py:67, 174-235`

**Auto-Refresh on Bot Detail Page** (Commit: 7e4c1de):
**Why**: Users had to manually refresh to see new bot execution results
**What**: Added polling mechanism to detect and auto-refresh when bot executes
**Backend**:
- New API endpoint `/api/bots/<bot_id>/last-execution`
- Returns latest execution timestamp from `execution_metrics` table
- Validates bot ownership before responding
**Frontend**:
- JavaScript polling every 30 seconds
- Detects new bot executions automatically
- Refreshes page when new data available
- Clean lifecycle (starts on load, stops on page leave)
**Impact**: Real-time updates to charts, logs, and trade history without manual refresh
**Files**: `saas/app.py:864-899`, `saas/templates/bot_detail.html:506-545`

#### 2. Professional UI/UX Redesign (Commits: c05403b, 5a4ad53)
**Inspired by**: Bybit, Binance, Phemex trading platforms
**Features**:
- **Dark Theme**: Professional color palette (#0B0E11 primary, #1E2329 secondary)
- **Trading Colors**: Green (#0ECB81) for Long/Buy, Red (#F6465D) for Short/Sell
- **Gradient Effects**: Cards with gradient borders, smooth transitions, glow effects
- **Space Optimization**: Charts side-by-side, horizontal Bot Info layout, compact spacing
- **Chart Layout**: 3 performance charts (Balance, PnL, Margin) displayed horizontally
- **Custom Styling**: Trading platform badges, monospace price fonts, custom scrollbar
- **Mobile Responsive**: Single-column stacking on mobile devices
**Files**: `saas/static/css/style.css`, `saas/templates/bot_detail.html`

#### 2. OWASP Security Controls (Commit: f8e3d5c)
**Protections**:
- **A01: Broken Access Control** - Path traversal detection
- **A03: Injection** - SQL/XSS/Null byte/Path traversal prevention
- **A07: Authentication Failures** - Strong password policy, input sanitization
**Features**:
- Comprehensive `validate_email()` with injection detection
- Strong password requirements (8+ chars, upper, lower, digit, special char, no common passwords)
- Input sanitization with HTML escaping, Unicode normalization, control character removal
- Pattern detection for SQL injection, XSS attacks, path traversal attempts
- Applied to all forms: registration, login, bot creation, trading pair creation
**Files**: `saas/validation.py`, `saas/app.py` (routes updated with validation)

#### 3. Production Error Handling Improvements
**Issue**: Bot execution failed when no trading pairs configured
**Fix**: Added validation in `main.py` to check for trading pairs before execution
**Error Message**: "Bot X has no active trading pairs configured. Please add at least one trading pair."
**Impact**: Clear user feedback instead of generic environment variable error
**Files**: `main.py:49-51`

#### 4. Database Schema Enhancements
**Tables**:
- `users` - User accounts with hashed passwords
- `bots` - Bot configurations with encrypted API keys
- `trading_pairs` - Symbol/side/leverage configs per bot
- `trades` - Trade history tracking
- `bot_logs` - Execution logs per bot
- `bot_metrics` - Performance tracking (balance, position, PnL, margin level)
**Migration System**: Automatic migrations via `saas/migrate.py` during Render deployment
**Files**: `saas/schema.sql`, `saas/migrate.py`

#### 5. Performance Metrics System
**API Endpoint**: `/api/bots/<bot_id>/metrics?days=7`
**Metrics Tracked**:
- Account balance over time
- Position value per symbol
- Unrealized PnL per symbol
- Margin level per symbol
- Timestamp history
**Visualization**: Chart.js integration with 3 interactive charts
**Files**: `saas/app.py:607-668`, `saas/templates/bot_detail.html:232-502`

### Implemented Features
✅ User registration/login with secure authentication (email + Google OAuth)
✅ Web dashboard for bot management
✅ Multi-bot support per user
✅ Trading pair management (CRUD operations)
✅ Real-time performance metrics with charts (Chart.js)
✅ Auto-refresh when bot executes (30s polling)
✅ Detailed bot decision logging (explains why no action taken)
✅ Bot execution logs and trade history
✅ Telegram notifications per user
✅ API key encryption (Fernet) and password hashing (PBKDF2-SHA256)
✅ OWASP security controls (input validation, injection prevention)
✅ Professional trading platform UI (Bybit/Binance-inspired dark theme)
✅ Automatic database migrations (SQL-based with version tracking)
✅ **Timezone support** (auto-detection, user preferences, 50+ countries)
✅ User settings page (timezone, country code, account info)

### Future Enhancements
- Backtest integration (test configs before deploying)
- Advanced analytics dashboard
- Multi-exchange support (Binance, Bybit)
- Portfolio-level risk management
- User API for programmatic bot control

See `docs/SAAS.md` for complete details on the SaaS platform.

## Important Patterns & Decisions

### 1. EMA-Based Entry/Exit
- **Long positions**: Only enter when price > EMA200
- **Short positions**: Only enter when price < EMA200
- **Reason**: Trend confirmation reduces false entries

### 2. Margin Level Thresholds
- **< 1.5**: Send margin warning (close to liquidation)
- **< 2.0**: Critical - always add to maintain margin
- **>= 2.0**: Safe - use normal strategy rules

### 3. Profit Taking Strategy
- **7.5% of balance**: Close 33% of position
- **10% of balance**: Close 50% of position
- **10% PnL**: Close full position

### 4. Position Sizing
- **Initial**: 0.6% of balance (6x leverage = 3.6% exposure)
- **Max position**: 2% of balance (6x leverage = 12% exposure)
- **Slow declines**: Allow up to 3% of balance (50% more)

### 5. Error Handling
- **Log errors** for debugging
- **Re-raise exceptions** to propagate to main.py
- **Telegram notifications** on all critical errors
- **Fail-fast** on invalid symbols or API failures

### 6. Notification Strategy
- **No spam**: BOT_STARTUP=False for cron jobs
- **Complete info**: All position updates include size, value, %
- **Context-aware**: Different alerts for different situations
- **Actionable**: Explains what action bot is taking

## Known Issues & Limitations

### 1. IP Binding (Phemex API)
**Issue**: Phemex API keys can be IP-restricted
**Symptom**: "401 Request IP mismatch" errors
**Solution**: Update API key IP whitelist in Phemex dashboard

### 2. Invalid Symbols
**Issue**: Not all symbols are supported on Phemex
**Example**: `1000PEPEUSDT` (invalid), `u1000PEPEUSDT` (valid)
**Solution**: Now sends Telegram notification on invalid symbols

### 3. Rate Limiting
**Issue**: Phemex has API rate limits
**Solution**: Rate limiter (10 req/sec) + retry with backoff
**Note**: May still hit limits during high-frequency trading

### 4. Leverage on Symbols
**Issue**: Different symbols have different max leverage
**Solution**: Bot attempts to set leverage, logs error if fails
**Note**: Check Phemex docs for per-symbol leverage limits

### 5. Position Value Calculation
**Issue**: Position value in USDT vs coins can be confusing
**Solution**: Notifications now show both:
- `position_size`: Amount in coins (e.g., 123.45 BTC)
- `position_value`: USD value (e.g., $6,172,500)

## Testing

### Manual Testing
```bash
# Test with testnet
export TESTNET=True
python main.py
```

### Backtesting Framework ✅
Complete backtesting system with 1-minute candle accuracy, testing every 5 minutes (matching live bot behavior).

**Basic Backtest**:
```bash
dcabot-env/bin/python backtest/backtest.py \
  --symbol HBARUSDT \
  --days 30 \
  --balance 200 \
  --side Long \
  --leverage 10 \
  --max-margin-pct 0.50 \
  --interval 1 \
  --source binance
```

**Parameters**:
- `--symbol`: Trading pair (e.g., HBARUSDT, BTCUSDT)
- `--days`: Number of days to backtest (e.g., 7, 30, 90, 180)
- `--balance`: Initial balance in USDT
- `--side`: Long or Short
- `--leverage`: Leverage multiplier (e.g., 5, 10, 15, 20)
- `--max-margin-pct`: Max margin usage cap (e.g., 0.50 = 50%)
- `--interval`: Candle interval (always use 1 for 1-minute)
- `--source`: Data source (binance recommended for history)

**Test Multiple Leverages** (`test_leverages.sh`):
```bash
./test_leverages.sh HBARUSDT 30 200 Long
# Tests 5x, 10x, 15x, 20x leverage
```

**Test Top Volume Coins** (`test_top_coins.py`):
```bash
# Test top 10 volume coins
dcabot-env/bin/python test_top_coins.py --leverage 10 --days 7

# Test specific coins
dcabot-env/bin/python test_top_coins.py --coins BTCUSDT ETHUSDT SOLUSDT --days 30

# Test top 5 with different settings
dcabot-env/bin/python test_top_coins.py --num-coins 5 --leverage 5 --days 60 --balance 500
```

**Features**:
- Fetches top volume coins from Binance (excludes stablecoins/fiat pairs)
- Runs backtests in sequence for all coins
- Saves individual results + summary CSV
- Filenames include: `{SYMBOL}_lev{X}x_{DAYS}d_{TIMESTAMP}_chart.png`

**Output Files** (saved to `backtest/results/`):
- `*_chart.png`: 5-panel visualization (price, balance, position size, drawdown, summary)
- `*_balance.csv`: Balance history over time
- `*_trades.csv`: Complete trade log
- `summary_lev{X}x_{DAYS}d_*.csv`: Performance comparison across all tested coins

**Backtest Accuracy**:
- Uses 1-minute candles for precise price action
- Checks every 5 minutes (matches live bot frequency)
- Includes all volatility protections and risk management
- Simulates exact margin calculations with configurable leverage
- Includes trading fees (0.075% per trade)
- Liquidation simulation (tracks margin_level ≤ 1.0)

### Testing Notifications
Set `BOT_STARTUP=True` to test Telegram bot startup notification

### Testing Invalid Symbols
Use invalid symbol like `1000PEPEUSDT` to test error notifications

## Future Improvements

### Potential Enhancements
1. **Blow-up Protection Circuit Breaker**
   - Max drawdown limit (15% from peak)
   - Hard position size limit (5% of account)
   - Time-based stop loss (48 hours max)
   - Large candle detection (>3% single candle)

2. **Multi-Symbol Portfolio Management**
   - Cross-symbol risk management
   - Portfolio-level position sizing
   - Correlation analysis

3. **Advanced Analytics**
   - Win rate tracking
   - Daily/weekly performance reports
   - Trade history database

4. **Web Dashboard**
   - Real-time position monitoring
   - Strategy parameter adjustment
   - Performance charts

5. **Additional Exchanges**
   - Bybit support (code exists but not used)
   - Binance integration
   - Multi-exchange arbitrage

## Debugging Tips

### 1. Check Logs
```bash
# Render
render logs -s martingale-trading-bot --tail

# Local
python main.py 2>&1 | tee bot.log
```

### 2. Common Log Messages
- `"Skipping position management"` - See reason field for why
- `"High volatility detected"` - Pausing new entries
- `"Dangerous decline detected"` - Fast crash, avoiding adds
- `"Failed to..."` - API error, check error_description

### 3. Telegram Not Working
- Check TELEGRAM_BOT_TOKEN is correct
- Check TELEGRAM_CHAT_ID is your user ID (not bot ID)
- Test: Send message to bot, get chat ID from updates

### 4. No Positions Opening
- Check EMA alignment (Long needs price > EMA200)
- Check automatic_mode is True in SYMBOL config
- Check volatility isn't too high
- Check decline velocity isn't showing CRASH

### 5. Position Not Closing
- Check profit_threshold (default 0.3% of total balance)
- Check position_factor >= buy_until_limit (2%)
- Check unrealised_pnl vs thresholds

## Critical Code Locations

### Strategy Decision Making
- `strategies/MartingaleTradingStrategy.py:46-172` - manage_position()
- `strategies/MartingaleTradingStrategy.py:131-156` - Add to position logic
- `strategies/MartingaleTradingStrategy.py:41-44` - is_valid_position()

### Volatility Analysis
- `indicators/volatility.py:171-266` - calculate_decline_velocity()
- `indicators/volatility.py:269-329` - is_high_volatility()
- `clients/PhemexClient.py:382-423` - check_volatility()

### Notifications
- `notifications/TelegramNotifier.py:69-134` - notify_position_update()
- `notifications/TelegramNotifier.py:180-204` - notify_decline_velocity_alert()
- `main.py:107-129` - execute_symbol_strategy() error handler

### Order Execution
- `clients/PhemexClient.py:425-489` - place_order()
- `clients/PhemexClient.py:491-523` - close_position()
- `strategies/MartingaleTradingStrategy.py:196-222` - add_to_position()

## User Credentials (Current Setup)

**Phemex API**:
- Key: 540fcfd6-0310-47eb-a0a6-29ef4dcad4f9
- Secret: (stored in .env, not in repo)

**Telegram**:
- Bot Token: 7981253761:AAHlQ27bKr7BwHQxdiaXemewaf0P9F14l7k
- Chat ID: 545494173

**Current Symbol**: ADAUSDT:Long:True
**Interval**: 1 minute
**Testnet**: True

## Git Repository

**Branches**:
- **main**: Standalone bot (production)
- **feature/saas-transformation**: SaaS platform (active development)

**Remote**: origin (https://github.com/pehur00/dcabot)

**Recent Commits (main)**:
- 5e81be1: Fix misleading skip log message
- 46ba5cd: Fix error propagation for Telegram notifications
- 6079bcd: Add decline velocity detection
- c38a213: Remove 1h EMA200 requirement and enhance notifications

**Recent Commits (feature/saas-transformation)**:
- 7e4c1de: Add auto-refresh for bot detail page when executions complete
- a70f20f: Improve bot execution logging with detailed reasoning
- 5a4ad53: Optimize bot detail page layout for better space utilization
- c05403b: Redesign UI with Bybit/Binance/Phemex-inspired dark theme
- d0f96b3: Improve bot execution error handling for missing trading pairs
- f8e3d5c: Implement OWASP security controls (validation.py)
- [Multiple earlier commits]: Database schema, migrations, metrics system

**Workflow (main branch)**:
1. Make changes locally
2. Test with `python main.py`
3. Commit with detailed message
4. Push to main
5. Render auto-deploys

**Workflow (SaaS branch)**:
1. Make changes locally
2. Test with local Flask app (`python saas/app.py`)
3. Commit with detailed message
4. Push to feature/saas-transformation
5. Render auto-deploys SaaS services

## Dependencies

**Core**:
- pandas==2.2.0
- numpy==1.26.3
- requests==2.31.0

**Exchange**:
- pybit==5.6.2 (not actively used)
- pycryptodome==3.20.0

**Utilities**:
- python-json-logger==3.2.1
- python-dateutil==2.2
- pytz==2023.3.post1

**Monitoring**:
- websocket-client==1.7.0
- websockets==12.0

## Contact & Support

**Issues**: https://github.com/pehur00/dcabot/issues
**Telegram**: @pehur_tradingbot (bot username)

---

**End of Memory Bank**
