# AI Bot Architecture Redesign: Real Balance Tracking

**Date:** November 5, 2025
**Status:** Design Phase
**Goal:** Redesign AI bot system to use real Phemex account balances instead of virtual balance tracking

---

## 🎯 Core Principle

**1 AI Bot = 1 Phemex Account = 1 AI Model**

Each AI bot has its own isolated Phemex account (via unique API keys), ensuring:
- Real balance tracking (no virtual construct)
- Position persistence across bot restarts
- Complete trade history from Phemex
- Accurate PnL calculations
- True isolation between bots

---

## ❌ Problems with Current Virtual Balance System

### 1. **Artificial State Management**
- We maintain `virtual_balance` in our database
- Balance changes tracked in `ai_bot_balance_history` table
- Disconnected from actual Phemex account state
- Can drift out of sync with reality

### 2. **No Position Persistence**
- If bot crashes/restarts, position state lost
- Positions exist on Phemex but we don't have full context
- Can't resume gracefully after interruption

### 3. **Incomplete Trade History**
- We only log AI decisions, not actual trade executions
- Missing partial fills, order amendments, manual overrides
- Can't calculate accurate win/loss statistics
- No realized PnL tracking per trade

### 4. **Complex Multi-Bot Support**
- Current design allows multiple bots to share same API keys
- Creates conflicts when managing shared balance
- Difficult to attribute PnL to specific models
- Race conditions possible with concurrent trades

### 5. **Testing Limitations**
- No clean testnet support
- Can't isolate test environments
- Risk of mixing testnet/mainnet data

---

## ✅ Benefits of New Design

### 1. **Real Balance Tracking**
```
OLD: virtual_balance = 200.00 (in database)
     actual Phemex balance = 205.35 (drifted)

NEW: Query Phemex → accountBalanceRv = 205.35 (source of truth)
```

### 2. **Position Persistence**
```
OLD: Bot crashes → position state lost
     Bot restarts → doesn't know about open positions

NEW: Bot restarts → Query Phemex → see all open positions
     Resume trading with full context
```

### 3. **Complete Trade History**
```
OLD: Only log AI decisions (BUY/SELL/HOLD)
     Miss execution details, fees, partial fills

NEW: Query Phemex trade history API
     Get every trade with exact fees, PnL, timestamps
```

### 4. **True Isolation**
```
OLD: Bot A (GLM) }
     Bot B (DeepSeek) } → Same Phemex account (conflicts!)
     Bot C (Claude) }

NEW: Bot A (GLM) → Phemex Account #1 (isolated)
     Bot B (DeepSeek) → Phemex Account #2 (isolated)
     Bot C (Claude) → Phemex Account #3 (isolated)
```

### 5. **Testnet Support**
```
NEW: Each bot has `testnet` boolean flag
     Testnet bots → testnet-api.phemex.com
     Mainnet bots → api.phemex.com
```

---

## 🏗️ New Architecture

### Database Schema Changes

#### Remove Virtual Balance Tracking:
```sql
-- Migration 016: Redesign for real balance tracking

-- Remove virtual balance columns from ai_bots
ALTER TABLE ai_bots
DROP COLUMN IF EXISTS virtual_balance,
DROP COLUMN IF EXISTS initial_balance,
DROP COLUMN IF EXISTS total_realized_pnl,
DROP COLUMN IF EXISTS total_trades_executed;

-- Drop balance history table (use Phemex history instead)
DROP TABLE IF EXISTS ai_bot_balance_history;

-- Add new columns for real balance tracking
ALTER TABLE ai_bots
ADD COLUMN IF NOT EXISTS testnet BOOLEAN DEFAULT true,
ADD COLUMN IF NOT EXISTS initial_balance_snapshot DECIMAL(20, 8),
ADD COLUMN IF NOT EXISTS snapshot_taken_at TIMESTAMP;

-- Update ai_model_performance to remove virtual_balance
ALTER TABLE ai_model_performance
DROP COLUMN IF EXISTS virtual_balance;

COMMENT ON COLUMN ai_bots.initial_balance_snapshot IS 'Snapshot of Phemex balance when bot was created (for PnL calculation)';
COMMENT ON COLUMN ai_bots.snapshot_taken_at IS 'When initial balance snapshot was taken';
COMMENT ON COLUMN ai_bots.testnet IS 'Whether bot uses Phemex testnet (true) or mainnet (false)';
```

