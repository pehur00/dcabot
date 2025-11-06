# DCABot - AI Context for Development

**Last Updated:** November 6, 2025
**Project:** Multi-User SaaS Cryptocurrency Trading Platform
**Status:** Production (Render.com)
**Branch:** `feature/saas-transformation`

---

## Quick Reference

### What This Project Is
A SaaS platform for cryptocurrency trading with two strategies:
1. **AI Trading Bots** - LLM-powered decisions (GLM, DeepSeek, Claude, Gemini)
2. **Martingale Strategy** - EMA-based dip-buying with intelligent risk management

### Tech Stack
- **Backend:** Flask 3.0, Python 3.10+, PostgreSQL 14+
- **Deployment:** Render.com (Blueprint), Gunicorn
- **Security:** Fernet encryption (API keys), PBKDF2 (passwords)
- **APIs:** Phemex (trading), AI models (GLM, DeepSeek, Claude)

---

## Current System State

### What's Working in Production
1. **Martingale Bots**
   - EMA-based entry (only buy dips: price < EMA100 for long)
   - Volatility protection with decline velocity detection
   - Dynamic position tapering (exponential)
   - 50% margin cap with pre-order validation
   - Running on Phemex testnet + mainnet

2. **AI Trading Bots**
   - Multi-model support: GLM-4.5-Air ($2.50/mo), DeepSeek ($3.50/mo), Claude ($150/mo)
   - Real balance tracking: 1 Bot = 1 Phemex Account = 1 AI Model
   - Comprehensive market data (technical + sentiment)
   - Live execution every 5 minutes with 70% confidence threshold
   - Complete trade logging with PnL tracking

3. **SaaS Platform**
   - Multi-user with Google OAuth
   - Encrypted API keys (Fernet)
   - Auto-migrations on deploy
   - Real-time Chart.js dashboards
   - Timezone support (50+ countries)
   - Admin approval system

---

## Recent Changes (Last 30 Days)

### November 5, 2025 - AI Bot Trades Tracking
**What Changed:**
- Added `ai_bot_trades` table for complete audit trail
- Executor logs every trade with entry/exit prices, PnL, fees
- Dashboard TRADES tab shows full trade history
- Trade PnL: `(exit_price - entry_price) * qty - fees`

**Key Files:**
- `saas/migrations/017_add_ai_bot_trades.sql`
- `saas/execute_ai_bots.py` - Added trade logging
- `saas/database.py` - Added `log_ai_bot_trade()`

### November 5, 2025 - AI Bot Real Balance Architecture
**What Changed:**
- Removed virtual balance system (migration 016)
- Each AI bot requires unique Phemex API keys
- Real balance fetched directly from Phemex
- `initial_balance_snapshot` saved when bot created
- PnL = `current_phemex_balance - initial_balance_snapshot`

**Why:**
- Virtual balance drifted from reality
- No position persistence across restarts
- Couldn't calculate accurate PnL per model

---

## Key Technical Decisions

### 1. Architecture: 1 Bot = 1 Account = 1 Model
**For AI Bots:**
- Each bot has dedicated Phemex account
- No shared API keys between bots
- True isolation for comparing model performance
- Real balance tracking only (no virtual construct)

### 2. Migration System
- SQL-based (NOT ORM migrations)
- Sequential naming: `001_`, `002_`, etc.
- Auto-run on Render deployment
- **MUST be idempotent**: Use `IF NOT EXISTS`, `ON CONFLICT DO NOTHING`

**Example:**
```sql
ALTER TABLE bots ADD COLUMN IF NOT EXISTS description TEXT;
INSERT INTO settings (key, value) VALUES ('foo', 'bar') ON CONFLICT DO NOTHING;
```

### 3. API Key Encryption
All API keys encrypted with Fernet before database storage:
```python
from saas.security import encrypt_api_key, decrypt_api_key

# Storing
encrypted = encrypt_api_key(plaintext)
cursor.execute("INSERT INTO bots (api_key) VALUES (%s)", (encrypted,))

# Using
encrypted = row['api_key']
plaintext = decrypt_api_key(encrypted)
```

### 4. Volatility vs Decline Velocity (CRITICAL for Martingale)
**Both must be checked:**
- High volatility + CRASH/FAST_DECLINE → ❌ STOP (dangerous)
- High volatility + SLOW/MODERATE_DECLINE → ✅ CONTINUE (safe for averaging)

**Why:** Slow, steady declines are IDEAL for Martingale averaging.

---

## Database Schema (Key Tables)

### Martingale Bots
- `bots` - Bot configuration with encrypted Phemex keys
- `trading_pairs` - Symbol/side/leverage per bot
- `trades` - Trade history
- `bot_logs` - Execution logs
- `bot_metrics` - Performance snapshots

### AI Trading Bots
- `ai_model_configs` - Model specs (GLM, DeepSeek, Claude)
- `ai_bots` - Bot configs with unique Phemex credentials per bot
- `ai_decisions` - Decision history with reasoning
- `ai_bot_trades` - Trade execution log with PnL (NEW)
- `ai_model_performance` - Performance snapshots

---

## Important Conventions

### 1. Timezone Handling
- All DB timestamps are UTC
- Display in user's timezone using `timezone_utils.py`
- Template filters: `user_timezone`, `user_date`, `user_time`

### 2. Security Validation
- ALL user inputs through `validation.py`
- Parameterized queries (NEVER string concatenation)

```python
from saas.validation import is_safe_input

user_input = request.form.get('symbol')
if not is_safe_input(user_input):
    return "Invalid input", 400

cursor.execute("SELECT * FROM bots WHERE symbol = %s", (user_input,))
```

