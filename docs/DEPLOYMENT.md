# Deployment Guide

This guide covers deploying the Martingale Trading Bot to Render.com.

## Prerequisites

- A GitHub account
- A Render.com account (free tier works)
- Your Phemex API credentials
- (Optional) Telegram bot credentials

## Deploy to Render.com

### Step 1: Push Code to GitHub

1. Make sure your code is in a GitHub repository
2. Ensure all changes are committed and pushed:
   ```bash
   git add .
   git commit -m "Prepare for deployment"
   git push origin main
   ```

### Step 2: Connect to Render

1. Log in to [Render.com](https://render.com)
2. Click "New +" and select "Cron Job"
3. Connect your GitHub repository
4. Select the repository containing your bot

### Step 3: Configure the Cron Job

**Basic Settings:**
- **Name**: `martingale-trading-bot` (or your preferred name)
- **Region**: Choose closest to you
- **Branch**: `main` (or your default branch)
- **Runtime**: `Docker`
- **Docker Context**: `.` (root directory)
- **Docker File Path**: `./Dockerfile`

**Schedule:**
- Choose how often you want the bot to run
- Examples:
  - Every 5 minutes: `*/5 * * * *`
  - Every hour: `0 * * * *`
  - Every 15 minutes: `*/15 * * * *`

**Recommended**: `*/5 * * * *` (every 5 minutes)

### Step 4: Set Environment Variables

Click "Add Environment Variable" and add the following:

#### Required Variables:

```
API_KEY=your_phemex_api_key
API_SECRET=your_phemex_api_secret
SYMBOL=BTCUSDT:Long:True,ETHUSDT:Short:False
EMA_INTERVAL=1
TESTNET=False
```

#### Optional Variables (Telegram):

```
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
```

**SYMBOL Format**: `SYMBOL:SIDE:AUTO_MODE`
- `SYMBOL`: Trading pair (e.g., BTCUSDT, ETHUSDT)
- `SIDE`: `Long` or `Short`
- `AUTO_MODE`: `True` (opens new positions automatically) or `False` (manual)

**Examples:**
- `BTCUSDT:Long:True` - Auto-trade BTC long positions
- `ETHUSDT:Short:False` - Manage ETH short positions manually
- `BTCUSDT:Long:True,ETHUSDT:Short:True` - Multiple pairs

### Step 5: Deploy

1. Click "Create Cron Job"
2. Render will build your Docker image
3. Once built, the bot will run on the schedule you specified

### Step 6: Monitor

**View Logs:**
1. Go to your Render dashboard
2. Click on your cron job
3. Click "Logs" to see real-time execution logs

**Check Status:**
- Look for "Bot Started" messages
- Check Telegram notifications (if configured)
- Monitor for any error messages

## Using render.yaml (Infrastructure as Code)

The repository includes a `render.yaml` file for automated deployment.

### Update render.yaml

Edit `render.yaml` to customize:

```yaml
services:
  - type: cron
    name: martingale-bot
    runtime: docker
    schedule: "*/5 * * * *"  # Every 5 minutes
    dockerfilePath: ./Dockerfile
    envVars:
      - key: API_KEY
        sync: false  # Set to true to sync from Render dashboard
      - key: API_SECRET
        sync: false
      - key: SYMBOL
        value: BTCUSDT:Long:True
      - key: EMA_INTERVAL
        value: 1
      - key: TESTNET
        value: False
```

### Deploy with Blueprint

1. Push your `render.yaml` to GitHub
2. In Render dashboard, click "New +" → "Blueprint"
3. Connect your repository
4. Render will automatically create services based on the YAML
5. Set environment variables in the dashboard (for security)

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `API_KEY` | Yes | - | Phemex API key |
| `API_SECRET` | Yes | - | Phemex API secret |
| `SYMBOL` | Yes | - | Trading pairs and sides |
| `EMA_INTERVAL` | No | 1 | EMA calculation interval (minutes) |
| `TESTNET` | No | False | Use Phemex testnet |
| `TELEGRAM_BOT_TOKEN` | No | - | Telegram bot token for notifications |
| `TELEGRAM_CHAT_ID` | No | - | Telegram chat ID for notifications |

## Security Best Practices

1. **Never commit API keys** to your repository
2. **Use environment variables** for all sensitive data
3. **Enable API key restrictions** on Phemex:
   - IP whitelist (if using static IP)
   - Limit to trading only (no withdrawals)
4. **Start with testnet** to verify everything works
5. **Monitor logs regularly** for any issues

## Troubleshooting

### Build Fails

**Check Docker file:**
- Ensure `Dockerfile` exists in the root directory
- Verify all dependencies are in `requirements.txt`

**Check logs:**
- Look for Python import errors
- Verify all environment variables are set

### Bot Runs But No Trades

**Common issues:**
- Wrong API credentials
- Insufficient balance
- Symbol not available on Phemex
- EMA conditions not met

**Debugging:**
1. Check logs for error messages
2. Verify API permissions on Phemex
3. Test with `TESTNET=True` first
4. Check if automatic mode is enabled

### Frequent Errors

**Rate limiting:**
- Reduce cron frequency
- The bot has built-in rate limiting (10 req/sec)

**Connection timeouts:**
- Check Render's status page
- Verify Phemex API is accessible

**Authentication errors:**
- Regenerate API keys on Phemex
- Update environment variables on Render

## Stopping the Bot

To stop the bot:

1. Go to Render dashboard
2. Select your cron job
3. Click "Suspend" at the top right
4. Or delete the service entirely

**Note**: Suspending doesn't close open positions. Close positions manually on Phemex first if needed.

## Updating the Bot

When you push updates to GitHub:

1. Render automatically detects changes
2. Rebuilds the Docker image
3. Next scheduled run uses the new code

**Manual redeploy:**
- Click "Manual Deploy" → "Clear build cache & deploy"

## Cost Estimate

**Render Free Tier:**
- 750 hours/month of cron jobs (free)
- Sufficient for running the bot continuously

**Paid Plans:**
- Only needed for advanced features
- Not required for basic bot operation

## Monitoring & Alerts

**Built-in Monitoring:**
- Telegram notifications (recommended)
- Render logs and metrics
- Error notifications via Telegram

**Additional Tools:**
- UptimeRobot: Monitor if bot is running
- Sentry: Error tracking (optional)
- Custom dashboards with the JSON logs

## Backup & Recovery

**Position Data:**
- Bot doesn't store local state
- All positions retrieved from Phemex API
- Safe to restart/redeploy anytime

**Configuration:**
- Environment variables stored in Render
- Export variables before making changes
- Keep a local copy of your settings

## Need Help?

- Check Render documentation: https://render.com/docs
- Review bot logs for detailed errors
- Test with TESTNET first
- Join Render community forums
