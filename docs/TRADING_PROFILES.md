# Trading Profiles Design

## Overview
Different trading styles require different execution frequencies and parameters. This document defines the trading profile system for AI bots.

---

## Profile Definitions

### 1. SCALPER
**Goal:** Capture small price movements with high frequency

**Execution Frequency:** Every 5 minutes (288 calls/day)
- Needs rapid response to market changes
- High API cost but high opportunity count

**Parameters:**
```python
{
    'execution_interval_minutes': 5,
    'trade_cooldown_minutes': 5,      # Can trade again quickly
    'position_size_default': 0.02,    # 2% per trade (smaller)
    'max_leverage': 5,                # Lower leverage for safety
    'confidence_threshold': 75,       # Higher confidence needed
    'price_change_filter': 0.003,     # 0.3% price movement to analyze
    'hold_cooldown_minutes': 10,      # Re-analyze after HOLD decision
    'stop_loss_tight': True,          # Tight stop losses
    'expected_holding_hours': 0.5     # 30 minutes avg
}
```

**Estimated Monthly Cost:**
- 288 calls/day × 30 days = 8,640 calls
- Avg 4,000 tokens/call = 34.56M tokens/month
- At $2/1M tokens (DeepSeek) = **$69/month**
- At $0.50/1M tokens (budget models) = **$17/month**

**Best For:**
- Active traders monitoring positions
- High volatility markets
- Models with low token costs

---

### 2. SWING
**Goal:** Capture medium-term trends (days to weeks)

**Execution Frequency:** Every 30 minutes (48 calls/day)
- Balance between responsiveness and cost
- **RECOMMENDED DEFAULT**

**Parameters:**
```python
{
    'execution_interval_minutes': 30,
    'trade_cooldown_minutes': 60,     # Wait 1 hour after trade
    'position_size_default': 0.05,    # 5% per trade
    'max_leverage': 10,               # Standard leverage
    'confidence_threshold': 70,       # Standard threshold
    'price_change_filter': 0.01,      # 1% price movement to analyze
    'hold_cooldown_minutes': 30,      # Re-analyze after HOLD
    'stop_loss_tight': False,         # Wider stops for swings
    'expected_holding_hours': 48      # 2 days avg
}
```

**Estimated Monthly Cost:**
- 48 calls/day × 30 days = 1,440 calls
- Avg 4,000 tokens/call = 5.76M tokens/month
- At $2/1M tokens (DeepSeek) = **$11.52/month**
- At $0.50/1M tokens (budget models) = **$2.88/month**

**Best For:**
- Most users
- Balanced approach
- Good cost/benefit ratio

---

### 3. DCA_LONG (Dollar Cost Averaging - Long Term)
**Goal:** Accumulate positions over time, buy dips

**Execution Frequency:** Every 6 hours (4 calls/day)
- Long-term perspective
- Extremely low cost

**Parameters:**
```python
{
    'execution_interval_minutes': 360,  # 6 hours
    'trade_cooldown_minutes': 360,      # Wait 6 hours after trade
    'position_size_default': 0.10,      # 10% per trade (larger)
    'max_leverage': 3,                  # Conservative leverage
    'confidence_threshold': 65,         # Lower threshold (more trades)
    'price_change_filter': 0.02,        # 2% price movement to analyze
    'hold_cooldown_minutes': 180,       # 3 hours after HOLD
    'prefer_dips': True,                # Only buy on dips
    'stop_loss_tight': False,           # Wide stops (patient)
    'expected_holding_hours': 720       # 30 days avg
}
```

**Estimated Monthly Cost:**
- 4 calls/day × 30 days = 120 calls
- Avg 4,000 tokens/call = 0.48M tokens/month
- At $2/1M tokens (DeepSeek) = **$0.96/month**
- At $15/1M tokens (Claude) = **$7.20/month**

**Best For:**
- Set-and-forget investors
- Believers in long-term trends
- Budget-conscious users
- Can afford expensive models (Claude)

---

### 4. SPOT_HODL (Spot Market Buy & Hold)
**Goal:** Accumulate spot positions (no leverage), rebalance periodically

**Execution Frequency:** Daily at 9 AM UTC (1 call/day)
- Very long-term
- Minimal trading
- No leverage = safer