#### Keep These Tables:
- `ai_bots` - Bot configuration with unique Phemex credentials per bot
- `ai_model_configs` - AI model specifications (GLM, DeepSeek, Claude)
- `ai_decisions` - AI decision log (BUY/SELL/HOLD with reasoning)
- `ai_model_performance` - Performance snapshots (balance, PnL, trades)

### Bot Creation Flow

**OLD:**
```python
1. User fills form with initial_balance ($200)
2. Save to database: virtual_balance = initial_balance = 200.00
3. Start trading with virtual balance
```

**NEW:**
```python
1. User fills form with Phemex API keys (unique per bot)
2. Validate API keys by fetching balance from Phemex
3. Save initial_balance_snapshot = current Phemex balance
4. Start trading with real Phemex balance
```

**Code Changes:**
```python
# In saas/ai_bot_routes.py (create_ai_bot)

# OLD:
initial_balance = float(request.form.get('initial_balance', 200))

# NEW:
from clients.PhemexClient import PhemexClient
import logging

testnet = request.form.get('testnet') == 'on'
logger = logging.getLogger(__name__)

# Validate API keys by connecting to Phemex
phemex = PhemexClient(
    api_key=phemex_api_key,
    api_secret=phemex_api_secret,
    logger=logger,
    testnet=testnet
)

# Fetch real balance from Phemex
balance, used_balance = phemex.get_account_balance()
if balance is None:
    flash('Invalid Phemex API keys or connection failed', 'error')
    return redirect(url_for('create_ai_bot'))

initial_balance_snapshot = balance

# Save to database
cursor.execute("""
    INSERT INTO ai_bots (
        user_id, name, model_config_id,
        symbol, side, max_leverage, max_position_size,
        risk_profile, allowed_symbols,
        is_active, automatic_mode,
        exchange_api_key, exchange_api_secret, ai_api_key,
        testnet, initial_balance_snapshot, snapshot_taken_at
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
""", (..., testnet, initial_balance_snapshot))
```

### Execution Flow

**OLD:**
```python
1. Get virtual_balance from database
2. Calculate position size based on virtual_balance
3. Execute trade on Phemex
4. Deduct API cost from virtual_balance
5. Deduct trading fee from virtual_balance
6. Update virtual_balance in database
```

**NEW:**
```python
1. Fetch real balance from Phemex (get_account_balance)
2. Calculate position size based on real balance
3. Execute trade on Phemex
4. Fetch updated balance from Phemex (includes fees, PnL)
5. Update performance metrics with real data
```

**Code Changes:**
```python
# In saas/execute_ai_bots.py

# OLD:
virtual_balance = float(bot.get('virtual_balance', 100.00))
position_value_usd = virtual_balance * ai_position_size_pct

# NEW:
balance, used_balance = phemex_client.get_account_balance()
if balance is None:
    logger.error(f"Failed to fetch balance for bot {bot['id']}")
    return

available_balance = balance - used_balance
position_value_usd = available_balance * ai_position_size_pct
```

### Performance Metrics Calculation

**OLD:**
```python
# Calculate from virtual balance
initial_balance = float(bot.get('initial_balance', 100.00))
virtual_balance = float(bot.get('virtual_balance', 100.00))
pnl_amount = virtual_balance - initial_balance
pnl_percentage = (pnl_amount / initial_balance * 100)

# No trade statistics (not tracked properly)
total_trades = 0
winning_trades = 0
losing_trades = 0
```

**NEW:**
```python
# Get real balance from Phemex
balance, used_balance = phemex_client.get_account_balance()

# Calculate PnL from snapshot
initial_balance = float(bot['initial_balance_snapshot'])
pnl_amount = balance - initial_balance
pnl_percentage = (pnl_amount / initial_balance * 100) if initial_balance > 0 else 0

# Get trade statistics from Phemex trade history
trades = phemex_client.get_trade_history(limit=1000)  # TODO: Add this method
total_trades = len(trades)
winning_trades = sum(1 for t in trades if t['closedPnl'] > 0)
losing_trades = sum(1 for t in trades if t['closedPnl'] < 0)
win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
```

---

## 🔧 Implementation Steps

### Step 1: Add Trade History Method to PhemexClient

