# Changelog

All notable changes to the Martingale Trading Bot.

## [v4] - 2025-01-15

### Added

**Telegram Notifications**
- Real-time notifications for all trading actions
- Position opened/closed alerts with PnL information
- High volatility warnings
- Margin level warnings when approaching liquidation
- Bot startup/shutdown notifications
- Error alerts

**Volatility Protection**
- ATR (Average True Range) monitoring
- Bollinger Band Width calculation
- Historical volatility tracking
- Automatic trading pause during high volatility
- Exception: Always adds to position if margin < 200% (liquidation protection)

**Error Handling & Resilience**
- Retry decorator with exponential backoff
- Rate limiting (10 requests/second)
- Graceful error handling throughout
- Detailed error logging

**Documentation**
- Complete strategy explanation (STRATEGY.md)
- Setup guide for local and remote (SETUP.md)
- Render.com deployment guide (DEPLOYMENT.md)
- Telegram bot setup instructions (TELEGRAM_SETUP.md)
- Cleaned up README.md

### Fixed

**Critical Bugs**
- Fixed `parse_symbols()` splitting by 3 instead of 2
- Fixed `PhemexAPIException` inheritance issue
- Fixed `PhemexClient` not inheriting from `TradingClient`
- Fixed ambiguous logic in `is_valid_position()`

**Improvements**
- Cleaned up requirements.txt
- Better margin level calculation
- More consistent logging

### Changed

**Strategy Behavior**
- Now checks volatility before position actions
- Pauses new entries during high volatility
- More conservative position management

**Configuration**
- Simplified requirements.txt
- Removed unused dependencies

## [v3] - Previous

- Added Phemex support
- Made the script job-based (single iteration for cron/jobs)

## [v2] - Previous

- Added EMA strategy
- Changes in class structure
- Preparations for multiple strategies

## [v1] - Initial

- First version with basic Martingale strategy