**Parameters:**
```python
{
    'execution_interval_minutes': 1440,  # 24 hours
    'trade_cooldown_minutes': 1440,      # Once per day max
    'position_size_default': 0.15,       # 15% per trade
    'max_leverage': 1,                   # NO LEVERAGE (spot only)
    'confidence_threshold': 60,          # Lower threshold
    'price_change_filter': 0.05,         # 5% price movement
    'hold_cooldown_minutes': 720,        # 12 hours after HOLD
    'spot_only': True,                   # No futures/margin
    'accumulation_mode': True,           # Prefer buying over selling
    'stop_loss_tight': False,
    'expected_holding_hours': 2160       # 90 days avg
}
```

**Estimated Monthly Cost:**
- 1 call/day × 30 days = 30 calls
- Avg 4,000 tokens/call = 0.12M tokens/month
- At $15/1M tokens (Claude) = **$1.80/month**
- At $50/1M tokens (GPT-4o) = **$6/month**

**Best For:**
- Conservative investors
- Anti-leverage mindset
- Long-term believers
- Can use premium models guilt-free

---

### 5. REBALANCER (Portfolio Rebalancing)
**Goal:** Maintain target allocations across portfolio

**Execution Frequency:** Weekly on Sundays at 00:00 UTC
- Rebalances entire portfolio
- Extremely low cost

**Parameters:**
```python
{
    'execution_interval_minutes': 10080,  # 7 days
    'trade_cooldown_minutes': 10080,      # Weekly only
    'position_size_default': 0.20,        # 20% (portfolio-wide)
    'max_leverage': 1,                    # Spot only
    'confidence_threshold': 50,           # Always rebalance if needed
    'price_change_filter': None,          # Ignore price changes
    'target_allocations': {               # User-defined targets
        'BTC': 0.40,   # 40% BTC
        'ETH': 0.30,   # 30% ETH
        'SOL': 0.15,   # 15% SOL
        'BNB': 0.15    # 15% BNB
    },
    'rebalance_threshold': 0.05,          # Rebalance if >5% drift
    'spot_only': True,
    'expected_holding_hours': 4320        # Continuous
}
```

**Estimated Monthly Cost:**
- 4 calls/month (weekly)
- Avg 6,000 tokens/call (portfolio decision) = 0.024M tokens/month
- At $15/1M tokens (Claude) = **$0.36/month**
- At $50/1M tokens (GPT-4o) = **$1.20/month**

**Best For:**
- Diversification seekers
- Index-style investing
- Ultra-low maintenance
- Premium models at negligible cost

---

## Implementation Plan

### Database Schema

**Migration 020: Add trading profiles**

```sql
-- Add profile column to ai_bots table
ALTER TABLE ai_bots ADD COLUMN IF NOT EXISTS trading_profile VARCHAR(20) DEFAULT 'SWING';

-- Add last execution tracking for cooldowns
ALTER TABLE ai_bots ADD COLUMN IF NOT EXISTS last_execution_at TIMESTAMP;
ALTER TABLE ai_bots ADD COLUMN IF NOT EXISTS last_trade_at TIMESTAMP;
ALTER TABLE ai_bots ADD COLUMN IF NOT EXISTS last_hold_decision_at TIMESTAMP;

-- Add profile-specific settings (JSONB for flexibility)
ALTER TABLE ai_bots ADD COLUMN IF NOT EXISTS profile_settings JSONB DEFAULT '{}';

-- Create index for execution scheduling
CREATE INDEX IF NOT EXISTS idx_ai_bots_profile ON ai_bots(trading_profile, is_active);
CREATE INDEX IF NOT EXISTS idx_ai_bots_last_exec ON ai_bots(last_execution_at) WHERE is_active = true;

-- Comments
COMMENT ON COLUMN ai_bots.trading_profile IS 'Trading profile: SCALPER, SWING, DCA_LONG, SPOT_HODL, REBALANCER';
COMMENT ON COLUMN ai_bots.last_execution_at IS 'Last time bot was analyzed (regardless of decision)';
COMMENT ON COLUMN ai_bots.last_trade_at IS 'Last time bot executed a trade';
COMMENT ON COLUMN ai_bots.last_hold_decision_at IS 'Last time bot decided to HOLD';
```

### Profile Configuration File

**New file: `saas/trading_profiles.py`**

