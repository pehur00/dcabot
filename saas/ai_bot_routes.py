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
        """AI Bots Dashboard - Multi-line chart and comparison"""
        from saas import database as db

        try:
            # Get user's AI bots
            with db.get_db() as conn:
                cursor = conn.cursor()
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

            # Get leaderboard stats
            leaderboard = db.get_ai_bot_leaderboard()

            # Get available models for filter
            available_models = db.get_all_ai_models()

            return render_template(
                'ai_bots_dashboard.html',
                bots=user_bots,
                leaderboard=leaderboard,
                available_models=available_models
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
            # Get available models
            available_models = db.get_all_ai_models()

            # Group by provider for UI
            models_by_provider = {}
            for model in available_models:
                provider = model['provider']
                if provider not in models_by_provider:
                    models_by_provider[provider] = []
                models_by_provider[provider].append(model)

            return render_template(
                'ai_bot_form.html',
                models_by_provider=models_by_provider
            )

        # POST: Create bot(s)
        try:
            # Get form data
            bot_name_base = request.form.get('name', '').strip()
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

            # AI model API keys (grouped by provider)
            # Support both old field names and new provider-based names
            api_keys_by_provider = {
                'z.ai': request.form.get('z.ai_api_key', '').strip() or request.form.get('zhipu_api_key', '').strip(),
                'deepseek': request.form.get('deepseek_api_key', '').strip(),
                'anthropic': request.form.get('anthropic_api_key', '').strip()
            }

            # Selected models (checkboxes)
            selected_model_ids = request.form.getlist('selected_models')

            if not selected_model_ids:
                flash('Please select at least one AI model', 'error')
                return redirect(url_for('create_ai_bot'))

            # Validate inputs
            is_valid, error_msg = validate_bot_name(bot_name_base)
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
            bot_name_base = sanitize_string(bot_name_base, max_length=100)
            primary_symbol = sanitize_string(primary_symbol, max_length=20)

            # Encrypt exchange credentials
            phemex_key_encrypted = encrypt_api_key(phemex_api_key)
            phemex_secret_encrypted = encrypt_api_key(phemex_api_secret)

            # Create bot for each selected model
            bots_created = []

            with db.get_db() as conn:
                cursor = conn.cursor()

                for model_id in selected_model_ids:
                    # Get model config
                    cursor.execute("""
                        SELECT * FROM ai_model_configs WHERE id = %s
                    """, (model_id,))
                    model = cursor.fetchone()

                    if not model:
                        continue

                    # Get API key for this model's provider
                    provider = model['provider']
                    ai_api_key = api_keys_by_provider.get(provider, '').strip()

                    if not ai_api_key:
                        flash(f"Missing API key for {provider}", 'warning')
                        continue

                    # Validate AI API key
                    is_valid, error_msg = validate_api_key(ai_api_key)
                    if not is_valid:
                        flash(f"{model['provider']} API Key: {error_msg}", 'error')
                        continue

                    # Encrypt AI API key
                    ai_api_key_encrypted = encrypt_api_key(ai_api_key)

                    # Create bot instance
                    bot_name = f"{bot_name_base} ({model['name']})"

                    cursor.execute("""
                        INSERT INTO ai_bots (
                            user_id, name, model_config_id,
                            symbol, side, max_leverage, max_position_size,
                            risk_profile, allowed_symbols,
                            is_active, automatic_mode,
                            exchange_api_key, exchange_api_secret, ai_api_key,
                            virtual_balance, initial_balance
                        ) VALUES (
                            %s, %s, %s,
                            %s, %s, %s, %s,
                            %s, %s,
                            %s, %s,
                            %s, %s, %s,
                            100.00, 100.00
                        )
                        RETURNING id
                    """, (
                        current_user.id, bot_name, model_id,
                        primary_symbol, side, max_leverage, max_position_size,
                        risk_profile, allowed_symbols,
                        True, automatic_mode,
                        phemex_key_encrypted, phemex_secret_encrypted, ai_api_key_encrypted
                    ))

                    bot_id = cursor.fetchone()[0]
                    bots_created.append((bot_id, bot_name))

                    # Log initial balance history
                    cursor.execute("""
                        INSERT INTO ai_bot_balance_history (
                            ai_bot_id, model_config_id, virtual_balance,
                            balance_change, change_reason
                        ) VALUES (%s, %s, 100.00, 100.00, 'initial')
                    """, (bot_id, model_id))

                conn.commit()

            if bots_created:
                bot_names = ", ".join([name for _, name in bots_created])
                flash(f'Created {len(bots_created)} AI bot(s): {bot_names}', 'success')
                return redirect(url_for('ai_bots_dashboard'))
            else:
                flash('No bots were created. Please check your inputs.', 'error')
                return redirect(url_for('create_ai_bot'))

        except Exception as e:
            logger.error(f"Create AI bot error: {e}", exc_info=True)
            flash('Error creating AI bot(s)', 'error')
            return redirect(url_for('create_ai_bot'))


    @app.route('/api/ai-bots/chart-data')
    @login_required
    def ai_bots_chart_data():
        """API endpoint for multi-line chart data"""
        from saas import database as db

        try:
            hours = int(request.args.get('hours', 72))
            model_filter = request.args.get('model', None)

            # Get balance history
            with db.get_db() as conn:
                cursor = conn.cursor()

                if model_filter and model_filter != 'all':
                    # Filter by model
                    cursor.execute("""
                        SELECT
                            bh.ai_bot_id,
                            bh.model_config_id,
                            amc.name as model_name,
                            amc.provider,
                            amc.logo_url,
                            bh.virtual_balance,
                            bh.created_at
                        FROM ai_bot_balance_history bh
                        JOIN ai_model_configs amc ON bh.model_config_id = amc.id
                        JOIN ai_bots ab ON bh.ai_bot_id = ab.id
                        WHERE ab.user_id = %s
                          AND amc.id = %s
                          AND bh.created_at >= NOW() - INTERVAL '%s hours'
                        ORDER BY bh.created_at ASC
                    """, (current_user.id, model_filter, hours))
                else:
                    # All models
                    cursor.execute("""
                        SELECT
                            bh.ai_bot_id,
                            bh.model_config_id,
                            amc.name as model_name,
                            amc.provider,
                            amc.logo_url,
                            bh.virtual_balance,
                            bh.created_at
                        FROM ai_bot_balance_history bh
                        JOIN ai_model_configs amc ON bh.model_config_id = amc.id
                        JOIN ai_bots ab ON bh.ai_bot_id = ab.id
                        WHERE ab.user_id = %s
                          AND bh.created_at >= NOW() - INTERVAL '%s hours'
                        ORDER BY bh.created_at ASC
                    """, (current_user.id, hours))

                history = cursor.fetchall()

            # Group by model for chart
            datasets = {}
            for row in history:
                model_id = row['model_config_id']
                if model_id not in datasets:
                    datasets[model_id] = {
                        'label': row['model_name'],
                        'provider': row['provider'],
                        'logo_url': row['logo_url'],
                        'data': []
                    }

                datasets[model_id]['data'].append({
                    'x': row['created_at'].isoformat(),
                    'y': float(row['virtual_balance'])
                })

            return jsonify({
                'success': True,
                'datasets': list(datasets.values())
            })

        except Exception as e:
            logger.error(f"Chart data error: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500
