#!/usr/bin/env python3
"""
AI Bot Executor
Executes all active AI trading bots (called by scheduler every 5 min)
"""

import os
import sys
import logging
from datetime import datetime
from decimal import Decimal

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from saas import database as db
from saas.security import decrypt_api_key
from data.market_data_fetcher import MarketDataFetcher
from strategies.AITradingStrategy import AITradingStrategy
from clients.PhemexClient import PhemexClient
from notifications.TelegramNotifier import TelegramNotifier

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AIBotExecutor:
    """Executes AI trading bots"""

    def __init__(self):
        self.market_data_fetcher = MarketDataFetcher()

    def execute_all_bots(self):
        """Execute all active AI bots"""
        logger.info("=" * 60)
        logger.info("AI Bot Executor Starting")
        logger.info("=" * 60)
        logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        try:
            # Get all active AI bots
            active_bots = db.get_active_ai_bots()

            if not active_bots:
                logger.info("No active AI bots found")
                return

            logger.info(f"Found {len(active_bots)} active AI bot(s)")

            # Execute each bot
            for bot in active_bots:
                try:
                    self.execute_bot(bot)
                except Exception as e:
                    logger.error(f"Error executing AI bot {bot['id']}: {e}")
                    self.notify_error(bot, e)

            logger.info("=" * 60)
            logger.info("AI Bot Executor Completed")
            logger.info("=" * 60)

        except Exception as e:
            logger.error(f"Fatal error in AI bot executor: {e}")
            raise

    def execute_bot(self, bot):
        """
        Execute single AI bot

        Args:
            bot: Bot record with model config (from get_active_ai_bots)
        """
        bot_id = bot['id']
        symbol = bot['symbol']
        model_name = bot['model_name']

        logger.info(f"\n{'='*60}")
        logger.info(f"Executing Bot #{bot_id}: {bot['name']}")
        logger.info(f"Model: {model_name} | Symbol: {symbol}")
        logger.info(f"{'='*60}")

        try:
            # Step 1: Decrypt API keys
            exchange_api_key = decrypt_api_key(bot['exchange_api_key'])
            exchange_api_secret = decrypt_api_key(bot['exchange_api_secret'])
            ai_api_key = decrypt_api_key(bot['ai_api_key'])

            # Step 2: Initialize clients
            phemex_client = PhemexClient(
                api_key=exchange_api_key,
                api_secret=exchange_api_secret,
                logger=logger,
                testnet=True  # TODO: Make this configurable per bot
            )

            # Step 3: Fetch market data
            logger.info(f"Fetching market data for {symbol}...")
            market_data = self.market_data_fetcher.fetch_all_data(symbol)

            # Get current position (if any)
            pos_side = "Long" if bot['side'] == "Long" else "Short"
            current_position = phemex_client.get_position_for_symbol(symbol, pos_side)
            if current_position and float(current_position.get('size', 0)) != 0:
                market_data['current_position'] = self.format_position(current_position)
            else:
                market_data['current_position'] = "None"

            logger.info(f"Price: ${market_data['current_price']:,.2f} | RSI: {market_data['rsi']} | Trend: {market_data['trend']}")

            # Step 4: Get AI decision
            model_config = {
                'name': bot['model_name'],
                'provider': bot['model_provider'],
                'api_endpoint': bot['api_endpoint'],
                'model_identifier': bot['model_identifier'],
                'cost_per_1m_input': bot['cost_per_1m_input'],
                'cost_per_1m_output': bot['cost_per_1m_output']
            }

            bot_config = {
                'symbol': bot['symbol'],
                'side': bot['side'],
                'leverage': bot['leverage'],
                'max_position_size': float(bot['max_position_size'])
            }

            strategy = AITradingStrategy(bot_config, model_config, ai_api_key)
            decision = strategy.get_trading_decision(market_data)

            logger.info(f"AI Decision: {decision['decision']} (confidence: {decision['confidence']}%)")
            logger.info(f"Reasoning: {decision['reasoning'][:100]}...")

            # Step 5: Log decision to database
            decision_data = {
                'ai_bot_id': bot_id,
                'symbol': symbol,
                'current_price': market_data['current_price'],
                'ema20_1m': market_data['ema20_1m'],
                'ema50_5m': market_data['ema50_5m'],
                'ema100_1h': market_data['ema100_1h'],
                'rsi_14': market_data['rsi'],
                'volume_trend': market_data['volume_trend'],
                'trend_description': market_data['trend'],
                'decision': decision['decision'],
                'confidence': decision['confidence'],
                'reasoning': decision['reasoning'],
                'risk_level': decision['risk_level'],
                'stop_loss': decision['stop_loss'],
                'take_profit': decision['take_profit'],
                'action_taken': 'PENDING',
                'skip_reason': None,
                'trade_id': None,
                'input_tokens': decision.get('input_tokens', 0),
                'output_tokens': decision.get('output_tokens', 0),
                'api_cost': decision.get('api_cost', 0),
                'response_time_ms': decision.get('response_time_ms', 0)
            }

            decision_id = db.log_ai_decision(decision_data)
            logger.info(f"Decision logged: ID={decision_id}")

            # Step 6: Execute trade (if applicable)
            action_result = self.execute_decision(
                bot, decision, phemex_client, decision_id
            )

            logger.info(f"Action: {action_result['action']} - {action_result['reason']}")

            # Step 7: Update performance metrics
            self.update_performance_metrics(bot, phemex_client)

            logger.info(f"Bot #{bot_id} execution complete\n")

        except Exception as e:
            logger.error(f"Error executing bot #{bot_id}: {e}", exc_info=True)
            raise

    def execute_decision(self, bot, decision, phemex_client, decision_id):
        """
        Execute trading decision (or skip with reason)

        Returns:
            Dict with 'action' and 'reason'
        """
        # Check if automatic mode is enabled
        if not bot['automatic_mode']:
            db.update_ai_decision_action(
                decision_id,
                'SKIPPED',
                skip_reason="Manual mode enabled"
            )
            return {'action': 'SKIPPED', 'reason': 'Manual mode enabled'}

        # Check confidence threshold
        confidence_threshold = 70  # TODO: Make this configurable
        if decision['confidence'] < confidence_threshold:
            db.update_ai_decision_action(
                decision_id,
                'SKIPPED',
                skip_reason=f"Low confidence: {decision['confidence']}% < {confidence_threshold}%"
            )
            return {
                'action': 'SKIPPED',
                'reason': f"Low confidence: {decision['confidence']}%"
            }

        # If decision is HOLD, skip
        if decision['decision'] == 'HOLD':
            db.update_ai_decision_action(
                decision_id,
                'SKIPPED',
                skip_reason="AI decision is HOLD"
            )
            return {'action': 'SKIPPED', 'reason': 'AI decision is HOLD'}

        # TODO: Execute trade via PhemexClient
        # For now, just log that we would execute
        logger.warning("Trade execution not yet implemented - would execute:")
        logger.warning(f"  Decision: {decision['decision']}")
        logger.warning(f"  Confidence: {decision['confidence']}%")
        logger.warning(f"  Stop Loss: ${decision['stop_loss']}")
        logger.warning(f"  Take Profit: ${decision['take_profit']}")

        db.update_ai_decision_action(
            decision_id,
            'SKIPPED',
            skip_reason="Trade execution not yet implemented"
        )

        return {
            'action': 'SKIPPED',
            'reason': 'Trade execution pending implementation'
        }

    def format_position(self, position):
        """Format position info for display"""
        side = position.get('side', 'Unknown')
        size = abs(float(position.get('size', 0)))
        entry_price = float(position.get('avgEntryPrice', 0))
        current_price = float(position.get('markPrice', 0))

        if entry_price > 0 and current_price > 0:
            pnl_pct = ((current_price - entry_price) / entry_price) * 100
            pnl_sign = "+" if pnl_pct >= 0 else ""
            return f"{side} {size} @ ${entry_price:,.2f} (PnL: {pnl_sign}{pnl_pct:.2f}%)"
        else:
            return f"{side} {size} @ ${entry_price:,.2f}"

    def update_performance_metrics(self, bot, phemex_client):
        """Update performance metrics for bot"""
        try:
            # Get account info
            balance_info = phemex_client.get_account_balance()
            balance = float(balance_info.get('accountBalance', 0)) if balance_info else 0

            # Get current position for this bot's symbol
            pos_side = "Long" if bot['side'] == "Long" else "Short"
            position = phemex_client.get_position_for_symbol(bot['symbol'], pos_side)

            open_positions = 1 if position and float(position.get('size', 0)) != 0 else 0
            total_position_value = 0
            if position and float(position.get('size', 0)) != 0:
                total_position_value = abs(float(position.get('size', 0))) * float(position.get('markPrice', 0))

            # Get stats from ai_decisions
            stats = db.get_ai_bot_stats(bot['id'])

            performance_data = {
                'ai_bot_id': bot['id'],
                'model_config_id': bot['model_config_id'],
                'balance': balance,
                'pnl_percentage': 0,  # TODO: Calculate from initial balance
                'pnl_amount': 0,  # TODO: Calculate
                'total_trades': 0,  # TODO: Count from trades table
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0,
                'open_positions': open_positions,
                'total_position_value': total_position_value,
                'total_api_cost': float(stats.get('total_api_cost', 0)) if stats else 0,
                'total_api_calls': int(stats.get('total_decisions', 0)) if stats else 0
            }

            db.save_ai_bot_performance(performance_data)
            logger.info(f"Performance metrics updated: Balance=${balance:,.2f}, Open positions={open_positions}")

        except Exception as e:
            logger.warning(f"Failed to update performance metrics: {e}")

    def notify_error(self, bot, error):
        """Send Telegram notification for errors"""
        try:
            # TODO: Get user's telegram credentials
            # TODO: Send error notification
            logger.info(f"Would send Telegram notification for bot {bot['id']} error")
        except Exception as e:
            logger.warning(f"Failed to send error notification: {e}")


def main():
    """Main entry point"""
    try:
        executor = AIBotExecutor()
        executor.execute_all_bots()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