```python
"""
Trading profile configurations for AI bots
Defines execution frequency, risk parameters, and trading style
"""

TRADING_PROFILES = {
    'SCALPER': {
        'name': 'Scalper',
        'description': 'High-frequency trading for quick profits (5-min intervals)',
        'emoji': '⚡',
        'execution_interval_minutes': 5,
        'trade_cooldown_minutes': 5,
        'position_size_default': 0.02,
        'max_leverage': 5,
        'confidence_threshold': 75,
        'price_change_filter': 0.003,
        'hold_cooldown_minutes': 10,
        'expected_holding_hours': 0.5,
        'estimated_monthly_cost_range': '$17-69',  # Depends on model
        'recommended_for': 'Active traders, high volatility markets'
    },
    'SWING': {
        'name': 'Swing Trader',
        'description': 'Medium-term trend following (30-min intervals)',
        'emoji': '📈',
        'execution_interval_minutes': 30,
        'trade_cooldown_minutes': 60,
        'position_size_default': 0.05,
        'max_leverage': 10,
        'confidence_threshold': 70,
        'price_change_filter': 0.01,
        'hold_cooldown_minutes': 30,
        'expected_holding_hours': 48,
        'estimated_monthly_cost_range': '$3-12',
        'recommended_for': 'Most users - balanced approach (RECOMMENDED)',
        'is_default': True
    },
    'DCA_LONG': {
        'name': 'DCA Long-Term',
        'description': 'Accumulate positions over time (6-hour intervals)',
        'emoji': '🎯',
        'execution_interval_minutes': 360,
        'trade_cooldown_minutes': 360,
        'position_size_default': 0.10,
        'max_leverage': 3,
        'confidence_threshold': 65,
        'price_change_filter': 0.02,
        'hold_cooldown_minutes': 180,
        'prefer_dips': True,
        'expected_holding_hours': 720,
        'estimated_monthly_cost_range': '$1-7',
        'recommended_for': 'Long-term investors, low cost'
    },
    'SPOT_HODL': {
        'name': 'Spot HODL',
        'description': 'Buy & hold spot positions (daily checks)',
        'emoji': '💎',
        'execution_interval_minutes': 1440,
        'trade_cooldown_minutes': 1440,
        'position_size_default': 0.15,
        'max_leverage': 1,  # Spot only
        'confidence_threshold': 60,
        'price_change_filter': 0.05,
        'hold_cooldown_minutes': 720,
        'spot_only': True,
        'accumulation_mode': True,
        'expected_holding_hours': 2160,
        'estimated_monthly_cost_range': '$2-6',
        'recommended_for': 'Conservative investors, no leverage'
    },
    'REBALANCER': {
        'name': 'Portfolio Rebalancer',
        'description': 'Weekly portfolio rebalancing',
        'emoji': '⚖️',
        'execution_interval_minutes': 10080,  # 7 days
        'trade_cooldown_minutes': 10080,
        'position_size_default': 0.20,
        'max_leverage': 1,
        'confidence_threshold': 50,
        'price_change_filter': None,
        'rebalance_threshold': 0.05,
        'spot_only': True,
        'expected_holding_hours': 4320,
        'estimated_monthly_cost_range': '$0.36-1.20',
        'recommended_for': 'Diversification, ultra-low maintenance'
    }
}

def get_profile(profile_name):
    """Get profile configuration by name"""
    return TRADING_PROFILES.get(profile_name, TRADING_PROFILES['SWING'])

def should_execute_bot(bot, current_time):
    """
    Determine if bot should execute based on profile and cooldowns

    Args:
        bot: Bot record with trading_profile, last_execution_at, etc.
        current_time: Current datetime

    Returns:
        (should_execute: bool, reason: str)
    """
    profile = get_profile(bot['trading_profile'])

    # Check execution interval
    if bot['last_execution_at']:
        minutes_since_last = (current_time - bot['last_execution_at']).total_seconds() / 60
        if minutes_since_last < profile['execution_interval_minutes']:
            return False, f"Too soon (last run {minutes_since_last:.0f}m ago, interval={profile['execution_interval_minutes']}m)"

    # Check trade cooldown
    if bot['last_trade_at']:
        minutes_since_trade = (current_time - bot['last_trade_at']).total_seconds() / 60
        if minutes_since_trade < profile['trade_cooldown_minutes']:
            return False, f"Trade cooldown (last trade {minutes_since_trade:.0f}m ago)"

    # Check HOLD cooldown
    if bot['last_hold_decision_at'] and 'hold_cooldown_minutes' in profile:
        minutes_since_hold = (current_time - bot['last_hold_decision_at']).total_seconds() / 60
        if minutes_since_hold < profile['hold_cooldown_minutes']:
            return False, f"HOLD cooldown (last HOLD {minutes_since_hold:.0f}m ago)"

    return True, "Ready to execute"
```

