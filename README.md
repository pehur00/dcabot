# Martingale Trading Bot

A sophisticated cryptocurrency trading bot implementing a Martingale-style averaging strategy with EMA filters, volatility protection, and automated risk management.

## Features

- **Martingale Strategy**: Systematic position averaging with EMA-based trend filtering
- **Volatility Protection**: Automatically pauses trading during high volatility (ATR, Bollinger Bands, Historical Volatility)
- **Telegram Notifications**: Real-time alerts for positions, profits, warnings, and errors
- **Risk Management**: Margin monitoring, position size limits, and liquidation protection
- **Multi-Symbol Support**: Trade multiple pairs simultaneously with different strategies
- **Retry & Rate Limiting**: Built-in error handling and API rate limiting
- **Cloud Ready**: Docker support and Render.com deployment configuration

## Quick Start

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

### 3. Run

```bash
python main.py
```

## Documentation

- **[Setup Guide](docs/SETUP.md)** - Local and remote installation
- **[Strategy Explanation](docs/STRATEGY.md)** - How the Martingale strategy works
- **[Deployment Guide](docs/DEPLOYMENT.md)** - Deploy to Render.com or VPS
- **[Telegram Setup](docs/TELEGRAM_SETUP.md)** - Configure notifications

## Architecture

```
dcabot/
├── clients/          # Exchange API clients (Phemex)
├── strategies/       # Trading strategy implementations
├── workflows/        # Execution workflows
├── notifications/    # Telegram notification system
├── indicators/       # Technical indicators (volatility, EMA)
├── utils/            # Retry logic and rate limiting
└── docs/             # Documentation
```

## Strategy Overview

The bot implements a **Martingale averaging strategy**:

1. **Entry**: Opens positions when price is trending (EMA filter)
2. **Averaging**: Adds to losing positions with increasing size
3. **Profit Taking**: Systematically closes profitable positions
4. **Volatility Protection**: Pauses during high volatility
5. **Risk Management**: Maintains safe margin levels

See [STRATEGY.md](docs/STRATEGY.md) for detailed explanation.

## Backtesting

The bot includes a comprehensive backtesting framework to validate strategy performance on historical data. The backtest simulates the exact bot behavior, checking every 5 minutes using 1-minute candles.

### Basic Usage

```bash
# Run backtest with default settings (1 day, $70 balance)
dcabot-env/bin/python backtest/backtest.py --symbol HBARUSDT --days 1 --interval 1 --source binance --balance 70 --side Long

# Run longer backtest (90 days)
dcabot-env/bin/python backtest/backtest.py --symbol HBARUSDT --days 90 --interval 1 --source binance --balance 70 --side Long

# Test different initial balance
dcabot-env/bin/python backtest/backtest.py --symbol BTCUSDT --days 30 --balance 100 --side Long

# Optimize profit-taking threshold
dcabot-env/bin/python backtest/backtest.py --symbol HBARUSDT --days 30 --profit-pnl 0.15 --side Long

# Test with margin protection (40% max margin cap to prevent early liquidations)
dcabot-env/bin/python backtest/backtest.py --symbol HBARUSDT --days 30 --max-margin-pct 0.40 --side Long
```

### Parameters

- `--symbol`: Trading pair (e.g., HBARUSDT, BTCUSDT, u1000PEPEUSDT)
- `--days`: Number of days to backtest (e.g., 1, 7, 30, 90)
- `--interval`: Candle interval in minutes (always use `1` for 1-minute candles)
- `--source`: Data source (`binance` recommended)
- `--balance`: Initial balance in USDT (default: 100)
- `--side`: Position side (`Long` or `Short`)
- `--profit-pnl`: Profit-taking threshold as decimal (default: 0.1 = 10%)
- `--max-margin-pct`: Optional maximum margin usage cap (e.g., 0.40 = 40% max). When absent, no cap is applied

### Example Results (34 days, HBARUSDT)

**Performance Metrics:**
- **Initial Balance**: $70.00
- **Final Balance**: $159.52
- **Total Return**: +127.89%
- **Win Rate**: 100.00% (30 wins, 0 losses)
- **Max Drawdown**: 0.58%
- **Total Operations**: 4,141 (30 opens, 4,020 adds, 61 reduces, 30 closes)
- **Average Win**: $1.16

