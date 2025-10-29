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

# Test with different leverage (default is 10x)
dcabot-env/bin/python backtest/backtest.py --symbol BTCUSDT --days 30 --leverage 5 --side Long
dcabot-env/bin/python backtest/backtest.py --symbol BTCUSDT --days 30 --leverage 20 --side Long
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
- `--leverage`: Leverage multiplier (default: 10). Test different leverages like 5, 10, 15, 20

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
- Simulates exact margin calculations and leverage (configurable via `--leverage`)
- Fees are included in calculations (0.075% per trade)

### Automated Testing Tools

**Test Multiple Leverages** (`test_leverages.sh`):
```bash
# Test one symbol with 5x, 10x, 15x, 20x leverage
./test_leverages.sh HBARUSDT 30 200 Long
# Results saved as: HBARUSDT_lev5x_30d_*, HBARUSDT_lev10x_30d_*, etc.
```

**Test Top Volume Coins** (`test_top_coins.py`):
```bash
# Test top 10 volume coins automatically
dcabot-env/bin/python test_top_coins.py --leverage 10 --days 7 --balance 200

# Test specific coins
dcabot-env/bin/python test_top_coins.py --coins BTCUSDT ETHUSDT SOLUSDT --days 30

# Test top 5 coins with custom settings
dcabot-env/bin/python test_top_coins.py --num-coins 5 --leverage 5 --days 60 --balance 500
```

**Features**:
- Automatically fetches top volume coins from Binance (excludes stablecoins/fiat)
- Runs backtests sequentially for all coins
- Generates summary CSV comparing performance across all coins
- Saves individual charts, balance CSVs, and trade logs for each coin

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
- `max_margin_pct` provides **margin protection with dynamic tapering**:
  - When `None`: No protection (not recommended for live trading)
  - When set (e.g., `0.50`): Implements smart tapering system
  - **Dynamic Tapering**: Order sizes reduce exponentially as margin usage increases
    - At 0% margin: 100% order size (full adds)
    - At 25% margin: 56% order size
    - At 40% margin: 4% order size
    - At 50% margin: 0% order size (no adds)
  - **Benefits**: More trades with smaller sizes, better price averaging, maintains volatility buffer
  - **Example**: With $200 balance and 50% cap, bot gradually reduces order sizes approaching $100 margin
  - **Result**: Never hits the hard cap, prevents liquidations while staying active

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
- ✅ **Dynamic position tapering** (reduces order sizes as margin increases)
- ✅ Optional margin usage cap (50% default with exponential tapering)

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