```python
# In clients/PhemexClient.py

def get_trade_history(self, symbol=None, start_time=None, end_time=None, limit=200):
    """
    Get trade history from Phemex

    Args:
        symbol: Filter by symbol (optional, None = all symbols)
        start_time: Start timestamp in seconds (optional)
        end_time: End timestamp in seconds (optional)
        limit: Max number of trades to return (default 200, max 200)

    Returns:
        List of trades with details (price, qty, fee, PnL, etc.)

    API Endpoint: GET /g-api-data/futures/orders/by-time-range
    or: GET /g-api-data/futures/trades

    Reference: https://phemex-docs.github.io/#query-user-trade
    """
    try:
        params = {
            'currency': 'USDT',
            'limit': min(limit, 200)  # Phemex max is 200
        }

        if symbol:
            params['symbol'] = symbol
        if start_time:
            params['start'] = int(start_time)
        if end_time:
            params['end'] = int(end_time)

        response = self._send_request("GET", "/g-api-data/futures/trades", params=params)
        trades = response['data']['rows']

        # Parse trades into usable format
        parsed_trades = []
        for trade in trades:
            parsed_trades.append({
                'orderId': trade.get('orderID'),
                'tradeId': trade.get('execID'),
                'symbol': trade.get('symbol'),
                'side': trade.get('side'),
                'price': float(trade.get('execPriceRp', 0)),
                'qty': float(trade.get('execQtyRq', 0)),
                'fee': float(trade.get('execFeeRv', 0)),
                'closedPnl': float(trade.get('closedPnlRv', 0)),
                'transactTime': trade.get('transactTimeNs'),
                'action': trade.get('action')  # 'New', 'PartialFill', 'Fill'
            })

        return parsed_trades

    except PhemexAPIException as e:
        self.logger.error(
            "Failed to get trade history",
            extra={
                "symbol": symbol,
                "error_details": str(e)
            }
        )
        return []
```

### Step 2: Create Migration 016

```sql
-- File: saas/migrations/016_redesign_real_balance.sql

-- Migration 016: Redesign AI bots for real balance tracking
-- Date: 2025-11-05
-- Description: Remove virtual balance, use Phemex account balance instead

-- Remove virtual balance tracking
ALTER TABLE ai_bots
DROP COLUMN IF EXISTS virtual_balance CASCADE,
DROP COLUMN IF EXISTS initial_balance CASCADE,
DROP COLUMN IF EXISTS total_realized_pnl CASCADE,
DROP COLUMN IF EXISTS total_trades_executed CASCADE;

-- Drop balance history table (Phemex is source of truth)
DROP TABLE IF EXISTS ai_bot_balance_history CASCADE;

-- Add new columns
ALTER TABLE ai_bots
ADD COLUMN IF NOT EXISTS testnet BOOLEAN DEFAULT true,
ADD COLUMN IF NOT EXISTS initial_balance_snapshot DECIMAL(20, 8),
ADD COLUMN IF NOT EXISTS snapshot_taken_at TIMESTAMP;

-- Update ai_model_performance
ALTER TABLE ai_model_performance
DROP COLUMN IF EXISTS virtual_balance CASCADE;

-- Add index for testnet filtering
CREATE INDEX IF NOT EXISTS idx_ai_bots_testnet ON ai_bots(testnet);

-- Add comments
COMMENT ON COLUMN ai_bots.testnet IS 'Whether bot uses Phemex testnet (true) or mainnet (false)';
COMMENT ON COLUMN ai_bots.initial_balance_snapshot IS 'Snapshot of Phemex account balance when bot was created (for PnL calculation)';
COMMENT ON COLUMN ai_bots.snapshot_taken_at IS 'Timestamp when initial balance snapshot was taken';

-- Migration tracking
INSERT INTO schema_migrations (version) VALUES ('016') ON CONFLICT DO NOTHING;
```

### Step 3: Update Bot Creation Form

