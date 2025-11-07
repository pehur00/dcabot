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

            # OPTIMIZATION: Collect all unique symbols across all bots
            unique_symbols = set()
            for bot in active_bots:
                allowed_symbols = bot.get('allowed_symbols', [bot['symbol']])
                unique_symbols.update(allowed_symbols)

            logger.info(f"Unique symbols to fetch: {', '.join(unique_symbols)}")

            # OPTIMIZATION: Fetch market data once per symbol (shared across all bots)
            market_data_cache = {}
            for symbol in unique_symbols:
                try:
                    logger.info(f"Fetching market data for {symbol}...")
                    market_data_cache[symbol] = self.market_data_fetcher.fetch_all_data(symbol)
                    logger.info(f"✓ {symbol}: ${market_data_cache[symbol]['current_price']:,.2f}")
                except Exception as e:
                    logger.error(f"Failed to fetch {symbol}: {e}")
                    market_data_cache[symbol] = None

            logger.info(f"Market data cached for {len(market_data_cache)} symbols\n")

            # Execute each bot with shared market data
            for bot in active_bots:
                try:
                    self.execute_bot(bot, market_data_cache)
                except Exception as e:
                    logger.error(f"Error executing AI bot {bot['id']}: {e}")
                    self.notify_error(bot, e)

            logger.info("=" * 60)
            logger.info("AI Bot Executor Completed")
            logger.info("=" * 60)

        except Exception as e:
            logger.error(f"Fatal error in AI bot executor: {e}")
            raise

    def execute_bot(self, bot, market_data_cache):
        """
        Execute single AI bot across all allowed symbols

        Args:
            bot: Bot record with model config (from get_active_ai_bots)
            market_data_cache: Dict of {symbol: market_data} pre-fetched data
        """
        bot_id = bot['id']
        model_name = bot['model_name']
        allowed_symbols = bot.get('allowed_symbols', [bot['symbol']])

        logger.info(f"\n{'='*60}")
        logger.info(f"Executing Bot #{bot_id}: {bot['name']}")
        logger.info(f"Model: {model_name} | Symbols: {', '.join(allowed_symbols)}")
        logger.info(f"{'='*60}")

        try:
            # Step 1: Decrypt API keys
            exchange_api_key = decrypt_api_key(bot['exchange_api_key'])
            exchange_api_secret = decrypt_api_key(bot['exchange_api_secret'])
            ai_api_key = decrypt_api_key(bot['ai_api_key'])

            # Step 2: Initialize clients
            # Check TESTNET environment variable like Martingale strategy does
            env_testnet = os.getenv('TESTNET', 'False').lower() in ('true', '1', 't')
            # Use environment variable if set, otherwise use database value (default to False for mainnet)
            use_testnet = env_testnet if os.getenv('TESTNET') else bot.get('testnet', False)
            phemex_client = PhemexClient(
                api_key=exchange_api_key,
                api_secret=exchange_api_secret,
                logger=logger,
                testnet=use_testnet
            )
            logger.info(f"Using {'TESTNET' if use_testnet else 'MAINNET'} for bot #{bot_id}")

            # Step 3: PORTFOLIO-LEVEL DECISION (one AI call for all symbols)
            logger.info(f"\n--- Making Portfolio Decision ---")

            # Build portfolio context (all symbols + positions)
            portfolio_context = self.build_portfolio_context(
                bot, allowed_symbols, market_data_cache, phemex_client
            )

            if not portfolio_context:
                logger.warning("Failed to build portfolio context - skipping bot")
                return

            # Make ONE AI decision for entire portfolio
            portfolio_decision = self.execute_portfolio_decision(
                bot, portfolio_context, phemex_client, ai_api_key
            )

            # Execute trades based on portfolio decision
            if portfolio_decision:
                self.execute_portfolio_trades(
                    bot, portfolio_decision, portfolio_context, phemex_client
                )

            # Step 4: Log total API cost (for tracking purposes only - not deducted from Phemex balance)
            total_api_cost = portfolio_decision.get('api_cost', 0) if portfolio_decision else 0
            if total_api_cost > 0:
                logger.info(f"\nTotal API cost: ${total_api_cost:.6f}")

            # Step 5: Update performance metrics
            self.update_performance_metrics(bot, phemex_client)

            logger.info(f"\n{'='*60}")
            logger.info(f"Bot #{bot_id} completed - Portfolio decision executed")
            logger.info(f"{'='*60}\n")

        except Exception as e:
            logger.error(f"Error executing bot #{bot_id}: {e}", exc_info=True)
            raise

    def build_portfolio_context(self, bot, symbols, market_data_cache, phemex_client):
        """
        Build comprehensive portfolio context for AI decision

        Returns:
            dict with balance, positions, market_data, symbol_constraints for all symbols
        """
        try:
            # Get account balance
            balance_info = phemex_client.get_account_balance()
            if balance_info is None or balance_info[0] is None:
                logger.error(f"Failed to fetch balance from Phemex for bot {bot['id']}")
                return None

            total_balance = float(balance_info[0])
            used_balance = float(balance_info[1])
            available_balance = total_balance - used_balance

            # Get positions and constraints for all symbols
            positions = {}
            market_data = {}
            symbol_constraints = {}

            pos_side = "Long" if bot['side'] == "Long" else "Short"

            for symbol in symbols:
                # Market data (from cache)
                md = market_data_cache.get(symbol)
                if md is None:
                    logger.warning(f"No market data for {symbol} - skipping")
                    continue

                market_data[symbol] = md

                # Current position
                current_position = phemex_client.get_position_for_symbol(symbol, pos_side)
                if current_position and float(current_position.get('size', 0)) != 0:
                    positions[symbol] = self.format_position(current_position)
                else:
                    positions[symbol] = None

                # Symbol constraints
                min_qty, max_qty, qty_step = phemex_client.define_instrument_info(symbol)
                symbol_constraints[symbol] = {
                    'min_order_qty': min_qty,
                    'max_order_qty': max_qty,
                    'qty_step': qty_step
                }

            portfolio_context = {
                'balance': {
                    'total': total_balance,
                    'used': used_balance,
                    'available': available_balance
                },
                'positions': positions,
                'market_data': market_data,
                'symbol_constraints': symbol_constraints,
                'symbols': list(market_data.keys())  # Only symbols with valid data
            }

            logger.info(f"Portfolio context: ${total_balance:.2f} total, {len(market_data)} symbols")
            return portfolio_context

        except Exception as e:
            logger.error(f"Error building portfolio context: {e}", exc_info=True)
            return None

    def execute_portfolio_decision(self, bot, portfolio_context, phemex_client, ai_api_key):
        """
        Make ONE AI decision for entire portfolio

        Returns:
            dict with portfolio_action, decisions per symbol, api_cost, etc.
        """
        try:
            # Prepare bot config
            bot_config = {
                'symbol': ','.join(portfolio_context['symbols']),  # All symbols
                'side': bot['side'],
                'leverage': bot['max_leverage'],
                'max_position_size': float(bot['max_position_size']),
                'risk_profile': bot.get('risk_profile', 'moderate'),
                'balance': portfolio_context['balance']['available']
            }

            # Prepare model config
            model_config = {
                'name': bot['model_name'],
                'provider': bot['model_provider'],
                'api_endpoint': bot['api_endpoint'],
                'model_identifier': bot['model_identifier'],
                'cost_per_1m_input': bot['cost_per_1m_input'],
                'cost_per_1m_output': bot['cost_per_1m_output']
            }

            # Call AI strategy with portfolio context
            strategy = AITradingStrategy(bot_config, model_config, ai_api_key)
            portfolio_decision = strategy.get_portfolio_decision(portfolio_context)

            logger.info(f"Portfolio Action: {portfolio_decision.get('portfolio_action', 'N/A')}")
            logger.info(f"Risk Assessment: {portfolio_decision.get('risk_assessment', 'N/A')}")

            # Log portfolio decision to database
            import uuid
            portfolio_decision_id = str(uuid.uuid4())  # Convert to string for PostgreSQL

            with db.get_db() as conn:
                from psycopg2.extras import RealDictCursor
                cursor = conn.cursor(cursor_factory=RealDictCursor)

                cursor.execute("""
                    INSERT INTO ai_portfolio_decisions (
                        id, ai_bot_id, decision_time,
                        total_balance, available_balance, used_balance,
                        portfolio_action, risk_assessment, reasoning,
                        input_tokens, output_tokens, api_cost, response_time_ms
                    ) VALUES (
                        %s::uuid, %s, NOW(),
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s, %s
                    )
                """, (
                    portfolio_decision_id, bot['id'],
                    portfolio_context['balance']['total'],
                    portfolio_context['balance']['available'],
                    portfolio_context['balance']['used'],
                    portfolio_decision.get('portfolio_action'),
                    portfolio_decision.get('risk_assessment'),
                    portfolio_decision.get('reasoning'),
                    portfolio_decision.get('input_tokens', 0),
                    portfolio_decision.get('output_tokens', 0),
                    portfolio_decision.get('api_cost', 0),
                    portfolio_decision.get('response_time_ms', 0)
                ))

                conn.commit()

            portfolio_decision['portfolio_decision_id'] = portfolio_decision_id
            return portfolio_decision

        except Exception as e:
            logger.error(f"Error executing portfolio decision: {e}", exc_info=True)
            return None

    def execute_portfolio_trades(self, bot, portfolio_decision, portfolio_context, phemex_client):
        """
        Execute trades for all symbols based on portfolio decision
        """
        decisions = portfolio_decision.get('decisions', {})
        portfolio_decision_id = portfolio_decision.get('portfolio_decision_id')

        for symbol, decision in decisions.items():
            try:
                logger.info(f"\n--- {symbol}: {decision['decision']} ---")

                # Get market data and constraints for this symbol
                market_data = portfolio_context['market_data'].get(symbol)
                if not market_data:
                    logger.warning(f"No market data for {symbol} - skipping")
                    continue

                # Add constraints to market data for this symbol
                market_data['symbol_constraints'] = portfolio_context['symbol_constraints'].get(symbol, {})

                # Map portfolio-level decisions to database-level decisions
                # Database only allows: BUY, SELL, HOLD
                # Portfolio level allows: BUY, SELL, HOLD, REDUCE, CLOSE
                decision_mapping = {
                    'BUY': 'BUY',
                    'SELL': 'SELL',
                    'HOLD': 'HOLD',
                    'REDUCE': 'SELL',  # REDUCE is a partial sell
                    'CLOSE': 'SELL'    # CLOSE is a full sell
                }
                db_decision = decision_mapping.get(decision['decision'], 'HOLD')

                # Map risk levels to database-allowed values
                # Database only allows: LOW, MEDIUM, HIGH
                # AI may return: LOW, MEDIUM-LOW, MEDIUM, MEDIUM-HIGH, HIGH
                risk_level_mapping = {
                    'LOW': 'LOW',
                    'MEDIUM-LOW': 'MEDIUM',
                    'MEDIUM': 'MEDIUM',
                    'MEDIUM-HIGH': 'MEDIUM',
                    'HIGH': 'HIGH'
                }
                raw_risk_level = decision.get('risk_level', 'MEDIUM')
                db_risk_level = risk_level_mapping.get(raw_risk_level, 'MEDIUM')

                # Log individual decision to database
                decision_data = {
                    'ai_bot_id': bot['id'],
                    'symbol': symbol,
                    'current_price': market_data['current_price'],
                    'ema20_1m': market_data.get('ema20_1m'),
                    'ema50_5m': market_data.get('ema50_5m'),
                    'ema100_1h': market_data.get('ema100_1h'),
                    'rsi_14': market_data.get('rsi'),
                    'volume_trend': market_data.get('volume_trend'),
                    'trend_description': market_data.get('trend'),
                    'decision': db_decision,  # Use mapped decision
                    'confidence': decision.get('confidence', 0),
                    'reasoning': decision.get('reasoning', ''),
                    'risk_level': db_risk_level,  # Use mapped risk level
                    'stop_loss': decision.get('stop_loss'),
                    'take_profit': decision.get('take_profit'),
                    'position_size_pct': decision.get('position_size_pct'),
                    'leverage_used': decision.get('leverage'),
                    'action_taken': 'PENDING',
                    'skip_reason': None,
                    'trade_id': None,
                    'input_tokens': 0,  # Portfolio-level tokens tracked separately
                    'output_tokens': 0,
                    'api_cost': 0,
                    'response_time_ms': 0
                }

                decision_id = db.log_ai_decision(decision_data)

                # Link to portfolio decision
                with db.get_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE ai_decisions
                        SET portfolio_decision_id = %s
                        WHERE id = %s
                    """, (portfolio_decision_id, decision_id))
                    conn.commit()

                # Execute trade
                action_result = self.execute_decision(
                    bot, symbol, decision, market_data, phemex_client, decision_id, portfolio_decision_id
                )
                logger.info(f"{symbol}: {action_result['action']} - {action_result['reason']}")

            except Exception as e:
                logger.error(f"Error executing trade for {symbol}: {e}", exc_info=True)

    # OLD METHOD (kept for reference during migration, remove later)
    def execute_symbol_decision_old(self, bot, symbol, market_data, phemex_client, ai_api_key):
        """
        Execute AI decision for a single symbol using pre-fetched market data

        Args:
            bot: Bot record
            symbol: Symbol to analyze
            market_data: Pre-fetched market data (shared across bots)
            phemex_client: Phemex client instance
            ai_api_key: Decrypted AI API key

        Returns:
            float: API cost for this decision
        """
        bot_id = bot['id']

        # Fetch symbol constraints (min qty, max qty, qty step)
        min_order_qty, max_order_qty, qty_step = phemex_client.define_instrument_info(symbol)
        if not qty_step or qty_step == 0:
            logger.error(f"Failed to fetch symbol constraints for {symbol}")
            return 0  # Return 0 API cost if we can't proceed

        # Add symbol constraints to market data so AI knows the limitations
        market_data['symbol_constraints'] = {
            'min_order_qty': min_order_qty,
            'max_order_qty': max_order_qty,
            'qty_step': qty_step
        }

        # Get current position (if any) - UNIQUE PER BOT
        pos_side = "Long" if bot['side'] == "Long" else "Short"
        current_position = phemex_client.get_position_for_symbol(symbol, pos_side)
        if current_position and float(current_position.get('size', 0)) != 0:
            market_data['current_position'] = self.format_position(current_position)
        else:
            market_data['current_position'] = "None"

        logger.info(f"Price: ${market_data['current_price']:,.2f} | RSI: {market_data['rsi']} | Trend: {market_data['trend']} | Position: {market_data['current_position']}")
        logger.info(f"Symbol constraints: min_qty={min_order_qty}, max_qty={max_order_qty}, step={qty_step}")

        # Get AI decision
        model_config = {
            'name': bot['model_name'],
            'provider': bot['model_provider'],
            'api_endpoint': bot['api_endpoint'],
            'model_identifier': bot['model_identifier'],
            'cost_per_1m_input': bot['cost_per_1m_input'],
            'cost_per_1m_output': bot['cost_per_1m_output']
        }

        bot_config = {
            'symbol': symbol,  # Use current symbol
            'side': bot['side'],
            'leverage': bot['max_leverage'],
            'max_position_size': float(bot['max_position_size']),
            'risk_profile': bot.get('risk_profile', 'moderate')
            # Note: Balance is fetched from Phemex in real-time during trade execution
        }

        strategy = AITradingStrategy(bot_config, model_config, ai_api_key)
        decision = strategy.get_trading_decision(market_data)

        logger.info(f"AI Decision: {decision['decision']} (confidence: {decision['confidence']}%)")
        logger.info(f"Reasoning: {decision['reasoning'][:150]}...")

        # Log decision to database
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
            'position_size_pct': decision.get('position_size_pct'),
            'leverage_used': decision.get('leverage'),
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

        # Execute trade (if applicable)
        action_result = self.execute_decision(
            bot, symbol, decision, market_data, phemex_client, decision_id
        )
        logger.info(f"Action: {action_result['action']} - {action_result['reason']}")

        return decision.get('api_cost', 0)

    def execute_decision(self, bot, symbol, decision, market_data, phemex_client, decision_id, portfolio_decision_id=None):
        """
        Execute trading decision (or skip with reason)

        Args:
            bot: Bot record
            symbol: Trading symbol
            decision: AI decision dict
            market_data: Market data with current price
            phemex_client: Phemex client instance
            decision_id: Decision ID from database
            portfolio_decision_id: Optional portfolio decision ID (for portfolio trading)

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

        # Execute the trade
        try:
            current_price = market_data['current_price']

            # Get AI's decisions for position size and leverage
            ai_position_size_pct = float(decision.get('position_size_pct', 0.03))  # Fallback to 3%
            ai_leverage = int(decision.get('leverage', 3))  # Fallback to 3x

            # Get REAL balance from Phemex
            balance_info = phemex_client.get_account_balance()
            if balance_info is None or balance_info[0] is None:
                logger.error(f"Failed to fetch balance from Phemex for bot {bot['id']}")
                db.update_ai_decision_action(
                    decision_id,
                    'SKIPPED',
                    skip_reason='Failed to fetch Phemex balance'
                )
                return {'action': 'SKIPPED', 'reason': 'Failed to fetch balance'}

            total_balance = float(balance_info[0])
            used_balance = float(balance_info[1])
            available_balance_raw = total_balance - used_balance

            # Apply 2% safety margin to prevent "cannot cover estimated loss" errors
            # Phemex requires buffer for fees (0.15%) + estimated losses + volatility
            available_balance = available_balance_raw * 0.98

            # Get symbol constraints from market_data (already fetched in process_bot_decision)
            symbol_constraints = market_data.get('symbol_constraints', {})
            min_order_qty = symbol_constraints.get('min_order_qty')
            max_order_qty = symbol_constraints.get('max_order_qty')
            qty_step = symbol_constraints.get('qty_step')

            # Special handling for CLOSE/REDUCE - check if position exists
            pos_side = "Long" if bot['side'] == "Long" else "Short"

            if decision['decision'] in ['CLOSE', 'REDUCE']:
                current_position = phemex_client.get_position_for_symbol(symbol, pos_side)

                if not current_position or float(current_position.get('size', 0)) == 0:
                    db.update_ai_decision_action(
                        decision_id,
                        'SKIPPED',
                        skip_reason='No position to close'
                    )
                    return {'action': 'SKIPPED', 'reason': 'No position to close'}

                position_size = abs(float(current_position.get('size', 0)))

            if decision['decision'] == 'CLOSE':
                # Use full position size for closing
                qty_raw = position_size
                import math
                qty = math.floor(qty_raw / qty_step) * qty_step
                position_value_usd = qty * current_price
                logger.info(f"CLOSE decision: Closing full position of {qty:.6f} {symbol}")
            else:
                # Calculate position value based on AI's decision
                # AI decides what % of AVAILABLE balance to risk
                position_value_usd = available_balance * ai_position_size_pct

                # Calculate quantity based on symbol price
                # For leverage trading, we use the position value directly
                qty_raw = position_value_usd / current_price

                # Round to step size and ensure it meets minimum
                import math
                qty = math.floor(qty_raw / qty_step) * qty_step

            # Ensure minimum order size
            if qty < min_order_qty:
                # Try to use minimum order size
                qty = min_order_qty
                position_value_usd = qty * current_price
                logger.warning(f"Order quantity {qty_raw:.6f} below minimum {min_order_qty}. Using minimum: {qty:.6f} (${position_value_usd:.2f})")

                # Check if we have enough balance for minimum order
                if position_value_usd > available_balance:
                    db.update_ai_decision_action(
                        decision_id,
                        'SKIPPED',
                        skip_reason=f'Insufficient balance for minimum order (need ${position_value_usd:.2f}, have ${available_balance:.2f})'
                    )
                    return {'action': 'SKIPPED', 'reason': f'Insufficient balance for minimum order size'}

            # Ensure maximum order size
            if qty > max_order_qty:
                qty = max_order_qty
                position_value_usd = qty * current_price
                logger.warning(f"Order quantity {qty_raw:.6f} exceeds maximum {max_order_qty}. Using maximum: {qty:.6f}")

            logger.info(f"AI Decision: Use {ai_position_size_pct*100}% of ${available_balance:.2f} available (${total_balance:.2f} total, {available_balance_raw:.2f} raw - 2% margin) = ${position_value_usd:.2f} with {ai_leverage}x leverage")
            logger.info(f"Calculated quantity: {qty_raw:.6f} → Rounded: {qty:.6f} (step={qty_step})")

            # Determine order side and position side
            reduce_only = False
            if decision['decision'] == 'BUY':
                order_side = "Buy"
                pos_side = "Long" if bot['side'] == "Long" else "Short"
            elif decision['decision'] == 'SELL':
                order_side = "Sell"
                pos_side = "Long" if bot['side'] == "Long" else "Short"
            elif decision['decision'] == 'REDUCE':
                # REDUCE means partially close position
                order_side = "Sell"  # Sell to reduce long position
                pos_side = "Long" if bot['side'] == "Long" else "Short"
                reduce_only = True
                logger.info("REDUCE decision: Will place reduce-only SELL order")
            elif decision['decision'] == 'CLOSE':
                # CLOSE means fully close position
                order_side = "Sell"  # Sell to close long position
                pos_side = "Long" if bot['side'] == "Long" else "Short"
                reduce_only = True
                logger.info("CLOSE decision: Will place reduce-only SELL order to fully close position")
            else:
                db.update_ai_decision_action(
                    decision_id,
                    'SKIPPED',
                    skip_reason=f"Unknown decision type: {decision['decision']}"
                )
                return {'action': 'SKIPPED', 'reason': f"Unknown decision: {decision['decision']}"}

            # Set leverage first (use AI's leverage decision)
            try:
                phemex_client.set_leverage(symbol, ai_leverage)
                logger.info(f"Set leverage to {ai_leverage}x for {symbol}")
            except Exception as e:
                logger.warning(f"Failed to set leverage (may already be set): {e}")

            logger.info(f"Placing {order_side} order: {symbol} | Qty: {qty:.4f} | Price: ${current_price:,.2f} | Value: ${position_value_usd:.2f}")

            # Place Market order for immediate execution
            order_response = phemex_client.place_order(
                symbol=symbol,
                qty=qty,
                price=current_price,  # Market price as reference
                side=order_side,
                order_type="Market",
                pos_side=pos_side,
                reduce_only=reduce_only  # Use reduce_only for REDUCE/CLOSE decisions
            )

            if order_response and 'data' in order_response:
                order_data = order_response['data']
                order_id = order_data.get('orderID', 'unknown')

                logger.info(f"✅ Order executed successfully: {order_id}")

                # Calculate trading fee for logging (0.075% maker, 0.15% taker - Market orders are taker)
                trading_fee = position_value_usd * 0.0015  # 0.15% taker fee
                logger.info(f"Trading fee (auto-deducted by Phemex): ${trading_fee:.4f}")

                # Update decision record with trade ID and EXECUTED status
                db.update_ai_decision_action(
                    decision_id,
                    'EXECUTED',
                    skip_reason=None,
                    trade_id=order_id
                )

                # Log trade to ai_trades table ONLY for FULL position closes (CLOSE only, not REDUCE)
                # This matches Phemex's "Closed PNL" tab behavior
                # Use Phemex's trade history API to get completed position data with accurate P&L
                if decision['decision'] == 'CLOSE':
                    try:
                        import time
                        # Wait briefly for trade to settle before querying history
                        time.sleep(2)

                        # Get recent trade history for this symbol
                        # Query last 5 minutes to catch the just-executed trade
                        current_time = int(time.time())
                        start_time = current_time - 300  # 5 minutes ago

                        trade_history = phemex_client.get_trade_history(
                            symbol=symbol,
                            start_time=start_time,
                            limit=50  # Get recent trades
                        )

                        # Find trades with closedPnl != 0 (completed positions)
                        # Match by order_id if possible, or use most recent
                        completed_trade = None
                        for trade in trade_history:
                            if trade.get('closedPnl', 0) != 0:
                                # Check if this is our order
                                if trade.get('orderId') == order_id or completed_trade is None:
                                    completed_trade = trade
                                    if trade.get('orderId') == order_id:
                                        break  # Found exact match

                        if completed_trade:
                            # Get balance after trade
                            balance_after_info = phemex_client.get_account_balance()
                            balance_after = float(balance_after_info[0]) if balance_after_info else total_balance

                            # Extract data from Phemex trade history
                            exit_price = completed_trade['price']
                            closed_pnl = completed_trade['closedPnl']  # Phemex's calculated P&L
                            actual_fee = completed_trade['fee']
                            actual_qty = completed_trade['qty']
                            trade_time = completed_trade['transactTime']

                            # Store in database
                            with db.get_db() as conn:
                                from psycopg2.extras import RealDictCursor
                                import json
                                cursor = conn.cursor(cursor_factory=RealDictCursor)

                                # Convert portfolio_decision_id to UUID string if it exists
                                portfolio_uuid = str(portfolio_decision_id) if portfolio_decision_id else None

                                # Calculate entry price from Phemex's closed P&L
                                # For Long: Entry = Exit - (P&L / Qty)
                                # For Short: Entry = Exit + (P&L / Qty)
                                if actual_qty > 0 and closed_pnl != 0:
                                    if bot['side'] == 'Long':
                                        entry_price = exit_price - (closed_pnl / actual_qty)
                                    else:  # Short
                                        entry_price = exit_price + (closed_pnl / actual_qty)
                                else:
                                    entry_price = exit_price  # Fallback if P&L is 0 (break-even)

                                # Build details JSON with Phemex data
                                details = {
                                    'entry_price': round(entry_price, 2),
                                    'exit_price': exit_price,
                                    'closed_pnl': closed_pnl,  # Phemex's calculated P&L
                                    'phemex_trade_id': completed_trade.get('tradeId'),
                                    'phemex_order_id': completed_trade.get('orderId'),
                                    'trade_time': trade_time,
                                    'action': completed_trade.get('action'),
                                    'side': completed_trade.get('side')
                                }

                                # Store completed position as a trade
                                cursor.execute("""
                                    INSERT INTO ai_trades (
                                        ai_bot_id, ai_decision_id, portfolio_decision_id,
                                        symbol, side, action, quantity, price,
                                        position_value_usd, leverage, reduce_only,
                                        trading_fee, order_id, order_type,
                                        balance_before, balance_after,
                                        details
                                    ) VALUES (
                                        %s, %s, %s::uuid,
                                        %s, %s, %s, %s, %s,
                                        %s, %s, %s,
                                        %s, %s, %s,
                                        %s, %s,
                                        %s
                                    )
                                """, (
                                    bot['id'], decision_id, portfolio_uuid,
                                    symbol, order_side, decision['decision'], actual_qty, exit_price,
                                    position_value_usd, ai_leverage, reduce_only,
                                    actual_fee, order_id, 'Market',
                                    total_balance, balance_after,
                                    json.dumps(details)
                                ))

                                conn.commit()
                                logger.info(f"✅ Completed trade logged from Phemex history: {symbol} exit=${exit_price:.2f} P&L=${closed_pnl:+.2f} (Phemex calculated)")

                        else:
                            logger.warning(f"No completed trade found in Phemex history for order {order_id}. Position may have been partially closed.")

                    except Exception as e:
                        logger.error(f"Failed to log completed trade from Phemex history: {e}", exc_info=True)
                        # Don't fail the entire execution if trade logging fails
                else:
                    # For BUY orders, don't log as completed trade
                    logger.info(f"Position opened/added - no completed trade logged yet")

                return {
                    'action': 'EXECUTED',
                    'reason': f"Order {order_id} placed successfully",
                    'order_id': order_id,
                    'qty': qty,
                    'price': current_price,
                    'fee': trading_fee
                }
            else:
                logger.error(f"Order failed: {order_response}")
                db.update_ai_decision_action(
                    decision_id,
                    'SKIPPED',
                    skip_reason=f"Order placement failed: {order_response}"
                )
                return {
                    'action': 'SKIPPED',
                    'reason': 'Order placement failed'
                }

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error executing trade: {error_msg}", exc_info=True)

            db.update_ai_decision_action(
                decision_id,
                'SKIPPED',
                skip_reason=f"Execution error: {error_msg}"
            )

            return {
                'action': 'SKIPPED',
                'reason': f"Error: {error_msg}"
            }

    def format_position(self, position):
        """Format position info for display"""
        side = position.get('side', 'Unknown')
        size = abs(float(position.get('size', 0)))
        entry_price = float(position.get('avgEntryPriceRp', 0))  # Fixed: Phemex uses "Rp" suffix
        current_price = float(position.get('markPriceRp', 0))  # Fixed: Phemex uses "Rp" suffix

        if entry_price > 0 and current_price > 0:
            pnl_pct = ((current_price - entry_price) / entry_price) * 100
            pnl_sign = "+" if pnl_pct >= 0 else ""
            return f"{side} {size} @ ${entry_price:,.2f} (PnL: {pnl_sign}{pnl_pct:.2f}%)"
        else:
            return f"{side} {size} @ ${entry_price:,.2f}"

    def update_performance_metrics(self, bot, phemex_client):
        """Update performance metrics for bot"""
        try:
            # Get account info (returns tuple: (total_balance, used_balance))
            balance_info = phemex_client.get_account_balance()

            # Skip metrics update if balance fetch failed (prevents saving $0 to DB)
            if balance_info is None or balance_info[0] is None:
                logger.warning(f"Skipping performance metrics update - failed to fetch balance for bot {bot['id']}")
                return

            balance = float(balance_info[0])

            # Get positions for ALL symbols in portfolio trading
            pos_side = "Long" if bot['side'] == "Long" else "Short"
            symbols = bot.get('symbols', [bot.get('symbol')])  # Support both single and multi-symbol bots

            open_positions = 0
            total_position_value = 0
            total_unrealised_pnl = 0.0

            for symbol in symbols:
                position = phemex_client.get_position_for_symbol(symbol, pos_side)
                if position and float(position.get('size', 0)) != 0:
                    open_positions += 1
                    position_value = abs(float(position.get('size', 0))) * float(position.get('markPriceRp', 0))
                    total_position_value += position_value
                    total_unrealised_pnl += float(position.get('unrealisedPnl', 0))

            # Get stats from ai_decisions
            stats = db.get_ai_bot_stats(bot['id'])

            # Extract values safely (stats is a dict/RealDictRow or None)
            total_api_cost = 0
            total_api_calls = 0
            if stats:
                total_api_cost = float(stats['total_api_cost']) if stats['total_api_cost'] else 0
                total_api_calls = int(stats['total_decisions']) if stats['total_decisions'] else 0

            # Calculate PnL from current Phemex balance vs initial snapshot
            # Handle None for old bots created before migration 016
            initial_balance_snapshot = float(bot.get('initial_balance_snapshot') or balance)
            pnl_amount = balance - initial_balance_snapshot
            pnl_percentage = (pnl_amount / initial_balance_snapshot * 100) if initial_balance_snapshot > 0 else 0

            # Get trade statistics from ai_decisions (executed trades only)
            trade_stats = db.get_ai_bot_trade_stats(bot['id'])
            total_trades = trade_stats.get('total_trades', 0) if trade_stats else 0
            winning_trades = trade_stats.get('winning_trades', 0) if trade_stats else 0
            losing_trades = trade_stats.get('losing_trades', 0) if trade_stats else 0
            win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

            performance_data = {
                'ai_bot_id': bot['id'],
                'model_config_id': bot['model_config_id'],
                'balance': balance,
                'pnl_percentage': pnl_percentage,
                'pnl_amount': pnl_amount,
                'total_trades': total_trades,
                'winning_trades': winning_trades,
                'losing_trades': losing_trades,
                'win_rate': win_rate,
                'open_positions': open_positions,
                'total_position_value': total_position_value,
                'total_api_cost': total_api_cost,
                'total_api_calls': total_api_calls,
                'unrealised_pnl': total_unrealised_pnl
            }

            db.save_ai_bot_performance(performance_data)
            logger.info(f"Performance metrics updated: Balance=${balance:,.2f}, PnL={pnl_percentage:+.2f}%, Trades={total_trades}, Open positions={open_positions}")

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
