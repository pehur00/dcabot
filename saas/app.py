"""
DCA Bot SaaS - Flask Web Application
Complete UI with user authentication and bot management
"""
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from datetime import datetime
import logging
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-change-in-production')

# Database connection test
try:
    from saas.database import test_connection
    db_connected = test_connection()
    logger.info("✅ Database connection successful")
except Exception as e:
    logger.error(f"❌ Database connection failed: {e}")
    db_connected = False

# Setup Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'


class User(UserMixin):
    """User model for Flask-Login"""
    def __init__(self, id, email, plan='free', max_bots=1, is_admin=False, is_approved=True):
        self.id = id
        self.email = email
        self.plan = plan
        self.max_bots = max_bots
        self.is_admin = is_admin
        self.is_approved = is_approved


@login_manager.user_loader
def load_user(user_id):
    """Load user by ID for Flask-Login"""
    from saas.database import get_db
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, email, plan, max_bots, is_admin, is_approved FROM users WHERE id = %s", (user_id,))
            user_data = cursor.fetchone()
            if user_data:
                return User(user_data[0], user_data[1], user_data[2], user_data[3], user_data[4], user_data[5])
    except Exception as e:
        logger.error(f"Error loading user: {e}")
    return None


# ============================================================================
# Public Routes
# ============================================================================

@app.route('/')
def index():
    """Home page"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        from saas.database import get_db
        from saas.security import verify_password

        email = request.form.get('email')
        password = request.form.get('password')

        try:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, email, password_hash, plan, max_bots, is_admin, is_approved FROM users WHERE email = %s", (email,))
                user_data = cursor.fetchone()

                if user_data and verify_password(password, user_data[2]):
                    # Check if user is approved
                    if not user_data[6]:  # is_approved
                        flash('Your account is pending approval. Please wait for an administrator to approve your registration.', 'warning')
                        return render_template('login.html')

                    user = User(user_data[0], user_data[1], user_data[3], user_data[4], user_data[5], user_data[6])
                    login_user(user)
                    flash('Successfully logged in!', 'success')
                    return redirect(url_for('dashboard'))
                else:
                    flash('Invalid email or password', 'error')
        except Exception as e:
            logger.error(f"Login error: {e}")
            flash('An error occurred during login', 'error')

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    """Registration page"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    from saas.database import get_db

    # Check if registration is enabled
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = 'registration_enabled'")
            result = cursor.fetchone()
            registration_enabled = result[0].lower() == 'true' if result else True

        if not registration_enabled:
            flash('Registration is currently disabled. Please contact the administrator.', 'error')
            return redirect(url_for('login'))
    except Exception as e:
        logger.error(f"Error checking registration setting: {e}")

    if request.method == 'POST':
        from saas.security import hash_password

        email = request.form.get('email')
        password = request.form.get('password')
        password_confirm = request.form.get('password_confirm')

        # Validation
        if not email or not password:
            flash('Email and password are required', 'error')
            return render_template('register.html')

        if password != password_confirm:
            flash('Passwords do not match', 'error')
            return render_template('register.html')

        if len(password) < 8:
            flash('Password must be at least 8 characters', 'error')
            return render_template('register.html')

        try:
            with get_db() as conn:
                cursor = conn.cursor()
                # Check if user already exists
                cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
                if cursor.fetchone():
                    flash('Email already registered', 'error')
                    return render_template('register.html')

                # Create new user (pending approval)
                password_hash = hash_password(password)
                cursor.execute("""
                    INSERT INTO users (email, password_hash, plan, max_bots, is_approved, requested_at)
                    VALUES (%s, %s, 'free', 1, FALSE, NOW())
                    RETURNING id
                """, (email, password_hash))
                user_id = cursor.fetchone()[0]
                conn.commit()

                flash('Registration successful! Your account is pending approval. You will be notified when an administrator approves your account.', 'success')
                return redirect(url_for('login'))
        except Exception as e:
            logger.error(f"Registration error: {e}")
            flash('An error occurred during registration', 'error')

    return render_template('register.html')


@app.route('/logout')
@login_required
def logout():
    """Logout"""
    logout_user()
    flash('Successfully logged out', 'success')
    return redirect(url_for('index'))


# ============================================================================
# Protected Routes (require login)
# ============================================================================