```html
<!-- saas/templates/ai_bot_form.html -->

<!-- REMOVE: Virtual balance input -->
<!--
<div class="form-group">
    <label for="initial_balance">💰 Initial Virtual Balance (USD)</label>
    <input type="number" id="initial_balance" name="initial_balance" required
           value="200" min="50" max="10000" step="10">
</div>
-->

<!-- ADD: Testnet toggle -->
<div class="form-group">
    <label for="testnet">
        <input type="checkbox" id="testnet" name="testnet" checked>
        🧪 Use Testnet (recommended for testing)
    </label>
    <small style="color: var(--gray-500);">
        Testnet allows safe testing with fake money. Uncheck for live trading with real funds.
    </small>
</div>

<!-- UPDATE: API key help text -->
<div class="form-group">
    <label for="phemex_api_key">🔑 Phemex API Key</label>
    <input type="text" id="phemex_api_key" name="phemex_api_key" required>
    <small style="color: var(--gray-500);">
        <strong>Important:</strong> Each AI bot needs its own Phemex account (unique API keys).
        This ensures isolation and accurate performance tracking.
        <br>
        Create testnet API keys at: <a href="https://testnet.phemex.com" target="_blank">testnet.phemex.com</a>
        <br>
        Create mainnet API keys at: <a href="https://phemex.com" target="_blank">phemex.com</a>
    </small>
</div>
```

### Step 4: Update Bot Creation Route

```python
# In saas/ai_bot_routes.py

@app.route('/ai-bots/new', methods=['POST'])
@login_required
def create_ai_bot():
    try:
        # Get form data
        bot_name_base = request.form.get('name', '').strip()
        testnet = request.form.get('testnet') == 'on'  # NEW

        # Exchange credentials
        phemex_api_key = request.form.get('phemex_api_key', '').strip()
        phemex_api_secret = request.form.get('phemex_api_secret', '').strip()

        # Validate by connecting to Phemex
        from clients.PhemexClient import PhemexClient
        phemex = PhemexClient(
            api_key=phemex_api_key,
            api_secret=phemex_api_secret,
            logger=app.logger,
            testnet=testnet
        )

        # Fetch real balance to validate credentials
        balance, used_balance = phemex.get_account_balance()
        if balance is None:
            flash('Failed to connect to Phemex. Check API keys and permissions.', 'error')
            return redirect(url_for('create_ai_bot'))

        # Save initial balance snapshot
        initial_balance_snapshot = balance

        # Create bot (only ONE per unique API keys)
        cursor.execute("""
            INSERT INTO ai_bots (
                user_id, name, model_config_id,
                symbol, side, max_leverage, max_position_size,
                risk_profile, allowed_symbols,
                is_active, automatic_mode,
                exchange_api_key, exchange_api_secret, ai_api_key,
                testnet, initial_balance_snapshot, snapshot_taken_at
            ) VALUES (
                %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s,
                %s, %s,
                %s, %s, %s,
                %s, %s, NOW()
            )
            RETURNING id
        """, (
            current_user.id, bot_name, model_id,
            primary_symbol, side, max_leverage, max_position_size,
            risk_profile, allowed_symbols,
            True, automatic_mode,
            phemex_key_encrypted, phemex_secret_encrypted, ai_api_key_encrypted,
            testnet, initial_balance_snapshot
        ))

        flash(f'AI bot created! Initial balance: ${initial_balance_snapshot:.2f}', 'success')
        return redirect(url_for('ai_bots_dashboard'))

    except Exception as e:
        app.logger.error(f"Failed to create AI bot: {e}")
        flash(f'Error creating bot: {str(e)}', 'error')
        return redirect(url_for('create_ai_bot'))
```

### Step 5: Update Executor

```python
# In saas/execute_ai_bots.py

class AIBotExecutor:
    def execute_bot(self, bot):
        """Execute trading decisions for a single AI bot"""
        try:
            # Get Phemex client (with testnet flag)
            phemex_client = self.get_phemex_client(bot)

            # Fetch REAL balance from Phemex
            balance, used_balance = phemex_client.get_account_balance()
            if balance is None:
                logger.error(f"Failed to fetch balance for bot {bot['id']}")
                return

            available_balance = balance - used_balance
            logger.info(f"Bot {bot['id']}: Balance=${balance:.2f}, Used=${used_balance:.2f}, Available=${available_balance:.2f}")

            # Get AI decisions for each symbol
            decisions_data = []
            total_api_cost = 0

            for symbol in bot['allowed_symbols']:
                # Fetch market data
                market_data = self.market_fetcher.fetch_market_data(symbol)

                # Get AI decision
                decision = self.ai_strategy.get_ai_decision(
                    bot=bot,
                    market_data=market_data,
                    position_info=None,  # Will fetch from Phemex
                    current_balance=available_balance  # Use real balance
                )

                # Calculate API cost
                api_cost = self.ai_strategy.calculate_api_cost(...)
                total_api_cost += api_cost

                decisions_data.append((symbol, decision, api_cost))

            # Execute each decision
            for symbol, decision, api_cost in decisions_data:
                # Get current position from Phemex
                position = phemex_client.get_position_for_symbol(symbol, decision['side'])

                # Execute decision
                result = self.execute_decision(
                    bot=bot,
                    decision=decision,
                    phemex_client=phemex_client,
                    position=position,
                    available_balance=available_balance
                )

            # Update performance metrics with REAL data from Phemex
            self.update_performance_metrics(bot, phemex_client)

        except Exception as e:
            logger.error(f"Bot {bot['id']} execution failed: {e}", exc_info=True)
```

