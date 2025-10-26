# DCABot - Agent Memory Bank

Last Updated: 2025-10-26

## Project Overview

**DCABot** is a cryptocurrency trading bot that implements a **Martingale strategy** (not pure DCA) with intelligent risk management. It automatically manages positions on Phemex exchange with advanced volatility protection and decline velocity detection.

**Repository**: https://github.com/pehur00/dcabot
**Deployment**: Render.com (cron job, runs every 5 minutes)
**Exchange**: Phemex (testnet and mainnet support)

## Core Strategy: Martingale Trading

### Philosophy
- **Average down** on losing positions to lower entry price
- **Increase position size** as price moves against you
- **Profit from mean reversion** when price recovers
- **Risk management** is critical - can blow up account if not careful

### Key Parameters (strategies/MartingaleTradingStrategy.py)
```python
CONFIG = {
    'buy_until_limit': 0.02,           # Max 2% of balance in position
    'profit_threshold': 0.003,         # Min 0.3% profit to close
    'profit_pnl': 0.1,                 # 10% PnL target for full close
    'leverage': 6,                     # 6x leverage
    'begin_size_of_balance': 0.006,    # Start with 0.6% of balance
    'strategy_filter': 'EMA',          # EMA-based filtering
    'buy_below_percentage': 0.04,      # Buy when down 4%
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

### 1. Removed 1h EMA200 Requirement (Commit: c38a213)
**Why**: Strategy now uses configured `EMA_INTERVAL` for all EMAs instead of forcing 1h timeframe
**Impact**: More flexible and responsive to chosen interval
**Files**: MartingaleTradingStrategy.py, MartingaleTradingWorkflow.py

### 2. Enhanced Position Notifications (Commit: c38a213)
**Why**: Users needed complete position details for all actions
**What**: Unified notification system with action types (OPENED/ADDED/REDUCED/CLOSED)
**Details**: Shows position size, value, % of balance for all updates
**Files**: TelegramNotifier.py, MartingaleTradingStrategy.py

### 3. Decline Velocity Detection (Commit: 6079bcd)
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

### 4. Error Propagation Fix (Commit: 46ba5cd)
**Why**: Critical errors (invalid symbols, order failures) weren't triggering Telegram notifications
**What**: Re-raise exceptions after logging in PhemexClient methods
**Impact**: Users now get Telegram alerts for all critical failures
**Files**: PhemexClient.py (place_order, close_position, cancel_orders, set_leverage)

### 5. Improved Skip Logging (Commit: 5e81be1)
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

## Deployment

### Render.com Setup
**Type**: Cron job
**Schedule**: Every 5 minutes (`*/5 * * * *`)
**Service**: martingale-trading-bot
**Region**: Frankfurt
**Blueprint**: render.yaml

**How to Deploy**:
1. Push to GitHub main branch
2. Render auto-deploys from GitHub
3. Configure environment variables in Render dashboard

**Render CLI Access**:
```bash
render login
# Set workspace in ~/.render/cli.yaml
render services list
render logs -s martingale-trading-bot
```

### Docker Deployment
```bash
# Build
docker build -t dcabot .

# Run
docker run --env-file bot.env dcabot
```

### Local Development
```bash
# Setup
python3 -m venv dcabot-env
source dcabot-env/bin/activate
pip install -r requirements.txt

# Run
python main.py
```

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

5. **Backtesting Framework**
   - Historical data replay
   - Strategy optimization
   - Risk analysis

6. **Additional Exchanges**
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

**Main Branch**: main
**Remote**: origin (https://github.com/pehur00/dcabot)
**Recent Commits**:
- 5e81be1: Fix misleading skip log message
- 46ba5cd: Fix error propagation for Telegram notifications
- 6079bcd: Add decline velocity detection
- c38a213: Remove 1h EMA200 requirement and enhance notifications

**Workflow**:
1. Make changes locally
2. Test with `python main.py`
3. Commit with detailed message
4. Push to main
5. Render auto-deploys

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
