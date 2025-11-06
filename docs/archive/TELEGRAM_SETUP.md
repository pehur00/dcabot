# Telegram Bot Setup Guide

This guide will walk you through setting up Telegram notifications for your trading bot.

## Prerequisites
- A Telegram account
- Telegram app installed on your phone or computer

## Step 1: Create a Telegram Bot

1. Open Telegram and search for **@BotFather** (the official bot for creating bots)
2. Start a chat with BotFather and send the command:
   ```
   /newbot
   ```
3. BotFather will ask you to choose a name for your bot. Enter any name you like (e.g., "My Trading Bot")
4. Next, choose a username for your bot. It must end in 'bot' (e.g., "my_trading_bot")
5. BotFather will respond with a message containing your **Bot Token**. It looks like this:
   ```
   123456789:ABCdefGHIjklMNOpqrsTUVwxyz
   ```
6. **IMPORTANT**: Save this token securely. You'll need it for the `TELEGRAM_BOT_TOKEN` environment variable.

## Step 2: Get Your Chat ID

You need to get your Telegram Chat ID so the bot knows where to send messages.

### Method 1: Using @userinfobot (Easiest)

1. Search for **@userinfobot** in Telegram
2. Start a chat with it and send any message
3. The bot will reply with your user information, including your **Chat ID**
4. Copy the Chat ID (it's a number like `123456789`)

### Method 2: Using the Telegram API

1. Start a chat with your newly created bot (search for its username)
2. Send any message to your bot (e.g., "Hello")
3. Open this URL in your browser (replace `YOUR_BOT_TOKEN` with your actual token):
   ```
   https://api.telegram.org/botYOUR_BOT_TOKEN/getUpdates
   ```
4. Look for the `"chat":{"id":` field in the JSON response
5. The number after `"id":` is your Chat ID

## Step 3: Configure Environment Variables

Add these two environment variables to your system:

### For Local Development:

Create or edit a `.env` file in your project root:

```bash
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=123456789
```

### For Render.com Deployment:

1. Go to your Render dashboard
2. Select your service
3. Click on "Environment" in the left sidebar
4. Add two new environment variables:
   - Key: `TELEGRAM_BOT_TOKEN`, Value: Your bot token
   - Key: `TELEGRAM_CHAT_ID`, Value: Your chat ID
5. Click "Save Changes"

## Step 4: Test Your Setup

Once configured, start your trading bot. You should receive a "Bot Started" notification in Telegram.

If you don't receive a message:
1. Double-check your Bot Token and Chat ID
2. Make sure you've started a chat with your bot (send it any message)
3. Check your bot logs for any error messages

## Notification Types

Your bot will send the following types of notifications:

- **🚀 Bot Started**: When the bot starts running
- **🟢 Position Opened/Added**: When a trade is opened or added to
- **🔴 Position Closed**: When a trade is closed (with PnL information)
- **⚠️ High Volatility Alert**: When market volatility exceeds thresholds
- **🚨 Margin Warning**: When your position is at risk of liquidation
- **❌ Error**: When critical errors occur

## Troubleshooting

### Bot doesn't respond
- Make sure you've started a conversation with your bot first
- Verify the bot token is correct

### Wrong chat ID
- Make sure the chat ID doesn't have any extra characters
- The chat ID should be a number (can be negative for group chats)

### Notifications not received
- Check your environment variables are set correctly
- Ensure your bot has permission to send messages
- Check the bot logs for error messages

## Security Notes

- **Never share your Bot Token publicly**
- **Never commit your token to git**
- Use environment variables or secrets management
- Regenerate your token if it's ever exposed (use `/token` command with BotFather)

## Group Chats (Optional)

To send notifications to a group:

1. Create a Telegram group
2. Add your bot to the group
3. Make your bot an admin (if needed)
4. Get the group Chat ID:
   - Send a message in the group
   - Visit: `https://api.telegram.org/botYOUR_BOT_TOKEN/getUpdates`
   - Look for the group's chat ID (it will be negative, e.g., `-123456789`)
5. Use this negative number as your `TELEGRAM_CHAT_ID`

## Need Help?

If you encounter any issues:
1. Check the bot logs for detailed error messages
2. Verify all environment variables are set correctly
3. Test your bot token using the Telegram API directly
4. Make sure you've started a chat with your bot
