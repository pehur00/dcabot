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

The bot includes a comprehensive backtesting framework to validate strategy performance on historical data:

```bash
python backtest/backtest.py --symbol u1000PEPEUSDT --days 180 --interval 60 --source binance --balance 10000
```

### Example Results (180 days, u1000PEPEUSDT)

![Backtest Results](backtest/example_backtest_180days.png)

**Performance Metrics:**
- **Total Return**: +8.73%
- **Win Rate**: 87.50%
- **Max Drawdown**: 1.19%
- **Total Trades**: 8 (61 operations)

The visualization includes:
- **Price Chart**: Shows price action with EMA200/EMA50 and trade markers
- **Balance History**: Realized balance and total value (including unrealized PnL)
- **Drawdown Analysis**: Visual representation of portfolio risk
- **Performance Summary**: Detailed metrics and trade breakdown

### Running Your Own Backtests

```bash
# Basic backtest
python backtest/backtest.py --symbol u1000PEPEUSDT --days 30 --interval 60 --source binance

# Test with different initial balance
python backtest/backtest.py --balance 100 --days 180

# Optimize profit-taking strategy
python backtest/backtest.py --profit-pnl 0.15 --days 180

# All results saved to backtest/results/ with unique filenames
```

## Configuration

Key parameters in `strategies/MartingaleTradingStrategy.py`:

```python
CONFIG = {
    'leverage': 6,                    # Trading leverage
    'begin_size_of_balance': 0.006,   # Initial position: 0.6% of balance
    'buy_until_limit': 0.02,          # Max position: 2% of balance
    'profit_threshold': 0.003,        # Min profit: 0.3% of balance
    'profit_pnl': 0.1,                # Target: 10% PnL on position
}
```

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
