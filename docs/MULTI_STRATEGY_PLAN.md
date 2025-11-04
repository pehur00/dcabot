# Multi-Strategy Trading Bot Implementation Plan

**Date:** November 4, 2025
**Status:** Planning Phase
**Goal:** Add multiple algorithmic trading strategies with varying risk profiles

---

## 📊 Current State

### Existing Strategy
- **Type:** Martingale (Average Down)
- **Risk Level:** 🔴 HIGH
- **File:** `strategies/MartingaleTradingStrategy.py`
- **Characteristics:**
  - Averages down on losing positions
  - Exponential position size increases
  - Works in ranging markets, struggles in trends
  - Can lead to significant drawdowns (saw 20% in 3-day SOLUSDT backtest)

### Architecture
✅ **Already supports multiple strategies:**
- Abstract base class: `TradingStrategy.py`
- Polymorphic design ready
- JSONB `config` column for strategy-specific parameters

---

## 🎯 Proposed Trading Strategies

### 1. **Grid Trading Strategy** 🟢 LOW-MEDIUM RISK
**Best for:** Sideways/ranging markets

**How it works:**
- Places buy and sell orders at predefined price levels (grid)
- Profits from small price oscillations
- No position size increase (fixed lot sizes)
- Takes profit at each grid level

**Configuration:**
```python
{
    "grid_levels": 10,           # Number of grid levels
    "grid_spacing": 0.01,        # 1% between each level
    "order_size": 0.005,         # 0.5% of balance per order
    "max_position": 0.05,        # Max 5% of balance in position
    "take_profit_per_level": 0.005  # 0.5% profit per grid
}
```

**Risk Profile:**
- ✅ Fixed position sizes (no exponential growth)
- ✅ Defined maximum exposure
- ✅ Works well in choppy markets
- ⚠️ Can underperform in strong trends
- ⚠️ Requires wider ranges to be effective

**Expected Performance:**
- Win Rate: 70-80% (many small wins)
- Average Win: +0.5-1%
- Max Drawdown: 3-7%
- Best Markets: BTC, ETH (high liquidity, range-bound)

---

### 2. **DCA (True Dollar-Cost Averaging)** 🟢 LOW RISK
**Best for:** Long-term accumulation, bullish bias

**How it works:**
- Fixed investment amount at regular intervals
- NO averaging down on losses
- Time-based entries (not price-based)
- Long-term hold strategy

**Configuration:**
```python
{
    "entry_interval_hours": 24,  # Buy every 24 hours
    "order_size": 0.01,          # 1% of balance per buy
    "take_profit_pct": 0.10,     # 10% profit target
    "stop_loss_pct": 0.15,       # 15% stop loss (optional)
    "max_positions": 10          # Max 10 open positions
}
```

**Risk Profile:**
- ✅ Very low risk (fixed amounts)
- ✅ Predictable cost basis
- ✅ No leverage required
- ✅ Emotion-free investing
- ⚠️ Slow returns (long-term strategy)
- ⚠️ Requires patience

**Expected Performance:**
- Win Rate: 60-70%
- Average Win: +5-15%
- Max Drawdown: 5-10%
- Best Markets: BTC, ETH (long-term growth)

---

### 3. **Momentum/Trend Following** 🟡 MEDIUM RISK
**Best for:** Trending markets (bull or bear)

**How it works:**
- Enters positions when trend is confirmed
- Uses EMA crossovers and momentum indicators
- Rides the trend with trailing stop-loss
- Exits when trend reverses

**Configuration:**
```python
{
    "fast_ema": 20,              # Fast EMA period
    "slow_ema": 50,              # Slow EMA period
    "rsi_period": 14,            # RSI period
    "rsi_oversold": 30,          # RSI oversold level
    "rsi_overbought": 70,        # RSI overbought level
    "order_size": 0.02,          # 2% of balance per trade
    "trailing_stop_pct": 0.05,   # 5% trailing stop
    "take_profit_pct": 0.15      # 15% take profit
}
```

**Risk Profile:**
- ✅ Follows market direction
- ✅ Limited risk per trade
- ✅ Good risk/reward ratio
- ⚠️ Whipsaws in choppy markets
- ⚠️ Late entries/exits (lagging indicators)

**Expected Performance:**
- Win Rate: 40-50% (but bigger wins)
- Average Win: +10-20%
- Average Loss: -5%
- Max Drawdown: 10-15%
- Best Markets: Altcoins, trending markets

---

### 4. **Mean Reversion** 🟡 MEDIUM RISK
**Best for:** Overbought/oversold conditions

**How it works:**
- Identifies extreme price movements
- Enters when price deviates significantly from mean
- Expects price to revert to average
- Uses Bollinger Bands, RSI, Z-score

