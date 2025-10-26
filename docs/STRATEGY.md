# Martingale Trading Strategy Explained

This document explains how the Martingale trading strategy works in this bot.

## Overview

The bot implements a **Martingale-style averaging down strategy** with EMA filters and volatility protection. It's designed to:
- Enter positions when price is trending (based on EMA)
- Average down when price moves against you
- Take profits systematically
- Protect against liquidation
- Pause during high volatility

**⚠️ WARNING**: Martingale strategies carry significant risk. Never risk more than you can afford to lose.

## Core Strategy Logic

### 1. Position Entry

The bot opens new positions when:
- **Automatic mode is enabled** for the symbol
- **Price is trending correctly**:
  - **Long positions**: Current price > 200 EMA (1-hour)
  - **Short positions**: Current price < 200 EMA (1-hour)
- **Volatility is normal** (not in high volatility conditions)

**Initial Position Size**: 0.6% of account balance (with 6x leverage = ~3.6% exposure)

### 2. Adding to Positions (Averaging Down/Up)

The bot adds to existing positions when:

**A. Position is small** (< 2% of account balance):
- Automatically adds to build up position
- Regardless of current PnL

**B. Position is underwater**:
- Price moved > 5% against you
- Position is on the correct side of 50 EMA
- Margin level is safe (> 200%)
- **Volatility is normal** (exception: always adds if margin < 200%)

**C. Critical margin level**:
- Margin level < 200% (approaching liquidation)
- Bot adds to position **even during high volatility**
- This is a safety mechanism to prevent liquidation

### 3. Position Sizing (Martingale Element)

When adding to a losing position, the order size increases:

```python
qty = (position_value * leverage * abs(pnl_percentage)) / current_price
```

**Example**:
- Position value: $100
- Loss: -10% (pnl_percentage = -0.10)
- Leverage: 6x
- Current price: $50,000

New order: (100 * 6 * 0.10) / 50000 = 0.0012 BTC

**Effect**: Larger losses → Larger add-on orders (classic Martingale)

### 4. Taking Profits

**Partial Profit Taking**:

The bot closes portions of the position as it grows:

| Position Size | Action | Reason |
|---------------|--------|---------|
| > 7.5% of balance | Close 33% | Reduce exposure |
| > 10% of balance | Close 50% | Reduce exposure further |

**Full Position Close**:

Bot closes the entire position when:
- **PnL percentage > 10%** of position value
- AND **Absolute profit > 0.3%** of total balance

**Example**:
- Total balance: $1,000
- Position value: $200
- Unrealized PnL: $25 (12.5% of position, 2.5% of balance)
- ✅ Both conditions met → Close entire position

### 5. EMA Filters

The strategy uses Exponential Moving Averages to determine trend:

**200 EMA (1-hour)**: Primary trend filter
- Determines if we should be Long or Short
- Long bias when price > 200 EMA
- Short bias when price < 200 EMA

**200 EMA (configurable interval)**: Secondary filter
- Used to validate adding to positions
- Ensures we don't average down against the trend

**50 EMA (configurable interval)**: Micro trend
- Additional validation for position adds
- Helps avoid catching falling knives

### 6. Volatility Protection

The bot monitors three volatility indicators:

**Average True Range (ATR)**:
- Measures absolute volatility
- Triggered when ATR > 1.5x its 50-period average

**Bollinger Band Width**:
- Measures relative volatility
- Triggered when width > 8% of price

**Historical Volatility**:
- Standard deviation of returns
- Triggered when > 5% daily volatility

**Actions During High Volatility**:
- ❌ **Stop opening new positions**
- ❌ **Stop adding to profitable positions**
- ✅ **Still add if margin < 200%** (liquidation protection)
- 📢 **Send Telegram alert**

## Risk Management

### Leverage

**Default**: 6x leverage
- Amplifies both gains and losses
- Must be set manually on Phemex (API limitation)

### Position Limits

**Maximum position size**: 10% of account balance
- Bot triggers profit-taking before reaching this
- Reduces account blow-up risk

**Minimum entry size**: 0.6% of account balance
- Allows room for multiple add-ons
- Prevents overexposure on first entry

### Margin Monitoring