@app.route('/dashboard')
@login_required
def dashboard():
    """User dashboard showing all bots"""
    from saas.database import get_db

    try:
        with get_db() as conn:
            cursor = conn.cursor()
            # Get user's bots
            cursor.execute("""
                SELECT id, name, exchange, testnet, status, created_at
                FROM bots
                WHERE user_id = %s
                ORDER BY created_at DESC
            """, (current_user.id,))
            bots = cursor.fetchall()

            # Get bot count
            bot_count = len(bots)
            can_create_more = bot_count < current_user.max_bots

            return render_template('dashboard.html',
                                   bots=bots,
                                   bot_count=bot_count,
                                   max_bots=current_user.max_bots,
                                   can_create_more=can_create_more)
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        flash('Error loading dashboard', 'error')
        return render_template('dashboard.html', bots=[], bot_count=0, max_bots=current_user.max_bots, can_create_more=True)


@app.route('/bots/new', methods=['GET', 'POST'])
@login_required
def create_bot():
    """Create new bot"""
    from saas.database import get_db
    from saas.security import encrypt_api_key

    # Check if user can create more bots
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM bots WHERE user_id = %s", (current_user.id,))
        bot_count = cursor.fetchone()[0]

        if bot_count >= current_user.max_bots:
            flash(f'You have reached your bot limit ({current_user.max_bots} bots on {current_user.plan} plan)', 'error')
            return redirect(url_for('dashboard'))

    if request.method == 'POST':
        try:
            name = request.form.get('name')
            exchange = request.form.get('exchange', 'phemex')
            testnet = request.form.get('testnet') == 'on'
            api_key = request.form.get('api_key')
            api_secret = request.form.get('api_secret')

            # Validation
            if not name or not api_key or not api_secret:
                flash('All fields are required', 'error')
                return render_template('bot_form.html')

            # Encrypt API credentials
            api_key_encrypted = encrypt_api_key(api_key)
            api_secret_encrypted = encrypt_api_key(api_secret)

            # Create bot
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO bots (user_id, name, exchange, testnet, api_key_encrypted, api_secret_encrypted, status)
                    VALUES (%s, %s, %s, %s, %s, %s, 'stopped')
                    RETURNING id
                """, (current_user.id, name, exchange, testnet, api_key_encrypted, api_secret_encrypted))
                bot_id = cursor.fetchone()[0]
                conn.commit()

                flash(f'Bot "{name}" created successfully!', 'success')
                return redirect(url_for('view_bot', bot_id=bot_id))
        except Exception as e:
            logger.error(f"Create bot error: {e}")
            flash('Error creating bot', 'error')

    return render_template('bot_form.html', bot=None)


@app.route('/bots/<int:bot_id>')
@login_required
def view_bot(bot_id):
    """View bot details"""
    from saas.database import get_db

    try:
        with get_db() as conn:
            cursor = conn.cursor()
            # Get bot details
            cursor.execute("""
                SELECT id, name, exchange, testnet, status, created_at
                FROM bots
                WHERE id = %s AND user_id = %s
            """, (bot_id, current_user.id))
            bot = cursor.fetchone()

            if not bot:
                flash('Bot not found', 'error')
                return redirect(url_for('dashboard'))

            # Get trading pairs
            cursor.execute("""
                SELECT id, symbol, side, leverage, ema_interval, automatic_mode, is_active
                FROM trading_pairs
                WHERE bot_id = %s
            """, (bot_id,))
            trading_pairs = cursor.fetchall()

            # Get recent trades
            cursor.execute("""
                SELECT symbol, action, side, quantity, price, pnl, executed_at
                FROM trades
                WHERE bot_id = %s
                ORDER BY executed_at DESC
                LIMIT 20
            """, (bot_id,))
            trades = cursor.fetchall()

            # Get bot logs
            cursor.execute("""
                SELECT id, level, message, created_at
                FROM bot_logs
                WHERE bot_id = %s
                ORDER BY created_at DESC
                LIMIT 50
            """, (bot_id,))
            bot_logs = cursor.fetchall()

            # Get last execution status
            cursor.execute("""
                SELECT created_at, level, message
                FROM bot_logs
                WHERE bot_id = %s AND message LIKE '%%Execution%%'
                ORDER BY created_at DESC
                LIMIT 1
            """, (bot_id,))
            last_execution = cursor.fetchone()

            return render_template('bot_detail.html', bot=bot, trading_pairs=trading_pairs,
                                 trades=trades, bot_logs=bot_logs, last_execution=last_execution)
    except Exception as e:
        import traceback
        logger.error(f"View bot error: {e}")
        logger.error(traceback.format_exc())
        flash(f'Error loading bot: {str(e)}', 'error')
        return redirect(url_for('dashboard'))


@app.route('/bots/<int:bot_id>/start', methods=['POST'])
@login_required
def start_bot(bot_id):
    """Start bot"""
    from saas.database import get_db

    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE bots
                SET status = 'running', updated_at = NOW()
                WHERE id = %s AND user_id = %s
            """, (bot_id, current_user.id))
            conn.commit()
            flash('Bot started successfully', 'success')
    except Exception as e:
        logger.error(f"Start bot error: {e}")
        flash('Error starting bot', 'error')

    return redirect(url_for('view_bot', bot_id=bot_id))