**Configuration:**
```python
{
    "bb_period": 20,             # Bollinger Band period
    "bb_std_dev": 2,             # Standard deviations
    "rsi_period": 14,            # RSI period
    "rsi_threshold": 25,         # Enter when RSI < 25
    "order_size": 0.015,         # 1.5% of balance
    "take_profit_pct": 0.03,     # 3% take profit
    "stop_loss_pct": 0.05        # 5% stop loss
}
```

**Risk Profile:**
- ✅ Defined entry/exit rules
- ✅ Works well after sharp moves
- ⚠️ Can catch falling knives
- ⚠️ Doesn't work in strong trends

**Expected Performance:**
- Win Rate: 60-70%
- Average Win: +3-5%
- Max Drawdown: 8-12%
- Best Markets: High volatility altcoins

---

### 5. **Scalping Strategy** 🔴 HIGH RISK (but controlled)
**Best for:** Very active trading, small profits

**How it works:**
- Many small trades throughout the day
- Tiny profit targets (0.1-0.5%)
- Very tight stop-losses
- High win rate but requires constant monitoring

**Configuration:**
```python
{
    "timeframe": 1,              # 1-minute candles
    "order_size": 0.01,          # 1% of balance
    "take_profit_pct": 0.003,    # 0.3% profit
    "stop_loss_pct": 0.002,      # 0.2% stop loss
    "max_trades_per_day": 20,    # Limit overtrading
    "spread_threshold": 0.0005   # Max 0.05% spread
}
```

**Risk Profile:**
- ✅ Very tight risk control
- ✅ High win rate (80%+)
- ⚠️ High trading fees
- ⚠️ Requires low latency
- ⚠️ Emotionally draining

**Expected Performance:**
- Win Rate: 75-85%
- Average Win: +0.3-0.5%
- Max Drawdown: 3-5%
- Best Markets: BTC, ETH (high liquidity)

---

## 🏗️ Architecture Design

### Strategy Inheritance Structure

```
TradingStrategy (Abstract Base Class)
├── MartingaleTradingStrategy (Current - HIGH RISK)
├── GridTradingStrategy (NEW - LOW-MEDIUM RISK)
├── DCAStrategy (NEW - LOW RISK)
├── MomentumStrategy (NEW - MEDIUM RISK)
├── MeanReversionStrategy (NEW - MEDIUM RISK)
└── ScalpingStrategy (NEW - HIGH RISK)
```

### Database Schema Changes

#### Option 1: Add `strategy_type` column (RECOMMENDED)
```sql
-- Migration: Add strategy_type to trading_pairs
ALTER TABLE trading_pairs
ADD COLUMN strategy_type VARCHAR(50) DEFAULT 'martingale';

-- Valid values: 'martingale', 'grid', 'dca', 'momentum', 'mean_reversion', 'scalping'
```

#### Option 2: Use existing `config` JSONB column
```json
{
  "strategy_type": "grid",
  "parameters": {
    "grid_levels": 10,
    "grid_spacing": 0.01,
    ...
  }
}
```

**Recommendation:** Use **Option 1** (dedicated column) for easier querying and indexing.

---

## 🎨 UI/UX Design

### Bot Creation Flow

**Step 1: Choose Strategy Type**
```
┌─────────────────────────────────────────────────┐
│ Select Trading Strategy                         │
├─────────────────────────────────────────────────┤
│                                                 │
│  🟢 Grid Trading (Low-Medium Risk)             │
│     ✓ Best for ranging markets                 │
│     ✓ Fixed position sizes                     │
│     ✓ Many small profits                       │
│     [Select]                                    │
│                                                 │
│  🟢 DCA - True Dollar Cost Averaging (Low Risk)│
│     ✓ Time-based entries                       │
│     ✓ Long-term accumulation                   │
│     ✓ Very safe                                │
│     [Select]                                    │
│                                                 │
│  🟡 Momentum Trading (Medium Risk)             │
│     ✓ Trend following                          │
│     ✓ Good for trending markets                │
│     [Select]                                    │
│                                                 │
│  🔴 Martingale (HIGH RISK)                     │
│     ⚠️  Averages down on losses                │
│     ⚠️  Can lead to large drawdowns            │
│     [Select]                                    │
│                                                 │
└─────────────────────────────────────────────────┘
```

**Step 2: Configure Strategy Parameters**
- Dynamic form based on selected strategy
- Pre-filled with recommended defaults
- Tooltips explaining each parameter
- Risk calculator showing potential outcomes

**Step 3: Backtest Results (Optional)**
- Show recent backtest results for this strategy
- Compare with other strategies
- Risk metrics visualization

