import asyncio
import logging
import os
from typing import Optional
import requests


class TelegramNotifier:
    """
    Telegram notification service for trading bot alerts.
    Sends notifications for positions, trades, errors, and warnings.
    """

    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None, logger: Optional[logging.Logger] = None):
        """
        Initialize Telegram notifier.

        Args:
            bot_token: Telegram bot token (or set TELEGRAM_BOT_TOKEN env var)
            chat_id: Telegram chat ID (or set TELEGRAM_CHAT_ID env var)
            logger: Logger instance
        """
        self.bot_token = bot_token or os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = chat_id or os.getenv('TELEGRAM_CHAT_ID')
        self.logger = logger or logging.getLogger(__name__)
        self.enabled = bool(self.bot_token and self.chat_id)

        if not self.enabled:
            self.logger.warning("Telegram notifications disabled: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set")
        else:
            self.logger.info("Telegram notifications enabled")

    def _send_message(self, message: str, parse_mode: str = 'HTML') -> bool:
        """
        Send a message via Telegram bot.

        Args:
            message: Message text to send
            parse_mode: Parse mode (HTML or Markdown)

        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False

        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': parse_mode,
                'disable_web_page_preview': True
            }

            response = requests.post(url, json=payload, timeout=10)

            if response.status_code == 200:
                self.logger.debug("Telegram notification sent successfully")
                return True
            else:
                self.logger.error(f"Failed to send Telegram notification: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            self.logger.error(f"Error sending Telegram notification: {e}")
            return False

    def notify_position_opened(self, symbol: str, side: str, pos_side: str, qty: float, price: float,
                               balance: float, position_size_pct: float):
        """Send notification when a new position is opened or added to."""
        message = (
            f"🟢 <b>Position Opened/Added</b>\n\n"
            f"Symbol: <code>{symbol}</code>\n"
            f"Side: <b>{side}</b> ({pos_side})\n"
            f"Quantity: <code>{qty}</code>\n"
            f"Price: <code>{price}</code>\n"
            f"Position Size: <code>{position_size_pct:.2f}%</code> of balance\n"
            f"Total Balance: <code>${balance:.2f}</code>"
        )
        return self._send_message(message)

    def notify_position_closed(self, symbol: str, pos_side: str, qty: float, price: float,
                               pnl: float, pnl_pct: float, reason: str):
        """Send notification when a position is closed."""
        emoji = "🟢" if pnl > 0 else "🔴"
        pnl_sign = "+" if pnl > 0 else ""

        message = (
            f"{emoji} <b>Position Closed</b>\n\n"
            f"Symbol: <code>{symbol}</code>\n"
            f"Side: <b>{pos_side}</b>\n"
            f"Quantity: <code>{qty}</code>\n"
            f"Price: <code>{price}</code>\n"
            f"PnL: <code>{pnl_sign}${pnl:.2f}</code> ({pnl_sign}{pnl_pct:.2f}%)\n"
            f"Reason: {reason}"
        )
        return self._send_message(message)

    def notify_high_volatility(self, symbol: str, volatility_metric: str, value: float,
                               threshold: float, action: str):
        """Send notification when high volatility is detected."""
        message = (
            f"⚠️ <b>HIGH VOLATILITY ALERT</b>\n\n"
            f"Symbol: <code>{symbol}</code>\n"
            f"Metric: {volatility_metric}\n"
            f"Value: <code>{value:.4f}</code>\n"
            f"Threshold: <code>{threshold:.4f}</code>\n"
            f"Action: <b>{action}</b>"
        )
        return self._send_message(message)

    def notify_margin_warning(self, symbol: str, pos_side: str, margin_level: float,
                             position_value: float, unrealized_pnl: float):
        """Send notification when margin level is concerning."""
        message = (
            f"🚨 <b>MARGIN WARNING</b>\n\n"
            f"Symbol: <code>{symbol}</code>\n"
            f"Side: <b>{pos_side}</b>\n"
            f"Margin Level: <code>{margin_level:.2f}</code>\n"
            f"Position Value: <code>${position_value:.2f}</code>\n"
            f"Unrealized PnL: <code>${unrealized_pnl:.2f}</code>\n\n"
            f"⚠️ Position at risk of liquidation!"
        )
        return self._send_message(message)

    def notify_error(self, error_type: str, symbol: str, error_message: str):
        """Send notification when an error occurs."""
        message = (
            f"❌ <b>ERROR</b>\n\n"
            f"Type: {error_type}\n"
            f"Symbol: <code>{symbol}</code>\n"
            f"Message: {error_message}"
        )
        return self._send_message(message)

    def notify_daily_summary(self, total_trades: int, profitable_trades: int,
                            total_pnl: float, balance: float):
        """Send daily performance summary."""
        win_rate = (profitable_trades / total_trades * 100) if total_trades > 0 else 0
        pnl_sign = "+" if total_pnl > 0 else ""
        emoji = "🟢" if total_pnl > 0 else "🔴"

        message = (
            f"{emoji} <b>Daily Summary</b>\n\n"
            f"Total Trades: <code>{total_trades}</code>\n"
            f"Profitable: <code>{profitable_trades}</code>\n"
            f"Win Rate: <code>{win_rate:.1f}%</code>\n"
            f"Total PnL: <code>{pnl_sign}${total_pnl:.2f}</code>\n"
            f"Current Balance: <code>${balance:.2f}</code>"
        )
        return self._send_message(message)

    def notify_bot_started(self, symbols: list, testnet: bool = False):
        """Send notification when bot starts."""
        env = "TESTNET" if testnet else "MAINNET"
        symbols_str = ", ".join([f"<code>{s[0]} ({s[1]})</code>" for s in symbols])

        message = (
            f"🚀 <b>Bot Started</b>\n\n"
            f"Environment: <b>{env}</b>\n"
            f"Symbols: {symbols_str}\n"
            f"Status: <b>Running</b>"
        )
        return self._send_message(message)

    def notify_bot_stopped(self, reason: str = "Manual stop"):
        """Send notification when bot stops."""
        message = (
            f"🛑 <b>Bot Stopped</b>\n\n"
            f"Reason: {reason}"
        )
        return self._send_message(message)