### 3. Error Propagation
- PhemexClient methods re-raise exceptions after logging
- Users get Telegram notifications for critical errors
- Never swallow exceptions silently

---

## Common Pitfalls to Avoid

### 1. ❌ DON'T Edit Applied Migrations
Once deployed, create new migration instead:
```sql
-- ❌ WRONG: Edit 005_add_column.sql
-- ✅ RIGHT: Create 006_remove_column.sql
ALTER TABLE bots DROP COLUMN IF EXISTS description;
```

### 2. ❌ DON'T Use Virtual Balance for AI Bots
System removed in migration 016. Always fetch real balance:
```python
# ❌ WRONG: virtual_balance = bot.get('virtual_balance')
# ✅ RIGHT:
balance, used_balance = phemex_client.get_account_balance()
```

### 3. ❌ DON'T Assume High Volatility = Stop
Check decline velocity too:
```python
# ❌ WRONG:
if is_high_volatility: return "STOP"

# ✅ RIGHT:
if is_high_volatility and decline_velocity in ["CRASH", "FAST_DECLINE"]:
    return "STOP"
```

### 4. ❌ DON'T Forget Testnet Flag
Always check when creating PhemexClient:
```python
phemex = PhemexClient(
    api_key=api_key,
    api_secret=api_secret,
    testnet=bot['testnet']  # IMPORTANT!
)
```

### 5. ❌ DON'T Mix Decimal/Float Types
Phemex returns Decimal; convert in calculations:
```python
balance = float(bot.get('balance', 0))
price = float(position.get('avgEntryPrice', 0))
```

---

## Key File Locations

### Strategy Decision Making
- `strategies/MartingaleTradingStrategy.py:46-172` - manage_position()
- `strategies/AITradingStrategy.py:84-297` - get_ai_decision()

### Volatility & Risk Management
- `indicators/volatility.py:171-266` - calculate_decline_velocity()
- `indicators/volatility.py:269-329` - is_high_volatility()

### Trade Execution
- `clients/PhemexClient.py:425-489` - place_order()
- `clients/PhemexClient.py:491-523` - close_position()
- `clients/PhemexClient.py:525-567` - get_trade_history()

### AI Bot System
- `saas/execute_ai_bots.py:252-407` - execute_decision()
- `saas/database.py:600-650` - log_ai_bot_trade()
- `data/market_data_fetcher.py:44-195` - fetch_market_data()

### Dashboard
- `saas/templates/ai_bots_dashboard.html:688-718` - getModelColor()
- `saas/templates/ai_bots_dashboard.html:720-774` - loadDecisionsLog()

---

## Deployment

### Render Blueprint (`render.yaml`)
```yaml
services:
  - type: web
    name: dcabot-saas-web
    plan: starter  # $7/month
    buildCommand: pip install -r requirements.txt -r requirements-saas.txt && python saas/migrate.py
    startCommand: gunicorn -w 4 -b 0.0.0.0:$PORT saas.app:app

  - type: cron
    name: dcabot-saas-scheduler
    schedule: "*/5 * * * *"
    startCommand: python saas/execute_all_bots.py

  - type: cron
    name: dcabot-ai-executor
    schedule: "*/5 * * * *"
    startCommand: python saas/execute_ai_bots.py
```

**Deployment Flow:**
1. Push to `feature/saas-transformation`
2. Render auto-detects changes
3. Runs migrations during build
4. Deploys all services from blueprint

---

## Testing Locally

### Run Web App
```bash
cd dcabot
./scripts/run_local_app.sh
# Visit: http://localhost:3030
```

### Run Executors
```bash
# AI bots only
./scripts/run_executor.sh

# All bots (Martingale + AI)
./scripts/run_all_bots.sh

# Continuous loop (simulates production)
./scripts/run_bot_loop.sh
```

### Run Migrations
```bash
./scripts/run_migrations.sh
```

---

## Repository Information

**Repository:** https://github.com/pehur00/dcabot

**Branches:**
- `main` - Standalone bot (deprecated)
- `feature/saas-transformation` - Production SaaS platform ⭐

**Documentation:**
- `README.md` - Project overview and quick start
- `docs/ARCHITECTURE.md` - System architecture
- `docs/ROADMAP.md` - Future plans
- `docs/RENDER_DEPLOYMENT.md` - Deployment guide
- `docs/LOCAL_SETUP.md` - Local dev setup
- `docs/DATABASE_MIGRATIONS.md` - Migration system
- `docs/STRATEGY.md` - Trading strategies
- `scripts/README.md` - Helper scripts

**Key Dependencies:**
- Flask 3.0.0, PostgreSQL 14+
- pandas 2.2.0, numpy 1.26.3
- pytz 2023.3, cryptography 41.0.7

---

## Development Credentials (Testnet)

**Phemex Testnet:**
- Available in user's local `.env` file
- Testnet flag: True

**Telegram Bot:**
- Configured per user in Settings

---

## Remember

1. **Two systems** - Martingale (production) + AI bots (production)
2. **This is Martingale, NOT DCA** - Averages down with exponential sizing
3. **Volatility protection is nuanced** - Allows slow declines
4. **Real balance for AI bots** - No virtual construct
5. **1 Bot = 1 Account = 1 Model** - True isolation
6. **Migrations must be idempotent** - Use `IF NOT EXISTS`
7. **All timestamps timezone-aware** - Use `timezone_utils.py`
8. **Security first** - Validate inputs, encrypt keys

---

**End of AI Context**