@app.route('/bots/<int:bot_id>/stop', methods=['POST'])
@login_required
def stop_bot(bot_id):
    """Stop bot"""
    from saas.database import get_db

    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE bots
                SET status = 'stopped', updated_at = NOW()
                WHERE id = %s AND user_id = %s
            """, (bot_id, current_user.id))
            conn.commit()
            flash('Bot stopped successfully', 'success')
    except Exception as e:
        logger.error(f"Stop bot error: {e}")
        flash('Error stopping bot', 'error')

    return redirect(url_for('view_bot', bot_id=bot_id))


@app.route('/bots/<int:bot_id>/delete', methods=['POST'])
@login_required
def delete_bot(bot_id):
    """Delete bot"""
    from saas.database import get_db

    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM bots
                WHERE id = %s AND user_id = %s
            """, (bot_id, current_user.id))
            conn.commit()
            flash('Bot deleted successfully', 'success')
    except Exception as e:
        logger.error(f"Delete bot error: {e}")
        flash('Error deleting bot', 'error')

    return redirect(url_for('dashboard'))


@app.route('/api/bots/<int:bot_id>/metrics')
@login_required
def get_bot_metrics(bot_id):
    """API endpoint to fetch execution metrics for graphing"""
    from saas.database import get_db
    from flask import jsonify
    from datetime import datetime, timedelta

    try:
        # Get time range from query params (default: last 7 days)
        days = request.args.get('days', 7, type=int)
        since = datetime.now() - timedelta(days=days)

        with get_db() as conn:
            cursor = conn.cursor()

            # Verify user owns this bot
            cursor.execute("""
                SELECT id FROM bots WHERE id = %s AND user_id = %s
            """, (bot_id, current_user.id))
            if not cursor.fetchone():
                return jsonify({'error': 'Bot not found'}), 404

            # Fetch metrics
            cursor.execute("""
                SELECT
                    executed_at,
                    symbol,
                    total_balance,
                    position_value,
                    unrealized_pnl,
                    unrealized_pnl_pct,
                    margin_level,
                    current_price,
                    entry_price,
                    action,
                    conclusion
                FROM execution_metrics
                WHERE bot_id = %s AND executed_at >= %s
                ORDER BY executed_at ASC
            """, (bot_id, since))

            metrics = cursor.fetchall()

            # Group data by symbol for multi-pair support
            from collections import defaultdict

            # Collect unique timestamps and balance (same for all symbols)
            timestamps = []
            balance_data = []
            symbol_data = defaultdict(lambda: {
                'position_value': [],
                'unrealized_pnl': [],
                'margin_level': []
            })

            # Track which timestamps we've seen
            seen_timestamps = set()

            for row in metrics:
                (exec_time, symbol, balance, pos_val, pnl, pnl_pct,
                 margin, curr_price, entry, action, conclusion) = row

                timestamp_iso = exec_time.isoformat()

                # Add timestamp and balance only once per unique time
                if timestamp_iso not in seen_timestamps:
                    timestamps.append(timestamp_iso)
                    balance_data.append(float(balance) if balance else None)
                    seen_timestamps.add(timestamp_iso)

                # Group position metrics by symbol
                symbol_data[symbol]['position_value'].append({
                    'time': timestamp_iso,
                    'value': float(pos_val) if pos_val else None
                })
                symbol_data[symbol]['unrealized_pnl'].append({
                    'time': timestamp_iso,
                    'value': float(pnl) if pnl else None
                })
                symbol_data[symbol]['margin_level'].append({
                    'time': timestamp_iso,
                    'value': float(margin) if margin else None
                })

            # Format response with per-symbol datasets
            data = {
                'timestamps': timestamps,
                'balance': balance_data,
                'symbols': {}
            }

            # Add per-symbol data
            for symbol, metrics_dict in symbol_data.items():
                data['symbols'][symbol] = {
                    'position_value': [m['value'] for m in metrics_dict['position_value']],
                    'unrealized_pnl': [m['value'] for m in metrics_dict['unrealized_pnl']],
                    'margin_level': [m['value'] for m in metrics_dict['margin_level']]
                }

            # Backward compatibility: if only one symbol, also add flat arrays
            if len(symbol_data) == 1:
                single_symbol = list(symbol_data.keys())[0]
                data['position_value'] = data['symbols'][single_symbol]['position_value']
                data['unrealized_pnl'] = data['symbols'][single_symbol]['unrealized_pnl']
                data['margin_level'] = data['symbols'][single_symbol]['margin_level']

            return jsonify(data)

    except Exception as e:
        logger.error(f"Get metrics error: {e}")
        return jsonify({'error': 'Failed to fetch metrics'}), 500


