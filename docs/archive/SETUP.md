# Setup Guide

Complete guide for setting up the Martingale Trading Bot locally and remotely.

## Prerequisites

- Python 3.8 or higher
- Git
- Phemex account with API keys
- (Optional) Telegram bot for notifications

## Local Development Setup

### 1. Clone the Repository

```bash
git clone https://github.com/pehur00/dcabot.git
cd dcabot
```

### 2. Create Virtual Environment

**On macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**On Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the project root:

```bash
# Phemex API Credentials
API_KEY=your_phemex_api_key_here
API_SECRET=your_phemex_api_secret_here

# Trading Configuration
SYMBOL=BTCUSDT:Long:True
EMA_INTERVAL=1
TESTNET=True  # Start with testnet!

# Optional: Telegram Notifications
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
```

**⚠️ Important**: Add `.env` to your `.gitignore` to avoid committing secrets!

### 5. Get Phemex API Keys

**Testnet (Recommended for testing):**
1. Go to https://testnet.phemex.com/
2. Register an account
3. Go to Account → API Management
4. Create new API key
5. **Save the key and secret** (you can't view the secret again)
6. Enable "Enable Trading" permission only

**Mainnet (Production):**
1. Go to https://phemex.com/
2. Complete KYC if required
3. Go to Account → API Management
4. Create new API key with trading permissions
5. **Optional**: Set IP whitelist for extra security
6. **Important**: Disable withdrawal permissions

### 6. Run the Bot Locally

**Test run:**
```bash
python main.py
```

The bot will:
- Load environment variables
- Initialize Phemex client
- Send startup notification (if Telegram configured)
- Execute strategy for each symbol
- Log all actions to console

**Stop the bot**: Press `Ctrl+C`

### 7. Understanding the Output

**JSON Log Format:**
```json
{
  "asctime": "2025-01-15 10:30:00",
  "levelname": "INFO",
  "message": "Position managed",
  "symbol": "BTCUSDT",
  "action": "Added to position",
  "json": {
    "current_price": 50000,
    "position_size": 0.015
  }
}
```

**Log Levels:**
- `INFO`: Normal operations
- `WARNING`: Issues that don't stop execution
- `ERROR`: Problems that need attention
- `DEBUG`: Detailed debugging info (disabled by default)

## Testing Before Going Live

### 1. Testnet Testing

Always test on testnet first:

```bash
# In .env file
TESTNET=True
```

**Benefits:**
- Free testnet coins
- No real money risk
- Same API as mainnet
- Test all features safely

**Get testnet funds:**
- Phemex testnet provides free test USDT
- Check testnet dashboard for balance

### 2. Dry Run Mode

For extra caution, you can modify the code to do dry runs:

```python
# In MartingaleTradingStrategy.py
def place_order(...):
    if os.getenv('DRY_RUN', 'False').lower() == 'true':
        self.logger.info("DRY RUN: Would place order", extra={"qty": qty, "price": price})
        return
    # ... rest of the code
```

Then set `DRY_RUN=True` in your `.env`.

### 3. Small Position Test

Start with minimal positions:

```python
# In MartingaleTradingStrategy.py CONFIG
'begin_size_of_balance': 0.001,  # 0.1% instead of 0.6%
'leverage': 2,                    # 2x instead of 6x
```

## Running Remotely

### Option 1: Render.com (Recommended)

See [DEPLOYMENT.md](./DEPLOYMENT.md) for full Render.com setup.

**Quick setup:**
1. Push code to GitHub
2. Connect Render to your repo
3. Create Cron Job service
4. Set environment variables
5. Deploy

**Pros:**
- Free tier available
- Auto-deployment on git push
- Built-in logging
- Easy to scale

### Option 2: VPS (DigitalOcean, AWS, etc.)

**Setup on Ubuntu VPS:**

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python
sudo apt install python3 python3-pip python3-venv git -y

# Clone repo
git clone https://github.com/pehur00/dcabot.git
cd dcabot

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
nano .env
# Add your environment variables, then save (Ctrl+X, Y, Enter)
```

**Run with systemd (auto-restart):**

Create service file:
```bash
sudo nano /etc/systemd/system/tradingbot.service
```

Add this content:
```ini
[Unit]
Description=Martingale Trading Bot
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/home/your_username/dcabot
Environment="PATH=/home/your_username/dcabot/venv/bin"
ExecStart=/home/your_username/dcabot/venv/bin/python main.py
Restart=always
RestartSec=60

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable tradingbot
sudo systemctl start tradingbot
sudo systemctl status tradingbot
```

View logs:
```bash
sudo journalctl -u tradingbot -f
```

### Option 3: Docker Deployment

**Build image:**
```bash
docker build -t martingale-bot .
```

**Run container:**
```bash
docker run -d \
  --name trading-bot \
  --restart unless-stopped \
  -e API_KEY=your_api_key \
  -e API_SECRET=your_api_secret \
  -e SYMBOL=BTCUSDT:Long:True \
  -e TESTNET=False \
  martingale-bot
```

**View logs:**
```bash
docker logs -f trading-bot
```

**Stop container:**
```bash
docker stop trading-bot
docker rm trading-bot
```

## Project Structure

```
dcabot/
├── main.py                          # Entry point
├── requirements.txt                 # Python dependencies
├── Dockerfile                       # Docker configuration
├── render.yaml                      # Render.com config
├── .gitignore                       # Git ignore rules
│
├── clients/                         # Exchange API clients
│   ├── TradingClient.py            # Abstract base
│   ├── PhemexClient.py             # Phemex implementation
│   └── BybitClient.py              # Bybit (not maintained)
│
├── strategies/                      # Trading strategies
│   ├── TradingStrategy.py          # Abstract base
│   └── MartingaleTradingStrategy.py # Main strategy
│
├── workflows/                       # Execution workflows
│   ├── Workflow.py                 # Abstract base
│   └── MartingaleTradingWorkflow.py # Main workflow
│
├── notifications/                   # Alert system
│   └── TelegramNotifier.py         # Telegram notifications
│
├── indicators/                      # Technical indicators
│   └── volatility.py               # Volatility calculations
│
├── utils/                           # Utility modules
│   └── retry.py                    # Retry & rate limiting
│
└── docs/                            # Documentation
    ├── DEPLOYMENT.md               # Deployment guide
    ├── SETUP.md                    # This file
    ├── STRATEGY.md                 # Strategy explanation
    └── TELEGRAM_SETUP.md           # Telegram bot setup
```

## Configuration Reference

### Strategy Configuration

Edit `strategies/MartingaleTradingStrategy.py`:

```python
CONFIG = {
    'buy_until_limit': 0.02,          # Max position: 2% of balance
    'profit_threshold': 0.003,        # Min profit: 0.3% of balance
    'profit_pnl': 0.1,                # Target: 10% PnL on position
    'leverage': 6,                    # 6x leverage
    'begin_size_of_balance': 0.006,   # Initial: 0.6% of balance
    'buy_below_percentage': 0.04,     # Add after 4% move
    'strategy_filter': 'EMA',         # Use EMA filtering
}
```

### Volatility Thresholds

Edit `indicators/volatility.py` → `is_high_volatility()`:

```python
def is_high_volatility(
    df,
    atr_threshold=None,              # Auto-calculated if None
    bb_width_threshold=8.0,          # Bollinger Band width %
    hist_vol_threshold=5.0           # Historical volatility %
):
```

### Rate Limiting

Edit `clients/PhemexClient.py`:

```python
rate_limiter = RateLimiter(
    max_calls=10,  # Max requests
    period=1.0     # Per second
)
```

## Troubleshooting

### Import Errors

```bash
ModuleNotFoundError: No module named 'pythonjsonlogger'
```

**Fix**: Reinstall dependencies
```bash
pip install --upgrade -r requirements.txt
```

### API Authentication Errors

```
HTTP(code=401), API(errorcode=401): Unauthorized
```

**Fix**:
- Check API_KEY and API_SECRET are correct
- Verify keys have trading permissions
- Try generating new API keys

### No Positions Opening

**Check:**
1. Is `automatic_mode` set to `True` in SYMBOL?
2. Is price on correct side of 200 EMA?
3. Is volatility too high?
4. Is there sufficient balance?
5. Are logs showing any errors?

### High CPU/Memory Usage

**Causes:**
- Too many symbols
- Too frequent execution
- Large historical data periods

**Fix:**
- Reduce number of trading pairs
- Increase cron interval
- Reduce EMA calculation periods

### Connection Timeouts

```
requests.exceptions.Timeout
```

**Fix:**
- Check internet connection
- Verify Phemex API status
- Built-in retry logic should handle temporary issues

## Maintenance

### Updating the Bot

```bash
# Pull latest changes
git pull origin main

# Update dependencies
pip install --upgrade -r requirements.txt

# Restart bot
# (Method depends on how you're running it)
```

### Monitoring

**What to monitor:**
- Position sizes (via Phemex dashboard)
- Telegram notifications
- Log files for errors
- Account balance trends
- API rate limit usage

**Recommended tools:**
- Phemex mobile app (position monitoring)
- Telegram (real-time alerts)
- Uptime monitoring (UptimeRobot, etc.)

### Backup

**What to backup:**
- `.env` file (keep secure!)
- Modified configuration files
- Custom strategy changes

**What NOT to backup:**
- `venv/` directory
- `__pycache__/` directories
- Log files (unless needed for analysis)

## Security Checklist

- [ ] API keys have trading-only permissions
- [ ] Withdrawal disabled on API keys
- [ ] `.env` file is in `.gitignore`
- [ ] Using testnet for initial testing
- [ ] Telegram bot token is secure
- [ ] IP whitelist enabled (if using static IP)
- [ ] Starting with small positions
- [ ] Monitoring is set up

## Getting Help

**Resources:**
- [Strategy explanation](./STRATEGY.md)
- [Deployment guide](./DEPLOYMENT.md)
- [Telegram setup](./TELEGRAM_SETUP.md)
- Phemex API docs: https://phemex-docs.github.io/

**Common Issues:**
- Check logs first (`docker logs` or console output)
- Verify environment variables are set
- Test with testnet before mainnet
- Ensure API permissions are correct

**Support:**
- GitHub Issues: Report bugs or ask questions
- Phemex Support: API-specific issues
- Telegram notifications: Help debug in real-time

## Next Steps

1. ✅ Complete this setup guide
2. ✅ Test on Phemex testnet
3. ✅ Set up Telegram notifications
4. ✅ Monitor for 24-48 hours on testnet
5. ✅ Deploy to production with small positions
6. ✅ Gradually increase position sizes as comfortable
7. ✅ Regular monitoring and adjustments

**Remember**: Start small, test thoroughly, and never risk more than you can afford to lose!