Bot continuously monitors margin level:
- **Margin Level = (Position Margin + Unrealized PnL) / Maintenance Margin**
- **Warning sent** when < 1.5 (150%)
- **Critical level** is < 2.0 (200%)
- **Liquidation** occurs at ~1.0 (100%)

## Configuration

Key parameters in `CONFIG` (in `MartingaleTradingStrategy.py`):

```python
CONFIG = {
    'buy_until_limit': 0.02,          # Max position size (2% of balance)
    'profit_threshold': 0.003,        # Min profit to consider closing (0.3% of balance)
    'profit_pnl': 0.1,                # Target PnL percentage (10% of position)
    'leverage': 6,                    # Trading leverage
    'begin_size_of_balance': 0.006,   # Initial position size (0.6% of balance)
    'buy_below_percentage': 0.04,     # Min price drop before adding (4%)
}
```

## Example Scenarios

### Scenario 1: Successful Trade

1. **Entry**: BTC @ $50,000 (Long), 1.5% of balance
   - Price > 200 EMA ✅
   - Low volatility ✅

2. **Price drops to $49,000** (-2%)
   - Add 2% of balance (averaging down)

3. **Price drops to $48,000** (-4%)
   - Add 3% of balance (larger add-on)

4. **Price recovers to $50,500**
   - Position in profit
   - Close full position: +2.5% on account

### Scenario 2: High Volatility Protection

1. **Entry**: ETH @ $3,000 (Short), 1.5% of balance

2. **High volatility detected** (ATR spike)
   - Telegram alert sent 📢
   - No new adds (unless margin critical)

3. **Price drops to $2,900** (profitable)
   - Still no adds (volatility high)
   - Wait for volatility to normalize

4. **Volatility normalizes**
   - Normal operation resumes

### Scenario 3: Near Liquidation

1. **Entry**: BTC @ $50,000 (Long), 1.5% of balance

2. **Price dumps to $45,000** (-10%)
   - Multiple add-ons triggered
   - Position now 8% of balance
   - Down -15% overall

3. **Margin level drops to 180%**
   - ⚠️ Critical level
   - Bot adds **even during high volatility**
   - Prevents liquidation

4. **Price recovers to $47,000**
   - Margin level back to safe range
   - Eventually close at profit

## Strategy Strengths

✅ **Systematic profit taking**: Reduces emotional trading
✅ **Trend following**: EMA filters improve win rate
✅ **Volatility aware**: Pauses during dangerous conditions
✅ **Liquidation protection**: Always adds when margin critical
✅ **Automated**: Runs 24/7 without human intervention

## Strategy Weaknesses

❌ **Extended drawdowns**: Can lose significantly before recovering
❌ **Black swan risk**: Large, fast moves can cause liquidation
❌ **Capital intensive**: Needs reserve to average down
❌ **Leverage amplifies losses**: 6x leverage means 6x the risk
❌ **No hard stop-loss**: Relies on margin level, not price stops

## Best Practices

1. **Start small**: Use only 10-20% of your trading capital
2. **Test on testnet first**: Verify everything works
3. **Monitor frequently**: Check positions daily
4. **Set API restrictions**: Disable withdrawals on Phemex
5. **Use Telegram alerts**: Stay informed of all actions
6. **Keep reserves**: Don't use 100% of account balance
7. **Understand the risks**: This strategy can blow up your account

## When to Use This Strategy

✅ **Good for**:
- Ranging markets with clear support/resistance
- Moderate volatility conditions
- Liquid markets (BTC, ETH)
- Traders comfortable with drawdowns

❌ **Bad for**:
- Strongly trending markets (against your position)
- Extreme volatility / Black swan events
- Low liquidity pairs
- Beginners or risk-averse traders

## Modifications & Improvements

Consider adjusting:
- **Leverage**: Lower = safer, less profit potential
- **Position limits**: Smaller = less risk, less profit
- **EMA periods**: Tune to your market conditions
- **Volatility thresholds**: More conservative = fewer trades
- **Profit targets**: Higher = hold longer, more risk

## Disclaimer

This strategy is provided for educational purposes. Cryptocurrency trading carries significant risk. Past performance does not guarantee future results. Only trade with funds you can afford to lose entirely.

**The bot creator is not responsible for any losses incurred using this strategy.**