---

## UI Changes

### Bot Creation Form

Add profile selector before model selection:

```html
<div class="form-group">
    <label for="trading_profile">Trading Profile</label>
    <select id="trading_profile" name="trading_profile" required onchange="updateProfileInfo()">
        {% for profile_id, profile in profiles.items() %}
        <option value="{{ profile_id }}"
                {% if profile.is_default %}selected{% endif %}
                data-emoji="{{ profile.emoji }}"
                data-interval="{{ profile.execution_interval_minutes }}"
                data-cost="{{ profile.estimated_monthly_cost_range }}">
            {{ profile.emoji }} {{ profile.name }}
        </option>
        {% endfor %}
    </select>

    <!-- Profile info panel -->
    <div id="profile-info" class="profile-info-panel">
        <p class="profile-description"></p>
        <div class="profile-stats">
            <span>⏱️ Execution: <strong class="exec-interval"></strong></span>
            <span>💰 Est. cost: <strong class="est-cost"></strong>/month</span>
        </div>
        <small class="profile-recommended"></small>
    </div>
</div>
```

### Dashboard Updates

Show profile badge on bot cards:

```html
<div class="bot-card">
    <div class="bot-header">
        <span class="profile-badge">⚡ SCALPER</span>
        <h3>{{ bot.name }}</h3>
    </div>
    <div class="bot-stats">
        <span>Next run: in 3 minutes</span>
        <span>Last trade: 45 minutes ago</span>
    </div>
</div>
```

---

## Executor Changes

### Modified `execute_ai_bots.py`

```python
from saas.trading_profiles import should_execute_bot, get_profile
from datetime import datetime

def main():
    """Execute AI bots based on their trading profiles"""

    # Get all active bots
    active_bots = db.get_active_ai_bots()
    current_time = datetime.utcnow()

    executed_count = 0
    skipped_count = 0

    for bot in active_bots:
        # Check if bot should execute based on profile
        should_execute, reason = should_execute_bot(bot, current_time)

        if not should_execute:
            logger.info(f"Bot {bot['id']} ({bot['name']}): SKIPPED - {reason}")
            skipped_count += 1
            continue

        logger.info(f"Bot {bot['id']} ({bot['name']}): EXECUTING ({bot['trading_profile']} profile)")

        # Execute bot...
        executor.execute_bot(bot)

        # Update last_execution_at
        db.update_bot_execution_time(bot['id'], current_time)
        executed_count += 1

    logger.info(f"Execution complete: {executed_count} bots executed, {skipped_count} skipped")
```

---

## Render Configuration

**Keep 5-minute cron, but logic determines who executes:**

```yaml
# Cron Job (AI bot executor) - runs every 5 min
- type: cron
  name: dcabot-ai-executor
  schedule: "*/5 * * * *"  # Still 5 min - profiles determine actual execution
  startCommand: python saas/execute_ai_bots.py
```

**Why 5-min cron?**
- Scalpers need 5-min precision
- Other profiles filter themselves out via cooldowns
- Single cron job handles all profiles

---

## Migration Path

1. **Migration 020** - Add columns
2. **Default existing bots** to SWING profile
3. **UI update** - Show profile selector
4. **Executor update** - Respect cooldowns
5. **Dashboard** - Show profile badges and next execution time

---

## Cost Comparison

**Example: Running 1 bot for 30 days with DeepSeek ($2/1M tokens)**

| Profile    | Calls/Month | Tokens      | Cost/Month |
|------------|-------------|-------------|------------|
| SCALPER    | 8,640       | 34.56M      | $69.12     |
| SWING      | 1,440       | 5.76M       | $11.52     |
| DCA_LONG   | 120         | 0.48M       | $0.96      |
| SPOT_HODL  | 30          | 0.12M       | $0.24      |
| REBALANCER | 4           | 0.024M      | $0.048     |

**With free models (Qwen3 Max free tier):**
All profiles = $0/month (amazing!)

---

## Next Steps

Let me know if you want me to:
1. ✅ Create migration 020
2. ✅ Add `trading_profiles.py` configuration
3. ✅ Update bot creation form with profile selector
4. ✅ Modify executor to respect cooldowns
5. ✅ Update dashboard to show profile info

Or would you like to adjust the profile definitions first?
