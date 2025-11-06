# Changelog

**Last Updated:** November 6, 2025

All notable changes to the DCABot SaaS Trading Platform.

---

## [2025-11] - SaaS Platform in Production

### Major Features

**Multi-User SaaS Platform**
- Google OAuth authentication with admin approval system
- Multi-user support with isolated bot configurations
- Encrypted API key storage (Fernet encryption)
- Timezone support for 50+ countries
- Real-time Chart.js dashboards
- Admin panel for user management

**AI Trading Bots** 🤖
- Multi-model support: GLM-4.5-Air, DeepSeek-Chat, Claude-3.5-Sonnet, Gemini-1.5-Flash
- Real balance tracking: 1 Bot = 1 Phemex Account = 1 AI Model
- Comprehensive market data (technical indicators + Fear & Greed Index)
- Live execution every 5 minutes with 70% confidence threshold
- Complete trade logging with PnL tracking (`ai_bot_trades` table)
- Model-specific colored dashboards for comparison
- Decision history with AI reasoning logged

**Martingale Strategy Bots**
- EMA-based entry filtering (only buy dips: price < EMA100 for long)
- Volatility protection with decline velocity detection
- Dynamic position tapering (exponential sizing)
- 50% margin cap with pre-order validation
- Support for multiple trading pairs per bot
- Automated execution via Render cron jobs

**Deployment & Infrastructure**
- Render.com Blueprint deployment (zero-config)
- Automated database migrations on deploy
- Web Service ($7/month) + Cron Jobs (FREE)
- PostgreSQL with encrypted credentials
- Auto-scaling support

### November 5, 2025 - AI Bot Trades Tracking (Migration 017)
**Added:**
- `ai_bot_trades` table for complete audit trail
- Trade logging with entry/exit prices, PnL, fees, balance changes
- Dashboard TRADES tab showing full trade history
- Trade PnL calculation: `(exit_price - entry_price) * qty - fees`

**Files Modified:**
- `saas/migrations/017_add_ai_bot_trades.sql`
- `saas/execute_ai_bots.py` - Added trade logging after execution
- `saas/database.py` - Added `log_ai_bot_trade()` function
- `saas/templates/ai_bots_dashboard.html` - TRADES tab UI

### November 5, 2025 - AI Bot Real Balance Architecture (Migration 016)
**Changed:**
- Removed virtual balance system (caused drift from reality)
- Each AI bot now requires unique Phemex API keys
- Real balance fetched directly from Phemex (no virtual construct)
- `initial_balance_snapshot` saved when bot created
- PnL calculated as: `current_phemex_balance - initial_balance_snapshot`

**Why:**
- Virtual balance drifted from actual account balance
- No position persistence across bot restarts
- Couldn't calculate accurate PnL per AI model
- Race conditions with shared API keys

**Removed:**
- `virtual_balance` column from `ai_bots` table
- `ai_bot_balance_history` table
- Virtual balance tracking logic

**Added:**
- `testnet` flag per AI bot
- `initial_balance_snapshot` for PnL calculation
- `snapshot_taken_at` timestamp
- Real balance fetching from Phemex API

### October 2025 - AI Trading Bots (Migrations 012-015)
**Added:**
- AI model configurations (GLM, DeepSeek, Claude, Gemini)
- AI bot creation and management
- AI decision logging with reasoning
- Market data fetcher with technical + sentiment data
- AI bot executor (runs every 5 minutes via cron)
- Model performance tracking
- Multi-model comparison dashboards

### September 2025 - SaaS Transformation (Migrations 001-011)
**Added:**
- User authentication system (Google OAuth)
- Multi-user bot management
- Admin approval system
- Database migration framework (SQL-based)
- Encrypted API key storage (Fernet)
- Web dashboard with Chart.js
- Telegram notifications per user
- Timezone support
- Performance metrics tracking
- Execution logs and history

**Changed:**
- Migrated from standalone bot to SaaS platform
- Database-driven configuration (no more config.json)
- Web-based bot creation and management
- Centralized execution via cron jobs on Render

---

## [2024-12] - Standalone Bot (Legacy)

### v4 - Advanced Risk Management
**Added:**
- Telegram notifications for all trading actions
- ATR and Bollinger Band volatility monitoring
- Automatic trading pause during high volatility
- Error handling with exponential backoff retry
- Rate limiting (10 requests/second)
- Comprehensive documentation (STRATEGY.md, DEPLOYMENT.md)

**Fixed:**
- `parse_symbols()` splitting bug
- `PhemexAPIException` inheritance issue
- Margin level calculation improvements

**Changed:**
- More conservative position management
- Volatility-aware entry/exit logic

### v3 - Phemex Integration
**Added:**
- Phemex exchange support
- Job-based execution (single iteration for cron)
- Position management improvements

### v2 - Strategy Enhancement
**Added:**
- EMA-based entry filtering
- Multi-strategy preparation
- Refactored class structure

### v1 - Initial Release
**Added:**
- Basic Martingale averaging strategy
- Bybit exchange support
- Position sizing logic
- Basic risk management

---

## Migration History

| Migration | Date | Description |
|-----------|------|-------------|
| 017 | Nov 5, 2025 | Add AI bot trades tracking table |
| 016 | Nov 5, 2025 | Redesign AI bots for real balance tracking |
| 012-015 | Oct 2025 | Create AI trading bot tables and features |
| 001-011 | Sep 2025 | SaaS platform foundation |

**See [DATABASE_MIGRATIONS.md](DATABASE_MIGRATIONS.md) for complete migration details.**

---

## Upcoming Features

**See [ROADMAP.md](ROADMAP.md) for planned enhancements:**
- Real-time WebSocket updates (eliminate polling)
- News headline integration for AI models
- User-initiated backtests from dashboard
- Portfolio-level analytics
- Multi-exchange support (Binance, Bybit)
- Advanced risk management controls

---

## Versioning Notes

- **Pre-SaaS (v1-v4):** Standalone bot with local configuration
- **SaaS Platform (2025):** Multi-user platform with database-driven config
- **Current:** Migration-based versioning (numbered migrations)

---

**For detailed system architecture, see [ARCHITECTURE.md](ARCHITECTURE.md)**
