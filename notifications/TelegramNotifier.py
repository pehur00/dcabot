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

    def notify_position_update(self, action: str, symbol: str, side: str, pos_side: str,
                               qty: float, price: float, balance: float,
                               position_size: float = None, position_value: float = None,
                               position_pct: float = None, pnl: float = None,
                               pnl_pct: float = None, reason: str = None):
        """
        Unified notification for all position updates.

        Args:
            action: Action type - "OPENED", "ADDED", "REDUCED", "CLOSED"
            symbol: Trading symbol
            side: Buy/Sell
            pos_side: Long/Short
            qty: Quantity of this action
            price: Execution price
            balance: Total account balance
            position_size: Total position size after action (in coins/tokens)
            position_value: Total position value after action (in USD)
            position_pct: Position as % of total balance
            pnl: Profit/Loss (for REDUCED/CLOSED)
            pnl_pct: PnL percentage (for REDUCED/CLOSED)
            reason: Reason for action (for REDUCED/CLOSED)
        """
        # Emoji and color based on action
        action_emojis = {
            "OPENED": "🟢",
            "ADDED": "🔵",
            "REDUCED": "🟡",
            "CLOSED": "🔴" if (pnl is not None and pnl < 0) else "🟢"
        }
        emoji = action_emojis.get(action, "⚪")

        # Build message header
        message = f"{emoji} <b>Position {action}</b>\n\n"
        message += f"Symbol: <code>{symbol}</code>\n"
        message += f"Side: <b>{side}</b> ({pos_side})\n"
        message += f"Action Qty: <code>{qty:.4f}</code>\n"
        message += f"Price: <code>${price:.4f}</code>\n"

        # Add position details if available
        if position_size is not None:
            message += f"\n<b>Position Status:</b>\n"
            message += f"Total Size: <code>{position_size:.4f}</code> {symbol.replace('USDT', '')}\n"

        if position_value is not None:
            message += f"Position Value: <code>${position_value:.2f}</code>\n"

        if position_pct is not None:
            message += f"% of Balance: <code>{position_pct:.2f}%</code>\n"

        # Add PnL for REDUCED/CLOSED actions
        if pnl is not None and action in ["REDUCED", "CLOSED"]:
            pnl_sign = "+" if pnl > 0 else ""
            message += f"\n<b>PnL:</b> <code>{pnl_sign}${pnl:.2f}</code>"
            if pnl_pct is not None:
                message += f" ({pnl_sign}{pnl_pct:.2f}%)"
            message += "\n"

        # Add reason if provided
        if reason:
            message += f"\nReason: {reason}"

        # Add balance
        message += f"\n<b>Balance:</b> <code>${balance:.2f}</code>"

        return self._send_message(message)

    def notify_position_opened(self, symbol: str, side: str, pos_side: str, qty: float, price: float,
                               balance: float, position_size_pct: float):
        """Deprecated: Use notify_position_update() instead. Kept for backwards compatibility."""
        return self.notify_position_update(
            action="OPENED",
            symbol=symbol,
            side=side,
            pos_side=pos_side,
            qty=qty,
            price=price,
            balance=balance,
            position_pct=position_size_pct
        )

    def notify_position_closed(self, symbol: str, pos_side: str, qty: float, price: float,
                               pnl: float, pnl_pct: float, reason: str):
        """Deprecated: Use notify_position_update() instead. Kept for backwards compatibility."""
        side = "Buy" if pos_side == "Long" else "Sell"
        return self.notify_position_update(
            action="CLOSED",
            symbol=symbol,
            side=side,
            pos_side=pos_side,
            qty=qty,
            price=price,
            balance=0,  # Not available in old method
            pnl=pnl,
            pnl_pct=pnl_pct,
            reason=reason
        )

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

    def notify_decline_velocity_alert(self, symbol: str, decline_type: str,
                                      velocity_score: float, roc_5: float,
                                      smoothness_ratio: float, action: str):
        """Send notification when dangerous decline velocity is detected."""
        # Emoji based on severity
        emoji_map = {
            'CRASH': '🔴',
            'FAST_DECLINE': '🟠',
            'MODERATE_DECLINE': '🟡',
            'SLOW_DECLINE': '🟢'
        }
        emoji = emoji_map.get(decline_type, '⚪')

        message = (
            f"{emoji} <b>DECLINE VELOCITY ALERT</b>\n\n"
            f"Symbol: <code>{symbol}</code>\n"
            f"Type: <b>{decline_type}</b>\n"
            f"Velocity Score: <code>{velocity_score:.1f}/100</code>\n"
            f"5-Period ROC: <code>{roc_5:.2f}%</code>\n"
            f"Smoothness Ratio: <code>{smoothness_ratio:.2f}</code>\n"
            f"Action: <b>{action}</b>\n\n"
            f"ℹ️ Slow declines are safer for averaging down.\n"
            f"Fast crashes are dangerous - avoid adding."
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