### Dashboard Updates

**Strategy Performance Comparison**
```
┌─────────────────────────────────────────────────┐
│ Your Bots by Strategy                           │
├─────────────────────────────────────────────────┤
│                                                 │
│  Grid Trading (2 bots)                         │
│    Avg Return: +3.2%  •  Win Rate: 78%        │
│    [View Bots]                                  │
│                                                 │
│  DCA (1 bot)                                   │
│    Avg Return: +8.5%  •  Win Rate: 65%        │
│    [View Bots]                                  │
│                                                 │
│  Martingale (1 bot)                            │
│    Avg Return: -12.3%  •  Win Rate: 66%       │
│    ⚠️  High drawdown detected                  │
│    [View Bots]                                  │
│                                                 │
└─────────────────────────────────────────────────┘
```

---

## 📋 Implementation Roadmap

### Phase 1: Foundation (Week 1-2)
**Goal:** Set up multi-strategy architecture

- [ ] Add `strategy_type` column to `trading_pairs` table
- [ ] Create migration script
- [ ] Add strategy selection to bot creation form
- [ ] Update `execute_all_bots.py` to instantiate correct strategy
- [ ] Add strategy info to bot detail page

**Deliverables:**
- Migration: `013_add_strategy_type.sql`
- Updated forms: `trading_pair_form.html`
- Strategy factory pattern in `execute_all_bots.py`

---

### Phase 2: Grid Trading Strategy (Week 3-4)
**Goal:** Implement first low-risk alternative

- [ ] Create `GridTradingStrategy.py`
- [ ] Implement grid placement logic
- [ ] Add grid visualization to UI
- [ ] Create backtesting suite for grid strategy
- [ ] Add strategy-specific metrics (grid fills, levels)

**Deliverables:**
- `strategies/GridTradingStrategy.py`
- Grid backtest results
- UI for grid visualization

---

### Phase 3: DCA Strategy (Week 5-6)
**Goal:** Implement safest strategy option

- [ ] Create `DCAStrategy.py`
- [ ] Implement time-based entry logic
- [ ] Add scheduler for periodic buys
- [ ] Create DCA-specific dashboard widgets
- [ ] Backtest DCA on 30+ day periods

**Deliverables:**
- `strategies/DCAStrategy.py`
- Time-based execution logic
- DCA performance metrics

---

### Phase 4: Momentum Strategy (Week 7-8)
**Goal:** Add trend-following capability

- [ ] Create `MomentumStrategy.py`
- [ ] Implement EMA crossover detection
- [ ] Add RSI and momentum indicators
- [ ] Trailing stop-loss implementation
- [ ] Backtesting on trending markets

**Deliverables:**
- `strategies/MomentumStrategy.py`
- Indicator calculations
- Trend detection logic

---

### Phase 5: Testing & Optimization (Week 9-10)
**Goal:** Validate all strategies

- [ ] Comprehensive backtesting (all strategies, multiple coins)
- [ ] A/B testing framework
- [ ] Strategy recommendation engine
- [ ] Performance comparison dashboard
- [ ] Risk profiling and warnings

**Deliverables:**
- Backtest report comparing all strategies
- Strategy selector wizard
- Risk assessment tool

---

### Phase 6: Advanced Features (Week 11-12)
**Goal:** Polish and enhance

- [ ] Strategy auto-switching based on market conditions
- [ ] Portfolio allocation across strategies
- [ ] Advanced risk management (global stop-loss, portfolio limits)
- [ ] Strategy marketplace (share/clone strategies)
- [ ] Machine learning for parameter optimization

**Deliverables:**
- Market regime detection
- Portfolio manager
- Strategy templates library

---

## 🗃️ Database Schema (Final)

### trading_pairs table (updated)
```sql
CREATE TABLE trading_pairs (
    id SERIAL PRIMARY KEY,
    bot_id INTEGER REFERENCES bots(id) ON DELETE CASCADE,
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,
    strategy_type VARCHAR(50) DEFAULT 'martingale', -- NEW
    leverage INTEGER DEFAULT 10,
    ema_interval INTEGER DEFAULT 1,
    automatic_mode BOOLEAN DEFAULT TRUE,
    config JSONB,  -- Strategy-specific parameters
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_trading_pairs_strategy_type ON trading_pairs(strategy_type);
```

### strategy_performance table (new)
```sql
CREATE TABLE strategy_performance (
    id SERIAL PRIMARY KEY,
    strategy_type VARCHAR(50) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    total_trades INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    avg_return_pct DECIMAL(10,4),
    max_drawdown_pct DECIMAL(10,4),
    sharpe_ratio DECIMAL(10,4),
    last_updated TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_strategy_performance_type ON strategy_performance(strategy_type, symbol);
```

