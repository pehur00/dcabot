"""
AI Bot Routes for Flask App
Handles AI trading bot creation, management, and dashboard
"""

from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
import logging

logger = logging.getLogger(__name__)


def register_ai_bot_routes(app):
    """Register all AI bot routes with Flask app"""

    # ============================================================================
    # AI Bot Routes
    # ============================================================================

    @app.route('/ai-bots')
    @login_required
    def ai_bots_dashboard():
        """AI Bots Dashboard - Real-time balance from Phemex"""
        from saas import database as db
        from saas.security import decrypt_api_key
        from clients.PhemexClient import PhemexClient

        try:
            # Get user's AI bots
            with db.get_db() as conn:
                from psycopg2.extras import RealDictCursor
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                cursor.execute("""
                    SELECT
                        ab.*,
                        amc.name as model_name,
                        amc.provider,
                        amc.logo_url
                    FROM ai_bots ab
                    JOIN ai_model_configs amc ON ab.model_config_id = amc.id
                    WHERE ab.user_id = %s
                    ORDER BY ab.created_at DESC
                """, (current_user.id,))
                user_bots = cursor.fetchall()

            # Fetch real-time balance from Phemex for each bot
            for bot in user_bots:
                try:
                    # Decrypt API keys
                    exchange_api_key = decrypt_api_key(bot['exchange_api_key'])
                    exchange_api_secret = decrypt_api_key(bot['exchange_api_secret'])

                    # Connect to Phemex
                    testnet = bot.get('testnet', True)
                    phemex = PhemexClient(
                        api_key=exchange_api_key,
                        api_secret=exchange_api_secret,
                        logger=logger,
                        testnet=testnet
                    )

                    # Fetch real balance
                    balance_info = phemex.get_account_balance()
                    if balance_info and balance_info[0] is not None:
                        total_balance = float(balance_info[0])
                        used_balance = float(balance_info[1])
                        available_balance = total_balance - used_balance

                        # Calculate PnL from initial snapshot
                        # Handle None for old bots created before migration 016
                        initial_snapshot = float(bot.get('initial_balance_snapshot') or total_balance)
                        pnl_amount = total_balance - initial_snapshot
                        pnl_percentage = (pnl_amount / initial_snapshot * 100) if initial_snapshot > 0 else 0

                        # Get total unrealized PnL from open positions
                        total_upnl = 0.0
                        symbols = bot.get('symbols', [])
                        pos_side = "Long" if bot['side'] == "Long" else "Short"
                        for symbol in symbols:
                            position = phemex.get_position_for_symbol(symbol, pos_side)
                            if position and float(position.get('size', 0)) != 0:
                                total_upnl += float(position.get('unrealisedPnl', 0))

                        # Add to bot dict
                        bot['current_balance'] = total_balance
                        bot['used_balance'] = used_balance
                        bot['available_balance'] = available_balance
                        bot['pnl_amount'] = pnl_amount
                        bot['pnl_percentage'] = pnl_percentage
                        bot['total_upnl'] = total_upnl
                        bot['balance_with_upnl'] = total_balance + total_upnl
                        bot['balance_status'] = 'success'
                    else:
                        bot['current_balance'] = None
                        bot['balance_status'] = 'error'
                        bot['balance_error'] = 'Failed to fetch balance'

                except Exception as e:
                    logger.error(f"Failed to fetch balance for bot {bot['id']}: {e}")
                    bot['current_balance'] = None
                    bot['balance_status'] = 'error'
                    bot['balance_error'] = str(e)

            # Get leaderboard stats (bot-centric)
            leaderboard = db.get_ai_bot_leaderboard(current_user.id)

            return render_template(
                'ai_bots_dashboard.html',
                bots=user_bots,
                leaderboard=leaderboard
            )

        except Exception as e:
            logger.error(f"AI bots dashboard error: {e}", exc_info=True)
            flash('Error loading AI bots dashboard', 'error')
            return redirect(url_for('dashboard'))


    @app.route('/ai-bots/new', methods=['GET', 'POST'])
    @login_required
    def create_ai_bot():
        """Create new AI trading bot(s) - Multi-model selection"""
        from saas import database as db
        from saas.security import encrypt_api_key
        from saas.validation import validate_bot_name, validate_api_key, sanitize_string

        if request.method == 'GET':
            # Get available OpenRouter models (active only)
            available_models = db.get_all_ai_models()

            # Group by category for UI (budget, recommended, premium)
            models_by_category = {
                'budget': [],
                'recommended': [],
                'premium': []
            }

            for model in available_models:
                category = model.get('category', 'recommended')  # Default to recommended
                if category in models_by_category:
                    models_by_category[category].append(model)

            return render_template(
                'ai_bot_form.html',
                models_by_category=models_by_category
            )

        # POST: Create bot
        try:
            # Get form data
            bot_name = request.form.get('name', '').strip()
            risk_profile = request.form.get('risk_profile', 'moderate').strip()
            automatic_mode = request.form.get('automatic_mode') == 'on'
            testnet = request.form.get('testnet') == 'on'

            # Get allowed symbols (multi-select)
            allowed_symbols = request.form.getlist('allowed_symbols')
            if not allowed_symbols:
                flash('Please select at least one trading symbol', 'error')
                return redirect(url_for('create_ai_bot'))

            # Set limits based on risk profile
            risk_limits = {
                'conservative': {'max_leverage': 2, 'max_position_size': 0.03},
                'moderate': {'max_leverage': 5, 'max_position_size': 0.05},
                'aggressive': {'max_leverage': 10, 'max_position_size': 0.10},
            }

            if risk_profile == 'custom':
                max_leverage = int(request.form.get('max_leverage', 5))
                max_position_size = float(request.form.get('max_position_size', 0.05))
            else:
                max_leverage = risk_limits[risk_profile]['max_leverage']
                max_position_size = risk_limits[risk_profile]['max_position_size']

            # For backward compatibility, use first symbol as primary
            primary_symbol = allowed_symbols[0]
            side = 'Long'  # AI will decide this per trade

            # Exchange credentials
            phemex_api_key = request.form.get('phemex_api_key', '').strip()
            phemex_api_secret = request.form.get('phemex_api_secret', '').strip()

            # OpenRouter API key (unified for all models)
            openrouter_api_key = request.form.get('openrouter_api_key', '').strip()

            # Selected model (single selection from dropdown)
            model_id = request.form.get('selected_model')

            if not model_id:
                flash('Please select an AI model', 'error')
                return redirect(url_for('create_ai_bot'))

            # Validate inputs
            is_valid, error_msg = validate_bot_name(bot_name)
            if not is_valid:
                flash(error_msg, 'error')
                return redirect(url_for('create_ai_bot'))

            is_valid, error_msg = validate_api_key(phemex_api_key)
            if not is_valid:
                flash(f'Phemex API Key: {error_msg}', 'error')
                return redirect(url_for('create_ai_bot'))

            is_valid, error_msg = validate_api_key(phemex_api_secret)
            if not is_valid:
                flash(f'Phemex API Secret: {error_msg}', 'error')
                return redirect(url_for('create_ai_bot'))

            # Sanitize
            bot_name = sanitize_string(bot_name, max_length=100)
            primary_symbol = sanitize_string(primary_symbol, max_length=20)

            # Validate Phemex API keys by connecting and fetching balance
            from clients.PhemexClient import PhemexClient
            import logging
            logger = logging.getLogger(__name__)

            try:
                phemex_client = PhemexClient(
                    api_key=phemex_api_key,
                    api_secret=phemex_api_secret,
                    logger=logger,
                    testnet=testnet
                )

                # Fetch real balance from Phemex to validate credentials
                balance, used_balance = phemex_client.get_account_balance()

                if balance is None:
                    flash('Failed to connect to Phemex. Please check your API keys and permissions. Make sure API key has "Read" and "Trade" permissions.', 'error')
                    return redirect(url_for('create_ai_bot'))

                initial_balance_snapshot = balance

                flash(f'✓ Connected to Phemex {"Testnet" if testnet else "Mainnet"}: Balance = ${balance:.2f} USDT', 'success')

            except Exception as e:
                flash(f'Failed to connect to Phemex: {str(e)}. Please check your API credentials.', 'error')
                return redirect(url_for('create_ai_bot'))

            # Encrypt exchange credentials
            phemex_key_encrypted = encrypt_api_key(phemex_api_key)
            phemex_secret_encrypted = encrypt_api_key(phemex_api_secret)

            # Get model config
            model = db.get_model_config(model_id)
            if not model:
                flash('Selected AI model not found', 'error')
                return redirect(url_for('create_ai_bot'))

            # Validate OpenRouter API key
            if not openrouter_api_key:
                flash("Missing OpenRouter API key", 'error')
                return redirect(url_for('create_ai_bot'))

            is_valid, error_msg = validate_api_key(openrouter_api_key)
            if not is_valid:
                flash(f"OpenRouter API Key: {error_msg}", 'error')
                return redirect(url_for('create_ai_bot'))

            # Encrypt OpenRouter API key
            ai_api_key_encrypted = encrypt_api_key(openrouter_api_key)

            # Create bot
            with db.get_db() as conn:
                from psycopg2.extras import RealDictCursor
                cursor = conn.cursor(cursor_factory=RealDictCursor)

                # Convert symbols list to JSON for JSONB column
                import json
                symbols_json = json.dumps(allowed_symbols)

                cursor.execute("""
                    INSERT INTO ai_bots (
                        user_id, name, model_config_id,
                        symbol, side, max_leverage, max_position_size,
                        risk_profile, allowed_symbols, symbols,
                        is_active, automatic_mode,
                        exchange_api_key, exchange_api_secret, ai_api_key,
                        testnet, initial_balance_snapshot
                    ) VALUES (
                        %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s::jsonb,
                        %s, %s,
                        %s, %s, %s,
                        %s, %s
                    )
                    RETURNING id
                """, (
                    current_user.id, bot_name, model_id,
                    primary_symbol, side, max_leverage, max_position_size,
                    risk_profile, allowed_symbols, symbols_json,
                    True, automatic_mode,
                    phemex_key_encrypted, phemex_secret_encrypted, ai_api_key_encrypted,
                    testnet, initial_balance_snapshot
                ))

                result = cursor.fetchone()
                bot_id = result['id']

                conn.commit()

            flash(f'✓ AI bot created: {bot_name} | Model: {model["name"]} | Initial Balance: ${initial_balance_snapshot:.2f}', 'success')
            return redirect(url_for('ai_bots_dashboard'))

        except Exception as e:
            logger.error(f"Create AI bot error: {e}", exc_info=True)
            flash('Error creating AI bot(s)', 'error')
            return redirect(url_for('create_ai_bot'))


    @app.route('/api/ai-bots/chart-data')
    @login_required
    def ai_bots_chart_data():
        """API endpoint for multi-line chart data (uses ai_model_performance snapshots)"""
        from saas import database as db
        from datetime import datetime, timedelta
        from collections import defaultdict

        try:
            hours = int(request.args.get('hours', 72))
            bot_filter = request.args.get('bot', None)

            # Get balance history from ai_model_performance snapshots
            with db.get_db() as conn:
                from psycopg2.extras import RealDictCursor
                cursor = conn.cursor(cursor_factory=RealDictCursor)

                if bot_filter and bot_filter != 'all':
                    # Filter by bot
                    cursor.execute("""
                        SELECT
                            amp.ai_bot_id,
                            ab.id as bot_id,
                            ab.name as bot_name,
                            ab.model_config_id,
                            amc.name as model_name,
                            amc.provider,
                            amc.logo_url,
                            amp.balance,
                            amp.unrealised_pnl,
                            amp.snapshot_at,
                            ab.created_at as bot_created_at,
                            ab.initial_balance_snapshot
                        FROM ai_model_performance amp
                        JOIN ai_bots ab ON amp.ai_bot_id = ab.id
                        JOIN ai_model_configs amc ON ab.model_config_id = amc.id
                        WHERE ab.user_id = %s
                          AND ab.id = %s
                          AND amp.snapshot_at >= NOW() - INTERVAL '%s hours'
                        ORDER BY ab.id, amp.snapshot_at ASC
                    """, (current_user.id, bot_filter, hours))
                else:
                    # All bots
                    cursor.execute("""
                        SELECT
                            amp.ai_bot_id,
                            ab.id as bot_id,
                            ab.name as bot_name,
                            ab.model_config_id,
                            amc.name as model_name,
                            amc.provider,
                            amc.logo_url,
                            amp.balance,
                            amp.unrealised_pnl,
                            amp.snapshot_at,
                            ab.created_at as bot_created_at,
                            ab.initial_balance_snapshot
                        FROM ai_model_performance amp
                        JOIN ai_bots ab ON amp.ai_bot_id = ab.id
                        JOIN ai_model_configs amc ON ab.model_config_id = amc.id
                        WHERE ab.user_id = %s
                          AND amp.snapshot_at >= NOW() - INTERVAL '%s hours'
                        ORDER BY ab.id, amp.snapshot_at ASC
                    """, (current_user.id, hours))

                history = cursor.fetchall()

                # Get all user bots
                if bot_filter and bot_filter != 'all':
                    cursor.execute("""
                        SELECT
                            ab.id as bot_id,
                            ab.name as bot_name,
                            amc.id as model_config_id,
                            amc.name as model_name,
                            amc.provider,
                            amc.logo_url,
                            ab.created_at as bot_created_at,
                            ab.initial_balance_snapshot
                        FROM ai_bots ab
                        JOIN ai_model_configs amc ON ab.model_config_id = amc.id
                        WHERE ab.user_id = %s AND ab.id = %s AND ab.is_active = true
                    """, (current_user.id, bot_filter))
                else:
                    cursor.execute("""
                        SELECT
                            ab.id as bot_id,
                            ab.name as bot_name,
                            amc.id as model_config_id,
                            amc.name as model_name,
                            amc.provider,
                            amc.logo_url,
                            ab.created_at as bot_created_at,
                            ab.initial_balance_snapshot
                        FROM ai_bots ab
                        JOIN ai_model_configs amc ON ab.model_config_id = amc.id
                        WHERE ab.user_id = %s AND ab.is_active = true
                    """, (current_user.id,))

                all_bots = cursor.fetchall()

            # Group balance history by bot
            balance_by_bot = defaultdict(list)
            for row in history:
                bot_id = row['ai_bot_id']
                balance = float(row['balance']) if row['balance'] else 0.0
                unrealised_pnl = float(row.get('unrealised_pnl', 0)) if row.get('unrealised_pnl') else 0.0
                balance_by_bot[bot_id].append({
                    'timestamp': row['snapshot_at'],
                    'balance': balance,
                    'unrealised_pnl': unrealised_pnl,
                    'balance_with_upnl': balance + unrealised_pnl
                })

            # Build datasets with synchronized timeline - one line per bot
            datasets = []
            now = datetime.now()
            start_time = now - timedelta(hours=hours)

            for bot in all_bots:
                bot_id = bot['bot_id']
                history_data = balance_by_bot.get(bot_id, [])

                # Create synchronized data points
                data_points = []

                # Add initial point (from initial_balance_snapshot)
                # Always show at least the initial balance, even if no executor runs yet
                initial_balance = float(bot['initial_balance_snapshot']) if bot['initial_balance_snapshot'] else 100.0
                bot_created = bot['bot_created_at']
                first_timestamp = max(bot_created, start_time)
                data_points.append({
                    'x': first_timestamp.isoformat(),
                    'y': initial_balance
                })

                # Add all historical points from performance snapshots (if any)
                if history_data:
                    for point in history_data:
                        data_points.append({
                            'x': point['timestamp'].isoformat(),
                            'y': point['balance_with_upnl']  # Plot balance + unrealised PnL
                        })

                datasets.append({
                    'label': bot['bot_name'],  # Use bot name instead of model name
                    'bot_id': bot_id,
                    'bot_name': bot['bot_name'],
                    'model_name': bot['model_name'],
                    'provider': bot['provider'],
                    'logo_url': bot['logo_url'],
                    'data': data_points
                })

            return jsonify({
                'success': True,
                'datasets': datasets
            })

        except Exception as e:
            logger.error(f"Chart data error: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500


    @app.route('/api/ai-bots/decisions')
    @login_required
    def ai_bots_decisions():
        """API endpoint for portfolio-level AI decisions log"""
        from saas import database as db

        try:
            bot_filter = request.args.get('bot', None)
            limit = int(request.args.get('limit', 50))

            with db.get_db() as conn:
                from psycopg2.extras import RealDictCursor
                cursor = conn.cursor(cursor_factory=RealDictCursor)

                # Query portfolio-level decisions
                if bot_filter and bot_filter != 'all':
                    # Filter by bot
                    cursor.execute("""
                        SELECT
                            pd.id,
                            pd.ai_bot_id,
                            ab.name as bot_name,
                            amc.name as model_name,
                            amc.provider,
                            amc.logo_url,
                            pd.portfolio_action,
                            pd.risk_assessment,
                            pd.reasoning,
                            pd.total_balance,
                            pd.available_balance,
                            pd.used_balance,
                            pd.input_tokens,
                            pd.output_tokens,
                            pd.api_cost,
                            pd.response_time_ms,
                            pd.created_at
                        FROM ai_portfolio_decisions pd
                        JOIN ai_bots ab ON pd.ai_bot_id = ab.id
                        JOIN ai_model_configs amc ON ab.model_config_id = amc.id
                        WHERE ab.user_id = %s
                          AND ab.id = %s
                        ORDER BY pd.created_at DESC
                        LIMIT %s
                    """, (current_user.id, bot_filter, limit))
                else:
                    # All models
                    cursor.execute("""
                        SELECT
                            pd.id,
                            pd.ai_bot_id,
                            ab.name as bot_name,
                            amc.name as model_name,
                            amc.provider,
                            amc.logo_url,
                            pd.portfolio_action,
                            pd.risk_assessment,
                            pd.reasoning,
                            pd.total_balance,
                            pd.available_balance,
                            pd.used_balance,
                            pd.input_tokens,
                            pd.output_tokens,
                            pd.api_cost,
                            pd.response_time_ms,
                            pd.created_at
                        FROM ai_portfolio_decisions pd
                        JOIN ai_bots ab ON pd.ai_bot_id = ab.id
                        JOIN ai_model_configs amc ON ab.model_config_id = amc.id
                        WHERE ab.user_id = %s
                        ORDER BY pd.created_at DESC
                        LIMIT %s
                    """, (current_user.id, limit))

                portfolio_decisions = cursor.fetchall()

                # For each portfolio decision, get the per-symbol decisions
                decisions_with_symbols = []
                for pd in portfolio_decisions:
                    cursor.execute("""
                        SELECT
                            symbol,
                            decision,
                            confidence,
                            reasoning,
                            action_taken,
                            skip_reason
                        FROM ai_decisions
                        WHERE portfolio_decision_id = %s
                        ORDER BY symbol
                    """, (str(pd['id']),))

                    symbol_decisions = cursor.fetchall()
                    decisions_with_symbols.append({
                        'portfolio': pd,
                        'symbols': symbol_decisions
                    })

                decisions = decisions_with_symbols

            # Format portfolio decisions for display
            formatted_decisions = []
            for item in decisions:
                pd = item['portfolio']
                symbols = item['symbols']

                # Format symbol decisions
                formatted_symbols = []
                for sym in symbols:
                    formatted_symbols.append({
                        'symbol': sym['symbol'],
                        'decision': sym['decision'],
                        'confidence': sym['confidence'],
                        'reasoning': sym['reasoning'],
                        'action_taken': sym['action_taken'],
                        'skip_reason': sym['skip_reason']
                    })

                formatted_decisions.append({
                    'id': pd['id'],
                    'bot_name': pd['bot_name'],
                    'model_name': pd['model_name'],
                    'provider': pd['provider'],
                    'logo_url': pd['logo_url'],
                    'portfolio_action': pd['portfolio_action'],
                    'risk_assessment': pd['risk_assessment'],
                    'reasoning': pd['reasoning'],
                    'total_balance': float(pd['total_balance']) if pd['total_balance'] else 0,
                    'available_balance': float(pd['available_balance']) if pd['available_balance'] else 0,
                    'used_balance': float(pd['used_balance']) if pd['used_balance'] else 0,
                    'symbols': formatted_symbols,
                    'api_cost': float(pd['api_cost']) if pd['api_cost'] else 0,
                    'response_time_ms': pd['response_time_ms'],
                    'created_at': pd['created_at'].isoformat()
                })

            return jsonify({
                'success': True,
                'decisions': formatted_decisions
            })

        except Exception as e:
            logger.error(f"Decisions log error: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500


    @app.route('/api/ai-bots/trades')
    @login_required
    def ai_bots_trades():
        """API endpoint for getting executed trades for user's AI bots"""
        from saas import database as db

        try:
            bot_filter = request.args.get('bot', None)
            limit = int(request.args.get('limit', 50))

            with db.get_db() as conn:
                from psycopg2.extras import RealDictCursor
                cursor = conn.cursor(cursor_factory=RealDictCursor)

                if bot_filter and bot_filter != 'all':
                    # Filter by bot
                    cursor.execute("""
                        SELECT
                            t.id,
                            t.ai_bot_id,
                            ab.name as bot_name,
                            amc.name as model_name,
                            amc.provider,
                            amc.logo_url,
                            t.symbol,
                            t.side,
                            t.action,
                            t.quantity,
                            t.price,
                            t.position_value_usd,
                            t.leverage,
                            t.reduce_only,
                            t.trading_fee,
                            t.order_id,
                            t.balance_before,
                            t.balance_after,
                            t.details,
                            t.executed_at
                        FROM ai_trades t
                        JOIN ai_bots ab ON t.ai_bot_id = ab.id
                        JOIN ai_model_configs amc ON ab.model_config_id = amc.id
                        WHERE ab.user_id = %s
                          AND ab.id = %s
                        ORDER BY t.executed_at DESC
                        LIMIT %s
                    """, (current_user.id, bot_filter, limit))
                else:
                    # All bots
                    cursor.execute("""
                        SELECT
                            t.id,
                            t.ai_bot_id,
                            ab.name as bot_name,
                            amc.name as model_name,
                            amc.provider,
                            amc.logo_url,
                            t.symbol,
                            t.side,
                            t.action,
                            t.quantity,
                            t.price,
                            t.position_value_usd,
                            t.leverage,
                            t.reduce_only,
                            t.trading_fee,
                            t.order_id,
                            t.balance_before,
                            t.balance_after,
                            t.details,
                            t.executed_at
                        FROM ai_trades t
                        JOIN ai_bots ab ON t.ai_bot_id = ab.id
                        JOIN ai_model_configs amc ON ab.model_config_id = amc.id
                        WHERE ab.user_id = %s
                        ORDER BY t.executed_at DESC
                        LIMIT %s
                    """, (current_user.id, limit))

                trades = cursor.fetchall()

            # Format trades for JSON response
            formatted_trades = []
            for trade in trades:
                formatted_trades.append({
                    'id': trade['id'],
                    'bot_id': trade['ai_bot_id'],
                    'bot_name': trade['bot_name'],
                    'model_name': trade['model_name'],
                    'provider': trade['provider'],
                    'logo_url': trade['logo_url'],
                    'symbol': trade['symbol'],
                    'side': trade['side'],
                    'action': trade['action'],
                    'quantity': float(trade['quantity']),
                    'price': float(trade['price']),
                    'position_value_usd': float(trade['position_value_usd']) if trade['position_value_usd'] else 0,
                    'leverage': trade['leverage'],
                    'reduce_only': trade['reduce_only'],
                    'trading_fee': float(trade['trading_fee']) if trade['trading_fee'] else 0,
                    'order_id': trade['order_id'],
                    'balance_before': float(trade['balance_before']) if trade['balance_before'] else 0,
                    'balance_after': float(trade['balance_after']) if trade['balance_after'] else 0,
                    'details': trade['details'],  # JSON string with entry/exit prices and P&L
                    'executed_at': trade['executed_at'].isoformat()
                })

            return jsonify({
                'success': True,
                'trades': formatted_trades
            })

        except Exception as e:
            logger.error(f"Trades API error: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500


    @app.route('/api/ai-bots/positions')
    @login_required
    def ai_bots_positions():
        """API endpoint for getting all open positions across user's AI bots"""
        from saas import database as db
        from clients.PhemexClient import PhemexClient
        from saas.security import decrypt_api_key

        try:
            model_filter = request.args.get('model', None)

            with db.get_db() as conn:
                from psycopg2.extras import RealDictCursor
                cursor = conn.cursor(cursor_factory=RealDictCursor)

                # Get all active user bots with their API keys
                if model_filter and model_filter != 'all':
                    cursor.execute("""
                        SELECT
                            ab.id,
                            ab.name,
                            ab.symbols,
                            ab.side,
                            ab.exchange_api_key,
                            ab.exchange_api_secret,
                            ab.testnet,
                            amc.name as model_name,
                            amc.logo_url
                        FROM ai_bots ab
                        JOIN ai_model_configs amc ON ab.model_config_id = amc.id
                        WHERE ab.user_id = %s
                          AND ab.is_active = true
                          AND amc.id = %s
                    """, (current_user.id, model_filter))
                else:
                    cursor.execute("""
                        SELECT
                            ab.id,
                            ab.name,
                            ab.symbols,
                            ab.side,
                            ab.exchange_api_key,
                            ab.exchange_api_secret,
                            ab.testnet,
                            amc.name as model_name,
                            amc.logo_url
                        FROM ai_bots ab
                        JOIN ai_model_configs amc ON ab.model_config_id = amc.id
                        WHERE ab.user_id = %s AND ab.is_active = true
                    """, (current_user.id,))

                bots = cursor.fetchall()

                bot_groups = []

                # For each bot, get positions from Phemex
                for bot in bots:
                    try:
                        # Decrypt API keys
                        api_key = decrypt_api_key(bot['exchange_api_key'])
                        api_secret = decrypt_api_key(bot['exchange_api_secret'])

                        # Create Phemex client
                        client = PhemexClient(
                            api_key=api_key,
                            api_secret=api_secret,
                            testnet=bot['testnet'],
                            logger=logger
                        )

                        # Get account balance
                        balance_info = client.get_account_balance()
                        total_balance = float(balance_info[0]) if balance_info and balance_info[0] else 0
                        used_balance = float(balance_info[1]) if balance_info and balance_info[1] else 0
                        available_balance = total_balance - used_balance

                        # Get positions for each symbol
                        symbols = bot['symbols'] if bot['symbols'] else []
                        pos_side = "Long" if bot['side'] == "Long" else "Short"

                        positions = []
                        total_upnl = 0.0

                        for symbol in symbols:
                            position = client.get_position_for_symbol(symbol, pos_side)

                            if position and float(position.get('size', 0)) != 0:
                                # Position exists and has size
                                size = abs(float(position.get('size', 0)))
                                entry_price = float(position.get('avgEntryPriceRp', 0))
                                mark_price = float(position.get('markPriceRp', 0))
                                unrealised_pnl = float(position.get('unrealisedPnl', 0))
                                leverage = int(position.get('leverage', 1))
                                side = position.get('side', 'Unknown')
                                notional = size * mark_price  # Position value

                                total_upnl += unrealised_pnl

                                positions.append({
                                    'symbol': symbol,
                                    'side': side,
                                    'size': size,
                                    'leverage': leverage,
                                    'entry_price': entry_price,
                                    'mark_price': mark_price,
                                    'notional': notional,
                                    'unrealised_pnl': unrealised_pnl
                                })

                        # Only add bot group if it has positions
                        if positions:
                            bot_groups.append({
                                'bot_id': bot['id'],
                                'bot_name': bot['name'],
                                'model_name': bot['model_name'],
                                'logo_url': bot['logo_url'],
                                'testnet': bot['testnet'],
                                'total_upnl': total_upnl,
                                'available_balance': available_balance,
                                'positions': positions
                            })

                    except Exception as e:
                        logger.error(f"Error fetching positions for bot {bot['name']}: {e}")
                        continue

                return jsonify({
                    'success': True,
                    'bot_groups': bot_groups
                })

        except Exception as e:
            logger.error(f"Positions API error: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500


    @app.route('/ai-bots/<int:bot_id>/delete', methods=['POST'])
    @login_required
    def delete_ai_bot(bot_id):
        """Delete an AI bot and all associated data"""
        from saas import database as db

        try:
            with db.get_db() as conn:
                from psycopg2.extras import RealDictCursor
                cursor = conn.cursor(cursor_factory=RealDictCursor)

                # Verify bot belongs to current user
                cursor.execute("""
                    SELECT id, name FROM ai_bots
                    WHERE id = %s AND user_id = %s
                """, (bot_id, current_user.id))

                bot = cursor.fetchone()
                if not bot:
                    flash('Bot not found or access denied', 'error')
                    return redirect(url_for('ai_bots_dashboard'))

                bot_name = bot['name']

                # Delete bot (CASCADE will handle ai_decisions and ai_model_performance)
                cursor.execute("DELETE FROM ai_bots WHERE id = %s", (bot_id,))

                conn.commit()

                flash(f'Bot "{bot_name}" deleted successfully', 'success')
                return redirect(url_for('ai_bots_dashboard'))

        except Exception as e:
            logger.error(f"Delete AI bot error: {e}", exc_info=True)
            flash('Error deleting bot', 'error')
            return redirect(url_for('ai_bots_dashboard'))


    @app.route('/ai-bots/<int:bot_id>/toggle', methods=['POST'])
    @login_required
    def toggle_ai_bot(bot_id):
        """Toggle AI bot active status (pause/resume)"""
        from saas import database as db

        try:
            with db.get_db() as conn:
                from psycopg2.extras import RealDictCursor
                cursor = conn.cursor(cursor_factory=RealDictCursor)

                # Verify bot belongs to current user
                cursor.execute("""
                    SELECT id, name, is_active FROM ai_bots
                    WHERE id = %s AND user_id = %s
                """, (bot_id, current_user.id))

                bot = cursor.fetchone()
                if not bot:
                    flash('Bot not found or access denied', 'error')
                    return redirect(url_for('ai_bots_dashboard'))

                # Toggle status
                new_status = not bot['is_active']
                cursor.execute("""
                    UPDATE ai_bots
                    SET is_active = %s
                    WHERE id = %s
                """, (new_status, bot_id))

                conn.commit()

                status_text = 'resumed' if new_status else 'paused'
                flash(f'Bot "{bot["name"]}" {status_text}', 'success')
                return redirect(url_for('ai_bots_dashboard'))

        except Exception as e:
            logger.error(f"Toggle AI bot error: {e}", exc_info=True)
            flash('Error toggling bot status', 'error')
            return redirect(url_for('ai_bots_dashboard'))

    @app.route('/ai-bots/<int:bot_id>/reset', methods=['POST'])
    @login_required
    def reset_ai_bot(bot_id):
        """
        Reset AI bot historical data - clears all decisions, trades, and performance history
        BUT keeps bot configuration and Phemex positions/balance intact
        """
        from saas import database as db

        try:
            with db.get_db() as conn:
                from psycopg2.extras import RealDictCursor
                cursor = conn.cursor(cursor_factory=RealDictCursor)

                # Verify bot belongs to user
                cursor.execute("""
                    SELECT id, name FROM ai_bots
                    WHERE id = %s AND user_id = %s
                """, (bot_id, current_user.id))

                bot = cursor.fetchone()
                if not bot:
                    flash('Bot not found or access denied', 'error')
                    return redirect(url_for('ai_bots_dashboard'))

                # Delete historical data (keeps bot configuration)
                cursor.execute("DELETE FROM ai_trades WHERE ai_bot_id = %s", (bot_id,))
                trades_deleted = cursor.rowcount

                cursor.execute("DELETE FROM ai_decisions WHERE ai_bot_id = %s", (bot_id,))
                decisions_deleted = cursor.rowcount

                cursor.execute("DELETE FROM ai_bot_balance_history WHERE ai_bot_id = %s", (bot_id,))
                balance_history_deleted = cursor.rowcount

                cursor.execute("DELETE FROM ai_model_performance WHERE ai_bot_id = %s", (bot_id,))
                perf_deleted = cursor.rowcount

                # Reset virtual balance to 1000 (deprecated, but kept for consistency)
                cursor.execute("""
                    UPDATE ai_bots
                    SET virtual_balance = 1000.0,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (bot_id,))

                conn.commit()

                logger.info(f"Reset bot #{bot_id}: {trades_deleted} trades, {decisions_deleted} decisions, {balance_history_deleted} balance records, {perf_deleted} perf snapshots deleted")
                flash(f'Bot "{bot["name"]}" reset successfully. Historical data cleared, configuration kept.', 'success')
                return redirect(url_for('ai_bots_dashboard'))

        except Exception as e:
            logger.error(f"Reset AI bot error: {e}", exc_info=True)
            flash('Error resetting bot', 'error')
            return redirect(url_for('ai_bots_dashboard'))

    @app.route('/api/openrouter-usage')
    @login_required
    def get_openrouter_usage():
        """Get OpenRouter API usage and balance for current user's bots"""
        from saas import database as db
        from saas.security import decrypt_api_key
        import requests
        from datetime import datetime, timedelta

        try:
            # Get user's API key (from first active bot, or user settings if we add that)
            with db.get_db() as conn:
                from psycopg2.extras import RealDictCursor
                cursor = conn.cursor(cursor_factory=RealDictCursor)

                # Get first active bot's API key
                cursor.execute("""
                    SELECT ai_api_key
                    FROM ai_bots
                    WHERE user_id = %s AND is_active = true
                    LIMIT 1
                """, (current_user.id,))
                bot = cursor.fetchone()

                if not bot or not bot['ai_api_key']:
                    return jsonify({'error': 'No active bot with OpenRouter API key found'}), 404

                # Decrypt API key
                api_key = decrypt_api_key(bot['ai_api_key'])

                # Fetch balance from OpenRouter
                headers = {
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json'
                }

                # OpenRouter credits endpoint (correct endpoint per docs)
                response = requests.get(
                    'https://openrouter.ai/api/v1/credits',
                    headers=headers,
                    timeout=10
                )

                if response.status_code != 200:
                    logger.error(f"OpenRouter API error: {response.status_code} - {response.text}")
                    return jsonify({'error': 'Failed to fetch OpenRouter credits'}), 500

                response_json = response.json()
                logger.info(f"OpenRouter credits API response: {response_json}")  # Debug logging

                # Parse credits response
                credits_data = response_json.get('data', {})
                total_credits = float(credits_data.get('total_credits', 0))
                used_credits = float(credits_data.get('used_credits', 0))
                remaining_credits = float(credits_data.get('remaining_credits', 0) or (total_credits - used_credits))

                # Calculate usage stats from recent decisions
                cursor.execute("""
                    SELECT
                        COUNT(*) as total_calls,
                        SUM(api_cost) as total_cost,
                        SUM(input_tokens + output_tokens) as total_tokens,
                        AVG(api_cost) as avg_cost_per_call
                    FROM ai_portfolio_decisions
                    WHERE ai_bot_id IN (
                        SELECT id FROM ai_bots WHERE user_id = %s
                    )
                    AND decision_time >= NOW() - INTERVAL '7 days'
                """, (current_user.id,))
                usage_stats = cursor.fetchone()

                # Calculate daily average
                daily_avg_cost = (usage_stats['total_cost'] or 0) / 7

                # Get last execution cost
                cursor.execute("""
                    SELECT api_cost, input_tokens, output_tokens, decision_time
                    FROM ai_portfolio_decisions
                    WHERE ai_bot_id IN (
                        SELECT id FROM ai_bots WHERE user_id = %s
                    )
                    ORDER BY decision_time DESC
                    LIMIT 1
                """, (current_user.id,))
                last_execution = cursor.fetchone()

                # Calculate estimated days remaining
                estimated_days = (remaining_credits / daily_avg_cost) if daily_avg_cost > 0 else float('inf')

                return jsonify({
                    'credits': {
                        'total': total_credits,
                        'used': used_credits,
                        'remaining': remaining_credits
                    },
                    'bot_usage': {
                        'total_calls_7d': usage_stats['total_calls'] or 0,
                        'total_cost_7d': float(usage_stats['total_cost'] or 0),
                        'total_tokens_7d': int(usage_stats['total_tokens'] or 0),
                        'avg_cost_per_call': float(usage_stats['avg_cost_per_call'] or 0),
                        'daily_avg_cost': daily_avg_cost
                    },
                    'last_execution': {
                        'cost': float(last_execution['api_cost']) if last_execution else 0,
                        'tokens': int((last_execution['input_tokens'] or 0) + (last_execution['output_tokens'] or 0)) if last_execution else 0,
                        'time': last_execution['decision_time'].isoformat() if last_execution else None
                    },
                    'estimated_days_remaining': estimated_days if estimated_days != float('inf') else None
                })

        except Exception as e:
            logger.error(f"Error fetching OpenRouter usage: {e}", exc_info=True)
            return jsonify({'error': str(e)}), 500