@app.route('/bots/<int:bot_id>/pairs/new', methods=['GET', 'POST'])
@login_required
def add_trading_pair(bot_id):
    """Add trading pair to bot"""
    from saas.database import get_db

    # Verify bot ownership
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM bots WHERE id = %s AND user_id = %s", (bot_id, current_user.id))
        bot = cursor.fetchone()
        if not bot:
            flash('Bot not found', 'error')
            return redirect(url_for('dashboard'))

    if request.method == 'POST':
        try:
            symbol = request.form.get('symbol').upper()
            side = request.form.get('side')
            leverage = int(request.form.get('leverage', 10))
            ema_interval = int(request.form.get('ema_interval', 1))
            automatic_mode = request.form.get('automatic_mode') == 'on'

            # Validation
            if not symbol or not side:
                flash('Symbol and side are required', 'error')
                return render_template('trading_pair_form.html', bot=bot, pair=None)

            # Create trading pair
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO trading_pairs (bot_id, symbol, side, leverage, ema_interval, automatic_mode, is_active)
                    VALUES (%s, %s, %s, %s, %s, %s, true)
                """, (bot_id, symbol, side, leverage, ema_interval, automatic_mode))
                conn.commit()

                flash(f'Trading pair {symbol} added successfully!', 'success')
                return redirect(url_for('view_bot', bot_id=bot_id))
        except Exception as e:
            logger.error(f"Add trading pair error: {e}")
            flash('Error adding trading pair', 'error')

    return render_template('trading_pair_form.html', bot=bot, pair=None)


@app.route('/bots/<int:bot_id>/pairs/<int:pair_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_trading_pair(bot_id, pair_id):
    """Edit trading pair"""
    from saas.database import get_db

    # Verify bot ownership and get pair
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT b.id, b.name, tp.id, tp.symbol, tp.side, tp.leverage, tp.ema_interval, tp.automatic_mode, tp.is_active
            FROM bots b
            JOIN trading_pairs tp ON tp.bot_id = b.id
            WHERE b.id = %s AND b.user_id = %s AND tp.id = %s
        """, (bot_id, current_user.id, pair_id))
        result = cursor.fetchone()

        if not result:
            flash('Trading pair not found', 'error')
            return redirect(url_for('dashboard'))

        bot = (result[0], result[1])
        pair = result[2:]

    if request.method == 'POST':
        try:
            symbol = request.form.get('symbol').upper()
            side = request.form.get('side')
            leverage = int(request.form.get('leverage', 10))
            ema_interval = int(request.form.get('ema_interval', 1))
            automatic_mode = request.form.get('automatic_mode') == 'on'
            is_active = request.form.get('is_active') == 'on'

            # Update trading pair
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE trading_pairs
                    SET symbol = %s, side = %s, leverage = %s, ema_interval = %s,
                        automatic_mode = %s, is_active = %s
                    WHERE id = %s AND bot_id = %s
                """, (symbol, side, leverage, ema_interval, automatic_mode, is_active, pair_id, bot_id))
                conn.commit()

                flash(f'Trading pair {symbol} updated successfully!', 'success')
                return redirect(url_for('view_bot', bot_id=bot_id))
        except Exception as e:
            logger.error(f"Edit trading pair error: {e}")
            flash('Error updating trading pair', 'error')

    return render_template('trading_pair_form.html', bot=bot, pair=pair)


@app.route('/bots/<int:bot_id>/pairs/<int:pair_id>/delete', methods=['POST'])
@login_required
def delete_trading_pair(bot_id, pair_id):
    """Delete trading pair"""
    from saas.database import get_db

    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM trading_pairs
                WHERE id = %s AND bot_id IN (SELECT id FROM bots WHERE id = %s AND user_id = %s)
            """, (pair_id, bot_id, current_user.id))
            conn.commit()
            flash('Trading pair deleted successfully', 'success')
    except Exception as e:
        logger.error(f"Delete trading pair error: {e}")
        flash('Error deleting trading pair', 'error')

    return redirect(url_for('view_bot', bot_id=bot_id))