---

## 💡 Strategy Recommendation Logic

### For User's Risk Profile:

**Conservative (Low Risk):**
1. ✅ DCA Strategy (primary)
2. ✅ Grid Trading (secondary)
3. ❌ Avoid: Martingale, Scalping

**Moderate (Medium Risk):**
1. ✅ Grid Trading (primary)
2. ✅ Momentum Strategy (secondary)
3. ✅ Mean Reversion (tertiary)
4. ⚠️ Limited Martingale (small positions only)

**Aggressive (High Risk):**
1. ✅ Momentum Strategy
2. ✅ Scalping (for active traders)
3. ✅ Martingale (with strict caps)

### By Market Condition:

**Ranging/Sideways:**
- 🎯 Grid Trading (best)
- 🎯 Mean Reversion (good)
- ❌ Momentum (avoid)

**Trending (Bull/Bear):**
- 🎯 Momentum (best)
- 🎯 DCA (bull only)
- ❌ Grid Trading (avoid)

**High Volatility:**
- 🎯 Mean Reversion (best)
- 🎯 Scalping (for experts)
- ❌ DCA (wait for stability)

**Low Volatility:**
- 🎯 DCA (best)
- 🎯 Grid Trading (good)
- ❌ Scalping (insufficient moves)

---

## 🔐 Risk Management Enhancements

### Global Portfolio Limits
```python
USER_RISK_LIMITS = {
    "max_total_exposure_pct": 0.50,  # Max 50% of balance across all bots
    "max_leverage_global": 10,        # Max leverage across all positions
    "max_drawdown_portfolio": 0.20,   # Stop all bots if -20% drawdown
    "max_margin_global": 0.40         # Max 40% margin used globally
}
```

### Per-Strategy Risk Limits
```python
STRATEGY_RISK_LIMITS = {
    "martingale": {
        "max_position_pct": 0.05,     # Max 5% per position
        "max_leverage": 10,
        "max_adds": 20                # Max 20 position adds
    },
    "grid": {
        "max_position_pct": 0.10,     # Max 10% total
        "max_leverage": 5,
        "max_grid_levels": 20
    },
    "dca": {
        "max_position_pct": 0.20,     # Max 20% total
        "max_leverage": 1,            # No leverage
        "max_positions": 10
    }
}
```

---

## 📊 Success Metrics

### Key Performance Indicators (KPIs)

**Per Strategy:**
- Total Return %
- Win Rate %
- Sharpe Ratio
- Max Drawdown %
- Average Trade Duration
- Profit Factor (Gross Profit / Gross Loss)

**Platform-wide:**
- User satisfaction by strategy type
- Strategy adoption rates
- Average return by risk profile
- Liquidation rate by strategy

---

## 🎓 User Education

### Strategy Guides
- In-app tutorials for each strategy
- Video explanations
- Recommended coins per strategy
- When to use each strategy

### Risk Warnings
```
⚠️  WARNING: Martingale Strategy

This strategy averages down on losing positions and can lead to
significant drawdowns in trending markets.

Recent Performance: -20% in SOLUSDT (3 days)

Consider safer alternatives:
• Grid Trading (recommended for ranging markets)
• DCA Strategy (recommended for long-term)

[Continue Anyway] [Choose Safer Strategy]
```

---

## 🚀 Quick Wins (Immediate Implementation)

### Priority Order:

1. **Grid Trading** (Week 1-4)
   - Lowest risk alternative
   - Easy to understand
   - Quick to implement
   - High user demand

2. **DCA Strategy** (Week 5-6)
   - Safest option
   - Appeals to long-term investors
   - Simple logic

3. **Momentum** (Week 7-8)
   - Medium risk
   - Good for trending markets
   - Broader market appeal

---

## 📝 Next Steps

1. **Review & Approve Plan** - Get stakeholder buy-in
2. **Create Detailed Specs** - For each strategy implementation
3. **Set Up Development Environment** - Create feature branch
4. **Begin Phase 1** - Database migration and architecture
5. **Implement Grid Trading** - First alternative strategy
6. **User Testing** - Beta test with select users
7. **Rollout** - Gradual release to all users

---

## 🤔 Open Questions

1. Should we allow users to combine strategies? (Portfolio mode)
2. Do we need strategy-specific backtesting UI?
3. Should strategies be user-customizable (advanced mode)?
4. Do we implement paper trading mode first?
5. Should we charge premium for advanced strategies?
6. How do we handle strategy migrations for existing users?

---

**End of Multi-Strategy Plan**

Next: Get feedback and prioritize Phase 1 implementation.