### Step 6: Update Performance Tracking

```python
# In saas/execute_ai_bots.py

def update_performance_metrics(self, bot, phemex_client):
    """Update performance metrics using real Phemex data"""
    try:
        # Get REAL balance from Phemex
        balance, used_balance = phemex_client.get_account_balance()
        if balance is None:
            logger.warning(f"Failed to fetch balance for metrics update")
            return

        # Calculate PnL from initial snapshot
        initial_balance = float(bot['initial_balance_snapshot'])
        pnl_amount = balance - initial_balance
        pnl_percentage = (pnl_amount / initial_balance * 100) if initial_balance > 0 else 0

        # Get trade history from Phemex
        trades = phemex_client.get_trade_history(limit=1000)

        # Calculate trade statistics
        total_trades = len(trades)
        winning_trades = sum(1 for t in trades if t['closedPnl'] > 0)
        losing_trades = sum(1 for t in trades if t['closedPnl'] < 0)
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

        # Get open positions
        open_positions = 0
        total_position_value = 0
        for symbol in bot['allowed_symbols']:
            for side in ['Long', 'Short']:
                position = phemex_client.get_position_for_symbol(symbol, side)
                if position and position['size'] > 0:
                    open_positions += 1
                    total_position_value += position['positionValue']

        # Get API cost from ai_decisions
        stats = db.get_ai_bot_stats(bot['id'])
        total_api_cost = float(stats['total_api_cost']) if stats else 0
        total_api_calls = int(stats['total_decisions']) if stats else 0

        # Save performance snapshot
        performance_data = {
            'ai_bot_id': bot['id'],
            'model_config_id': bot['model_config_id'],
            'balance': balance,  # Real balance from Phemex
            'pnl_percentage': pnl_percentage,
            'pnl_amount': pnl_amount,
            'total_trades': total_trades,  # From Phemex trade history
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'open_positions': open_positions,
            'total_position_value': total_position_value,
            'total_api_cost': total_api_cost,
            'total_api_calls': total_api_calls
        }

        db.save_ai_bot_performance(performance_data)
        logger.info(f"Performance updated: Balance=${balance:.2f}, PnL={pnl_percentage:+.2f}%, Trades={total_trades}, Win Rate={win_rate:.1f}%")

    except Exception as e:
        logger.warning(f"Failed to update performance metrics: {e}")
```

### Step 7: Update Dashboard

```python
# In saas/ai_bot_routes.py

@app.route('/ai-bots/dashboard')
@login_required
def ai_bots_dashboard():
    """AI Bots Dashboard - show real-time balance from Phemex"""
    try:
        # Get user's AI bots
        bots = db.get_user_ai_bots(current_user.id)

        # Fetch real-time balance for each bot
        for bot in bots:
            try:
                phemex = PhemexClient(
                    api_key=decrypt_api_key(bot['exchange_api_key']),
                    api_secret=decrypt_api_key(bot['exchange_api_secret']),
                    logger=app.logger,
                    testnet=bot['testnet']
                )

                balance, used_balance = phemex.get_account_balance()
                if balance is not None:
                    bot['current_balance'] = balance
                    bot['used_balance'] = used_balance
                    bot['available_balance'] = balance - used_balance

                    # Calculate PnL
                    initial = float(bot['initial_balance_snapshot'])
                    bot['pnl_amount'] = balance - initial
                    bot['pnl_percentage'] = (bot['pnl_amount'] / initial * 100) if initial > 0 else 0
                else:
                    bot['current_balance'] = None
                    bot['error'] = "Failed to fetch balance"

            except Exception as e:
                app.logger.error(f"Failed to fetch balance for bot {bot['id']}: {e}")
                bot['current_balance'] = None
                bot['error'] = str(e)

        return render_template('ai_bots_dashboard.html', bots=bots)

    except Exception as e:
        app.logger.error(f"Dashboard error: {e}")
        flash('Error loading dashboard', 'error')
        return redirect(url_for('dashboard'))
```