# ============================================================================
# Admin Routes
# ============================================================================

@app.route('/admin')
@login_required
def admin_panel():
    """Admin panel - only accessible to admins"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('dashboard'))

    from saas.database import get_db

    try:
        with get_db() as conn:
            cursor = conn.cursor()

            # Get pending users
            cursor.execute("""
                SELECT id, email, requested_at
                FROM users
                WHERE is_approved = FALSE
                ORDER BY requested_at DESC
            """)
            pending_users = cursor.fetchall()

            # Get all users
            cursor.execute("""
                SELECT id, email, is_admin, is_approved, created_at
                FROM users
                ORDER BY created_at DESC
            """)
            all_users = cursor.fetchall()

            # Get registration setting
            cursor.execute("SELECT value FROM settings WHERE key = 'registration_enabled'")
            result = cursor.fetchone()
            registration_enabled = result[0].lower() == 'true' if result else True

            return render_template('admin.html',
                                 pending_users=pending_users,
                                 all_users=all_users,
                                 registration_enabled=registration_enabled)
    except Exception as e:
        logger.error(f"Admin panel error: {e}")
        flash('Error loading admin panel', 'error')
        return redirect(url_for('dashboard'))


@app.route('/admin/users/<int:user_id>/approve', methods=['POST'])
@login_required
def approve_user(user_id):
    """Approve a pending user"""
    if not current_user.is_admin:
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))

    from saas.database import get_db

    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users
                SET is_approved = TRUE
                WHERE id = %s
            """, (user_id,))
            conn.commit()

        flash('User approved successfully!', 'success')
    except Exception as e:
        logger.error(f"Error approving user: {e}")
        flash('Error approving user', 'error')

    return redirect(url_for('admin_panel'))


@app.route('/admin/users/<int:user_id>/reject', methods=['POST'])
@login_required
def reject_user(user_id):
    """Reject and delete a pending user"""
    if not current_user.is_admin:
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))

    from saas.database import get_db

    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM users WHERE id = %s AND is_approved = FALSE", (user_id,))
            conn.commit()

        flash('User rejected and deleted', 'success')
    except Exception as e:
        logger.error(f"Error rejecting user: {e}")
        flash('Error rejecting user', 'error')

    return redirect(url_for('admin_panel'))


@app.route('/admin/registration/toggle', methods=['POST'])
@login_required
def toggle_registration():
    """Toggle registration on/off"""
    if not current_user.is_admin:
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))

    from saas.database import get_db

    try:
        with get_db() as conn:
            cursor = conn.cursor()

            # Get current value
            cursor.execute("SELECT value FROM settings WHERE key = 'registration_enabled'")
            result = cursor.fetchone()
            current_value = result[0].lower() == 'true' if result else True

            # Toggle
            new_value = 'false' if current_value else 'true'
            cursor.execute("""
                UPDATE settings
                SET value = %s, updated_at = NOW()
                WHERE key = 'registration_enabled'
            """, (new_value,))
            conn.commit()

        status = 'enabled' if new_value == 'true' else 'disabled'
        flash(f'Registration {status} successfully!', 'success')
    except Exception as e:
        logger.error(f"Error toggling registration: {e}")
        flash('Error toggling registration', 'error')

    return redirect(url_for('admin_panel'))


# ============================================================================
# API Routes (for health checks and monitoring)
# ============================================================================

@app.route('/health')
def health():
    """Health check endpoint for Render monitoring"""
    try:
        from saas.database import get_db

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()

        # Check for active bots
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM bots WHERE status = 'running'")
            active_bots = cursor.fetchone()[0]

        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'database': 'connected',
            'active_bots': active_bots
        }), 200

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500


@app.route('/api/status')
def api_status():
    """API status endpoint"""
    return jsonify({
        'api_version': 'v1',
        'status': 'operational',
        'database_connected': db_connected,
        'timestamp': datetime.utcnow().isoformat()
    })


# ============================================================================
# Error Handlers
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    return render_template('error.html', error='Page not found', code=404), 404


@app.errorhandler(500)
def internal_error(error):
    return render_template('error.html', error='Internal server error', code=500), 500


if __name__ == '__main__':
    # Development server
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('DEBUG', 'True').lower() in ('true', '1', 't')

    logger.info(f"Starting DCA Bot SaaS on port {port}")
    logger.info(f"Debug mode: {debug}")
    logger.info(f"Database connected: {db_connected}")

    app.run(host='0.0.0.0', port=port, debug=debug)