### Backtest Chart Breakdown

The backtest generates a comprehensive 5-panel chart:

1. **Price Chart**: Shows price action with 1-minute EMA200 and all trade markers
   - Green triangles = OPEN positions
   - Blue triangles = ADD to positions
   - Orange squares = REDUCE positions (profit-taking)
   - Red circles = CLOSE positions

2. **Account Balance & Total Value**: Clean view of your account performance
   - Blue line = Realized balance (only changes on close/reduce)
   - Purple line = Total value (balance + unrealized PnL)

3. **Position Size Chart**: Shows margin invested over time
   - Orange filled area = How much margin is actively in positions
   - Helps visualize when bot is heavily invested vs idle

4. **Drawdown Analysis**: Shows risk metrics and account drawdowns

5. **Performance Summary**: Detailed statistics and trade breakdown

### Output Files

All backtest results are saved to `backtest/results/` with timestamps:

```
HBARUSDT_Long_bal70_profit0.10_20251027_154543_chart.png    # Visual charts
HBARUSDT_Long_bal70_profit0.10_20251027_154541_balance.csv  # Balance history
HBARUSDT_Long_bal70_profit0.10_20251027_154541_trades.csv   # Trade log
```

### Important Notes

- Backtest checks every 5 minutes (matching real bot behavior)
- Uses 1-minute candles for accurate price data
- Includes all volatility protections and risk management
- Simulates exact margin calculations and leverage (10x)
- Fees are included in calculations (0.075% per trade)

## Configuration

Key parameters in `strategies/MartingaleTradingStrategy.py`:

```python
CONFIG = {
    'leverage': 10,                   # Trading leverage (10x)
    'begin_size_of_balance': 0.006,   # Initial position: 0.6% of balance
    'buy_until_limit': 0.05,          # Max position: 5% of balance (in margin)
    'profit_threshold': 0.003,        # Min profit: 0.3% of balance to consider closing
    'profit_pnl': 0.1,                # Target: 10% profit on margin invested
    'max_margin_pct': None,           # Optional: Max margin cap (e.g., 0.40 = 40%). None = no limit
}
```

**Important Notes**:
- `buy_until_limit` refers to margin invested, not notional value. With 10x leverage, 5% margin = 50% notional position.
- `max_margin_pct` provides an **optional safety buffer** against early liquidations:
  - When `None` (default): No pre-emptive protection, relies on exchange liquidation engine
  - When set (e.g., `0.40`): Bot stops adding to positions when margin usage would exceed 40%
  - **Example**: With $100 balance and 40% cap, bot won't use more than $40 in margin
  - This creates a buffer before reaching exchange liquidation threshold (typically ~100% margin usage)
  - Useful for preventing blow-ups during extreme volatility or fast crashes

## Requirements

- Python 3.8+
- Phemex account with API access
- (Optional) Telegram bot for notifications

## Deployment

### Render.com (Recommended)

1. Push code to GitHub
2. Create Cron Job on Render.com
3. Set environment variables
4. Deploy

See [DEPLOYMENT.md](docs/DEPLOYMENT.md) for details.

### Docker

```bash
docker build -t martingale-bot .
docker run -d \
  -e API_KEY=your_key \
  -e API_SECRET=your_secret \
  -e SYMBOL=BTCUSDT:Long:True \
  martingale-bot
```

## Monitoring

- **Telegram**: Real-time notifications for all bot actions
- **Logs**: Structured JSON logging for easy parsing
- **Phemex Dashboard**: Monitor positions and PnL

## Safety Features

- ✅ Testnet support for safe testing
- ✅ Rate limiting to prevent API bans
- ✅ Retry logic for failed requests
- ✅ Margin level monitoring
- ✅ Volatility detection and pausing
- ✅ Position size limits
- ✅ Emergency liquidation protection
- ✅ Optional margin usage cap (prevents early liquidations)

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

- **Documentation**: See `docs/` directory
- **Issues**: Report bugs via GitHub Issues
- **Strategy Questions**: See [STRATEGY.md](docs/STRATEGY.md)

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history.

## Disclaimer

This software is provided for educational purposes. Cryptocurrency trading carries significant risk. Past performance does not guarantee future results. The authors are not responsible for any financial losses incurred using this bot.

**Trade responsibly. Start small. Test thoroughly.**