---

## 📊 Data Flow Comparison

### OLD: Virtual Balance System
```
User Creates Bot
    ↓
Set virtual_balance = $200 (in DB)
    ↓
Executor runs:
    Read virtual_balance from DB
    Calculate position size
    Execute trade on Phemex
    Deduct fees from virtual_balance
    Update virtual_balance in DB
    ↓
Dashboard:
    Show virtual_balance from DB
```

### NEW: Real Balance System
```
User Creates Bot
    ↓
Connect to Phemex with API keys
Fetch real balance = $205.35
Save initial_balance_snapshot = $205.35
    ↓
Executor runs:
    Fetch real balance from Phemex
    Calculate position size
    Execute trade on Phemex
    Phemex updates balance (fees auto-deducted)
    ↓
Dashboard:
    Fetch real-time balance from Phemex
    Calculate PnL = current - snapshot
```

---

## 🚀 Deployment Strategy

### Phase 1: Preparation
1. ✅ Document new architecture (this file)
2. ⏳ Add `get_trade_history()` to PhemexClient
3. ⏳ Create migration 016
4. ⏳ Test migration on local dev database

### Phase 2: Code Updates
5. ⏳ Update bot creation form (remove virtual balance input, add testnet toggle)
6. ⏳ Update bot creation route (fetch real balance, save snapshot)
7. ⏳ Update executor (use Phemex balance, remove virtual balance updates)
8. ⏳ Update performance tracking (use Phemex trade history)
9. ⏳ Update dashboard (fetch real-time balance)

### Phase 3: Testing
10. ⏳ Test bot creation with testnet API keys
11. ⏳ Test executor with real Phemex data
12. ⏳ Test performance metrics calculations
13. ⏳ Test dashboard display

### Phase 4: Deployment
14. ⏳ Deploy to staging environment
15. ⏳ Run migration 016
16. ⏳ Test end-to-end on staging
17. ⏳ Deploy to production
18. ⏳ Monitor for issues

### Phase 5: User Migration
19. ⏳ Notify users of new architecture
20. ⏳ Require users to recreate bots with unique API keys
21. ⏳ Deprecate old virtual balance system

---

## 📝 User Communication

### User Guide Update

**OLD MESSAGE:**
"Set your initial virtual balance ($50-$10,000). The bot will track your virtual balance as it trades."

**NEW MESSAGE:**
"Each AI bot needs its own Phemex account (unique API keys). This ensures:
- Real balance tracking (no virtual construct)
- Position persistence across bot restarts
- Accurate PnL and trade history
- True isolation between different AI models

**Testnet (Recommended for Testing):**
- Create free testnet account at: https://testnet.phemex.com
- Get $10,000 fake USDT to test with
- Zero risk, perfect for learning

**Mainnet (Live Trading):**
- Use your real Phemex account
- Real money, real profits/losses
- Only after testing on testnet"

---

## 🎯 Success Criteria

- ✅ All virtual balance code removed
- ✅ Bots fetch real balance from Phemex
- ✅ PnL calculated from initial snapshot
- ✅ Trade history from Phemex API
- ✅ Win/loss statistics accurate
- ✅ Testnet support working
- ✅ Dashboard shows real-time data
- ✅ No state sync issues

---

## 🔮 Future Enhancements

1. **Historical Balance Chart**: Query Phemex balance history API for charting
2. **Trade Analysis**: Detailed per-trade breakdown with entry/exit prices
3. **Multi-Symbol Performance**: Track PnL per symbol separately
4. **Phemex Webhook Integration**: Real-time trade updates via webhooks
5. **Position Management UI**: View/close positions from dashboard
6. **Risk Alerts**: Monitor margin level, send alerts if approaching liquidation

---

**End of Redesign Document**
