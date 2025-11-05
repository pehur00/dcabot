"""
DCA Bot SaaS - Flask Web Application
Complete UI with user authentication and bot management
"""
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response, abort
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_caching import Cache
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

# Configure caching (in-memory, resets on deploy)
app.config['CACHE_TYPE'] = 'SimpleCache'  # In-memory cache
app.config['CACHE_DEFAULT_TIMEOUT'] = 0  # Cache forever (charts never change)
cache = Cache(app)

# Database connection test
try:
    from saas.database import test_connection, get_db
    db_connected = test_connection()
    logger.info("✅ Database connection successful")
except Exception as e:
    logger.error(f"❌ Database connection failed: {e}")
    db_connected = False

# Run database migrations automatically
if db_connected:
    try:
        from saas.migration_runner import run_migrations
        with get_db() as conn:
            run_migrations(conn)
    except Exception as e:
        logger.error(f"❌ Migration error: {e}")
        # Continue app startup even if migrations fail
        # This allows manual intervention if needed

# Setup Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'

# Setup OAuth
from saas.oauth import init_oauth
oauth = init_oauth(app)


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


# Register AI bot routes
from saas.ai_bot_routes import register_ai_bot_routes
register_ai_bot_routes(app)


# ============================================================================
# Public Routes
# ============================================================================

@app.route('/')
def index():
    """Home page"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    # Fetch latest backtest results for front page
    backtest_results = []
    try:
        with get_db() as conn:
            cursor = conn.cursor()

            # Get most recent result for each symbol
            cursor.execute("""
                SELECT DISTINCT ON (symbol)
                    symbol, side, leverage,
                    profit_loss, profit_loss_pct, max_drawdown_pct,
                    total_trades, win_rate,
                    start_date, end_date
                FROM backtest_results
                WHERE status = 'completed'
                ORDER BY symbol, executed_at DESC
                LIMIT 10
            """)

            for row in cursor.fetchall():
                backtest_results.append({
                    'symbol': row[0],
                    'side': row[1],
                    'leverage': row[2],
                    'profit_loss': float(row[3]) if row[3] else 0,
                    'profit_loss_pct': float(row[4]) if row[4] else 0,
                    'max_drawdown_pct': float(row[5]) if row[5] else 0,
                    'total_trades': row[6],
                    'win_rate': float(row[7]) if row[7] else 0,
                    'start_date': row[8],
                    'end_date': row[9],
                })

            # Sort by profit_loss_pct descending
            backtest_results.sort(key=lambda x: x['profit_loss_pct'], reverse=True)

    except Exception as e:
        print(f"Error fetching backtest results for front page: {e}")
        # Continue with empty results

    return render_template('index.html', backtest_results=backtest_results)


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        from saas.database import get_db
        from saas.security import verify_password
        from saas.validation import validate_email, sanitize_string

        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        # OWASP A03 & A07: Validate login inputs
        if not email or not password:
            flash('Email and password are required', 'error')
            return render_template('login.html')

        # Validate email format (prevent injection)
        is_valid, error_msg = validate_email(email)
        if not is_valid:
            flash('Invalid email or password', 'error')  # Generic message for security
            return render_template('login.html')

        # Sanitize email
        email = sanitize_string(email, max_length=255).lower()

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
        from saas.validation import (
            validate_email,
            validate_password,
            sanitize_string
        )

        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        password_confirm = request.form.get('password_confirm', '')

        # OWASP A03: Validate and sanitize email
        is_valid, error_msg = validate_email(email)
        if not is_valid:
            flash(error_msg, 'error')
            return render_template('register.html')

        # Sanitize email (defense in depth)
        email = sanitize_string(email, max_length=255).lower()

        # OWASP A07: Validate password strength
        is_valid, error_msg = validate_password(password)
        if not is_valid:
            flash(error_msg, 'error')
            return render_template('register.html')

        # Check password confirmation
        if password != password_confirm:
            flash('Passwords do not match', 'error')
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


@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Forgot password page - send reset link"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        from saas.database import get_db
        from saas.validation import validate_email, sanitize_string
        from saas.email_service import email_service
        import secrets
        from datetime import datetime, timedelta

        email = request.form.get('email', '').strip()

        # Validate email
        is_valid, error_msg = validate_email(email)
        if not is_valid:
            flash(error_msg, 'error')
            return render_template('forgot_password.html')

        email = sanitize_string(email, max_length=255).lower()

        try:
            with get_db() as conn:
                cursor = conn.cursor()

                # Check if user exists
                cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
                user = cursor.fetchone()

                # Always show success message (security: don't reveal if email exists)
                if user:
                    user_id = user[0]

                    # Generate secure token
                    token = secrets.token_urlsafe(32)
                    expires_at = datetime.now() + timedelta(hours=1)

                    # Store token in database
                    cursor.execute("""
                        INSERT INTO password_reset_tokens (user_id, token, expires_at)
                        VALUES (%s, %s, %s)
                    """, (user_id, token, expires_at))
                    conn.commit()

                    # Send reset email
                    reset_link = url_for('reset_password', token=token, _external=True)
                    email_service.send_password_reset_email(email, reset_link, expires_minutes=60)

            flash('If an account exists with that email, you will receive a password reset link shortly.', 'success')
            return redirect(url_for('login'))

        except Exception as e:
            logger.error(f"Forgot password error: {e}")
            flash('An error occurred. Please try again.', 'error')

    return render_template('forgot_password.html')


@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Reset password page - validate token and update password"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    from saas.database import get_db
    from saas.security import hash_password
    from saas.validation import validate_password
    from datetime import datetime

    # Validate token
    try:
        with get_db() as conn:
            cursor = conn.cursor()

            # Get token info
            cursor.execute("""
                SELECT user_id, expires_at, used
                FROM password_reset_tokens
                WHERE token = %s
            """, (token,))
            token_data = cursor.fetchone()

            if not token_data:
                flash('Invalid or expired password reset link', 'error')
                return redirect(url_for('login'))

            user_id, expires_at, used = token_data

            # Check if token is expired or used
            if used:
                flash('This password reset link has already been used', 'error')
                return redirect(url_for('login'))

            if datetime.now() > expires_at:
                flash('This password reset link has expired', 'error')
                return redirect(url_for('login'))

            # Process password reset
            if request.method == 'POST':
                password = request.form.get('password', '')
                password_confirm = request.form.get('password_confirm', '')

                # Validate password
                is_valid, error_msg = validate_password(password)
                if not is_valid:
                    flash(error_msg, 'error')
                    return render_template('reset_password.html', token=token)

                # Check password confirmation
                if password != password_confirm:
                    flash('Passwords do not match', 'error')
                    return render_template('reset_password.html', token=token)

                # Update password
                password_hash = hash_password(password)
                cursor.execute("""
                    UPDATE users
                    SET password_hash = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (password_hash, user_id))

                # Mark token as used
                cursor.execute("""
                    UPDATE password_reset_tokens
                    SET used = TRUE
                    WHERE token = %s
                """, (token,))

                conn.commit()

                flash('Your password has been reset successfully. You can now login with your new password.', 'success')
                return redirect(url_for('login'))

    except Exception as e:
        logger.error(f"Reset password error: {e}")
        flash('An error occurred. Please try again.', 'error')
        return redirect(url_for('login'))

    return render_template('reset_password.html', token=token)


# ============================================================================
# OAuth Routes
# ============================================================================

@app.route('/auth/google')
def google_login():
    """Initiate Google OAuth login"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if not oauth:
        flash('Google login is not configured', 'error')
        return redirect(url_for('login'))

    from saas.oauth import get_redirect_uri
    redirect_uri = get_redirect_uri(request)

    return oauth.google.authorize_redirect(redirect_uri)


@app.route('/auth/google/callback')
def google_callback():
    """Handle Google OAuth callback"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if not oauth:
        flash('Google login is not configured', 'error')
        return redirect(url_for('login'))

    try:
        from saas.database import get_db
        from saas.oauth import extract_user_info

        # Get OAuth token
        token = oauth.google.authorize_access_token()
        user_info = extract_user_info(token)

        # Validate user info
        if not user_info.get('email_verified'):
            flash('Please verify your Google email address first', 'error')
            return redirect(url_for('login'))

        google_id = user_info.get('google_id')
        email = user_info.get('email')

        if not google_id or not email:
            flash('Failed to get user information from Google', 'error')
            return redirect(url_for('login'))

        # Check if user exists
        with get_db() as conn:
            cursor = conn.cursor()

            # Try to find user by Google ID first
            cursor.execute("""
                SELECT id, email, plan, max_bots, is_admin, is_active
                FROM users
                WHERE google_id = %s
            """, (google_id,))
            user_data = cursor.fetchone()

            # If not found by Google ID, try by email
            if not user_data:
                cursor.execute("""
                    SELECT id, email, plan, max_bots, is_admin, is_active
                    FROM users
                    WHERE email = %s
                """, (email,))
                user_data = cursor.fetchone()

                # If user exists with email but not Google ID, link accounts
                if user_data:
                    cursor.execute("""
                        UPDATE users
                        SET google_id = %s, oauth_provider = 'google', profile_picture_url = %s, updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (google_id, user_info.get('picture'), user_data[0]))
                    conn.commit()
                    logger.info(f"Linked Google account to existing user: {email}")

            # If user doesn't exist, create new user (pending approval)
            if not user_data:
                cursor.execute("""
                    INSERT INTO users (email, google_id, oauth_provider, profile_picture_url, plan, max_bots, is_active)
                    VALUES (%s, %s, 'google', %s, 'free', 1, FALSE)
                    RETURNING id, email, plan, max_bots, is_admin, is_active
                """, (email, google_id, user_info.get('picture')))
                user_data = cursor.fetchone()
                conn.commit()
                logger.info(f"Created new user via Google OAuth: {email}")

                flash('Your account has been created successfully! Please wait for admin approval before you can login.', 'success')
                return redirect(url_for('login'))

            # User exists - check if approved
            user_id, user_email, plan, max_bots, is_admin, is_active = user_data

            if not is_active:
                flash('Your account is pending approval. Please wait for an administrator to approve your registration.', 'warning')
                return redirect(url_for('login'))

            # Login user
            user = User(user_id, user_email, plan, max_bots, is_admin, is_active)
            login_user(user)
            flash('Successfully logged in with Google!', 'success')
            return redirect(url_for('dashboard'))

    except Exception as e:
        logger.error(f"Google OAuth error: {e}")
        flash('An error occurred during Google login', 'error')
        return redirect(url_for('login'))


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
        from saas.validation import (
            validate_bot_name,
            validate_exchange,
            validate_api_key,
            sanitize_string
        )

        try:
            name = request.form.get('name', '').strip()
            exchange = request.form.get('exchange', 'phemex').strip().lower()
            testnet = request.form.get('testnet') == 'on'
            api_key = request.form.get('api_key', '').strip()
            api_secret = request.form.get('api_secret', '').strip()

            # OWASP A03: Validate bot name
            is_valid, error_msg = validate_bot_name(name)
            if not is_valid:
                flash(error_msg, 'error')
                return render_template('bot_form.html')

            # OWASP A03: Validate exchange
            is_valid, error_msg = validate_exchange(exchange)
            if not is_valid:
                flash(error_msg, 'error')
                return render_template('bot_form.html')

            # OWASP A03: Validate API credentials
            is_valid, error_msg = validate_api_key(api_key)
            if not is_valid:
                flash(f'API Key: {error_msg}', 'error')
                return render_template('bot_form.html')

            is_valid, error_msg = validate_api_key(api_secret)
            if not is_valid:
                flash(f'API Secret: {error_msg}', 'error')
                return render_template('bot_form.html')

            # Sanitize inputs (defense in depth)
            name = sanitize_string(name, max_length=100)
            exchange = sanitize_string(exchange, max_length=20)

            # Encrypt API credentials (OWASP A02: Cryptographic Failures)
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


@app.route('/api/bots/<int:bot_id>/last-execution')
@login_required
def get_last_execution(bot_id):
    """API endpoint to get last execution timestamp for auto-refresh detection"""
    from saas.database import get_db
    from flask import jsonify

    try:
        with get_db() as conn:
            cursor = conn.cursor()

            # Verify user owns this bot
            cursor.execute("""
                SELECT id FROM bots WHERE id = %s AND user_id = %s
            """, (bot_id, current_user.id))
            if not cursor.fetchone():
                return jsonify({'error': 'Bot not found'}), 404

            # Get most recent execution time from execution_metrics
            cursor.execute("""
                SELECT MAX(executed_at) as last_execution
                FROM execution_metrics
                WHERE bot_id = %s
            """, (bot_id,))

            result = cursor.fetchone()
            last_execution = result[0] if result and result[0] else None

            return jsonify({
                'last_execution': last_execution.isoformat() if last_execution else None,
                'bot_id': bot_id
            })

    except Exception as e:
        logger.error(f"Get last execution error: {e}")
        return jsonify({'error': 'Failed to fetch last execution'}), 500


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

            # Get global backtest config
            cursor.execute("""
                SELECT id, name, profit_pnl, profit_threshold, buy_until_limit,
                       max_margin_pct, begin_size_of_balance,
                       close_threshold_high, close_threshold_mid,
                       close_pct_high, close_pct_mid, is_active,
                       leverage, days, balance
                FROM global_backtest_config
                WHERE is_active = true
                LIMIT 1
            """)
            global_config_row = cursor.fetchone()
            global_config = None
            if global_config_row:
                global_config = {
                    'id': global_config_row[0],
                    'name': global_config_row[1],
                    'profit_pnl': float(global_config_row[2]),
                    'profit_threshold': float(global_config_row[3]),
                    'buy_until_limit': float(global_config_row[4]),
                    'max_margin_pct': float(global_config_row[5]) if global_config_row[5] else None,
                    'begin_size_of_balance': float(global_config_row[6]),
                    'close_threshold_high': float(global_config_row[7]),
                    'close_threshold_mid': float(global_config_row[8]),
                    'close_pct_high': float(global_config_row[9]),
                    'close_pct_mid': float(global_config_row[10]),
                    'is_active': global_config_row[11],
                    'leverage': global_config_row[12],
                    'days': global_config_row[13],
                    'balance': float(global_config_row[14])
                }

            # Get backtest configurations (per-symbol settings only)
            cursor.execute("""
                SELECT id, symbol, side, interval, category, source, is_active
                FROM backtest_configs
                ORDER BY category, symbol
            """)
            backtest_configs = cursor.fetchall()

            return render_template('admin.html',
                                 pending_users=pending_users,
                                 all_users=all_users,
                                 registration_enabled=registration_enabled,
                                 backtest_configs=backtest_configs,
                                 global_config=global_config)
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


@app.route('/admin/global-config/update', methods=['POST'])
@login_required
def update_global_config():
    """Update global backtest configuration"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('dashboard'))

    from saas.database import get_db

    try:
        # Get form data
        leverage = int(request.form.get('leverage'))
        days = int(request.form.get('days'))
        balance = float(request.form.get('balance'))
        profit_pnl = float(request.form.get('profit_pnl'))
        profit_threshold = float(request.form.get('profit_threshold'))
        buy_until_limit = float(request.form.get('buy_until_limit'))
        max_margin_pct = request.form.get('max_margin_pct')
        max_margin_pct = float(max_margin_pct) if max_margin_pct else None
        begin_size_of_balance = float(request.form.get('begin_size_of_balance'))
        close_threshold_high = float(request.form.get('close_threshold_high'))
        close_threshold_mid = float(request.form.get('close_threshold_mid'))
        close_pct_high = float(request.form.get('close_pct_high'))
        close_pct_mid = float(request.form.get('close_pct_mid'))

        with get_db() as conn:
            cursor = conn.cursor()

            # Update the active global config
            cursor.execute("""
                UPDATE global_backtest_config
                SET leverage = %s,
                    days = %s,
                    balance = %s,
                    profit_pnl = %s,
                    profit_threshold = %s,
                    buy_until_limit = %s,
                    max_margin_pct = %s,
                    begin_size_of_balance = %s,
                    close_threshold_high = %s,
                    close_threshold_mid = %s,
                    close_pct_high = %s,
                    close_pct_mid = %s,
                    updated_at = NOW()
                WHERE is_active = true
            """, (leverage, days, balance, profit_pnl, profit_threshold, buy_until_limit,
                  max_margin_pct, begin_size_of_balance, close_threshold_high,
                  close_threshold_mid, close_pct_high, close_pct_mid))

            conn.commit()

        flash('Global backtest config updated successfully!', 'success')
    except ValueError as e:
        logger.error(f"Invalid input for global config: {e}")
        flash('Invalid input values', 'error')
    except Exception as e:
        logger.error(f"Error updating global config: {e}")
        flash('Error updating global config', 'error')

    return redirect(url_for('admin_panel'))


@app.route('/admin/backtest/<int:config_id>/update', methods=['POST'])
@login_required
def update_backtest_config(config_id):
    """Update backtest configuration"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('dashboard'))

    from saas.database import get_db

    try:
        # Get form data (per-symbol settings only - leverage, days, balance, and strategy params are global)
        symbol = request.form.get('symbol')
        side = request.form.get('side')
        source = request.form.get('source')
        is_active = request.form.get('is_active') == 'on'
        category = request.form.get('category')

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE backtest_configs
                SET symbol = %s, side = %s, source = %s, is_active = %s, category = %s,
                    updated_at = NOW()
                WHERE id = %s
            """, (symbol, side, source, is_active, category, config_id))
            conn.commit()

        flash(f'Backtest configuration for {symbol} updated successfully!', 'success')
    except Exception as e:
        logger.error(f"Error updating backtest config: {e}")
        flash('Error updating backtest configuration', 'error')

    return redirect(url_for('admin_panel'))


@app.route('/admin/backtest/<int:config_id>/toggle', methods=['POST'])
@login_required
def toggle_backtest_config(config_id):
    """Toggle backtest configuration active status"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('dashboard'))

    from saas.database import get_db

    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE backtest_configs
                SET is_active = NOT is_active, updated_at = NOW()
                WHERE id = %s
                RETURNING symbol, is_active
            """, (config_id,))
            result = cursor.fetchone()
            conn.commit()

        if result:
            symbol, is_active = result
            status = 'enabled' if is_active else 'disabled'
            flash(f'Backtest for {symbol} {status} successfully!', 'success')
    except Exception as e:
        logger.error(f"Error toggling backtest config: {e}")
        flash('Error toggling backtest configuration', 'error')

    return redirect(url_for('admin_panel'))


@app.route('/admin/backtest/add', methods=['POST'])
@login_required
def add_backtest_config():
    """Add new backtest configuration"""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('dashboard'))

    from saas.database import get_db

    try:
        # Get form data
        # Per-symbol settings only (leverage, days, balance are now global)
        symbol = request.form.get('symbol')
        side = request.form.get('side', 'Long')
        source = request.form.get('source', 'binance')
        category = request.form.get('category', 'other')

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO backtest_configs (symbol, side, source, category)
                VALUES (%s, %s, %s, %s)
            """, (symbol, side, source, category))
            conn.commit()

        flash(f'Backtest configuration for {symbol} added successfully!', 'success')
    except Exception as e:
        logger.error(f"Error adding backtest config: {e}")
        flash('Error adding backtest configuration', 'error')

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


@app.route('/api/backtests/latest')
def api_latest_backtests():
    """
    Get latest backtest results for each symbol.
    Returns most recent completed backtest for each symbol/side combination.
    """
    try:
        with get_db() as conn:
            cursor = conn.cursor()

            # Get most recent result for each symbol using DISTINCT ON
            cursor.execute("""
                SELECT DISTINCT ON (symbol, side)
                    symbol, side, leverage, interval,
                    profit_loss, profit_loss_pct, max_drawdown_pct,
                    total_trades, win_rate, max_margin_used_pct,
                    start_date, end_date, executed_at
                FROM backtest_results
                WHERE status = 'completed'
                ORDER BY symbol, side, executed_at DESC
            """)

            results = []
            for row in cursor.fetchall():
                results.append({
                    'symbol': row[0],
                    'side': row[1],
                    'leverage': row[2],
                    'interval': row[3],
                    'profit_loss': float(row[4]) if row[4] else 0,
                    'profit_loss_pct': float(row[5]) if row[5] else 0,
                    'max_drawdown_pct': float(row[6]) if row[6] else 0,
                    'total_trades': row[7],
                    'win_rate': float(row[8]) if row[8] else 0,
                    'max_margin_used_pct': float(row[9]) if row[9] else 0,
                    'start_date': row[10].isoformat() if row[10] else None,
                    'end_date': row[11].isoformat() if row[11] else None,
                    'executed_at': row[12].isoformat() if row[12] else None,
                })

            # Sort by profit_loss_pct descending
            results.sort(key=lambda x: x['profit_loss_pct'], reverse=True)

            return jsonify(results)

    except Exception as e:
        print(f"Error fetching latest backtests: {e}")
        return jsonify([]), 500


@app.route('/api/backtests/<symbol>/history')
def api_backtest_history(symbol):
    """
    Get historical backtest results for a specific symbol.
    Returns last 12 backtest results for trending analysis.
    """
    try:
        limit = request.args.get('limit', 12, type=int)

        with get_db() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    executed_at, profit_loss_pct, max_drawdown_pct,
                    total_trades, win_rate, liquidation_occurred
                FROM backtest_results
                WHERE symbol = %s AND status = 'completed'
                ORDER BY executed_at DESC
                LIMIT %s
            """, (symbol, limit))

            results = []
            for row in cursor.fetchall():
                results.append({
                    'date': row[0].isoformat() if row[0] else None,
                    'profit_loss_pct': float(row[1]) if row[1] else 0,
                    'max_drawdown_pct': float(row[2]) if row[2] else 0,
                    'total_trades': row[3],
                    'win_rate': float(row[4]) if row[4] else 0,
                    'liquidation_occurred': row[5]
                })

            # Reverse to get chronological order (oldest to newest)
            results.reverse()

            return jsonify(results)

    except Exception as e:
        print(f"Error fetching backtest history for {symbol}: {e}")
        return jsonify([]), 500


@app.route('/backtest/<symbol>')
def backtest_detail(symbol):
    """Backtest detail page showing charts and metrics for a specific symbol"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()

            # Get the latest backtest for this symbol
            cursor.execute("""
                SELECT
                    id, symbol, side, leverage, interval,
                    test_period_days, start_date, end_date,
                    initial_balance, final_balance, profit_loss, profit_loss_pct,
                    max_drawdown_pct, total_trades, winning_trades, losing_trades, win_rate,
                    max_position_size, max_margin_used_pct, liquidation_occurred,
                    executed_at, execution_duration_seconds,
                    chart_balance_path, chart_position_path, chart_price_path
                FROM backtest_results
                WHERE symbol = %s AND status = 'completed'
                ORDER BY executed_at DESC
                LIMIT 1
            """, (symbol,))

            result = cursor.fetchone()

            if not result:
                flash(f'No backtest results found for {symbol}', 'error')
                return redirect(url_for('index'))

            backtest = {
                'id': result[0],
                'symbol': result[1],
                'side': result[2],
                'leverage': result[3],
                'interval': result[4],
                'test_period_days': result[5],
                'start_date': result[6],
                'end_date': result[7],
                'initial_balance': float(result[8]) if result[8] else 0,
                'final_balance': float(result[9]) if result[9] else 0,
                'profit_loss': float(result[10]) if result[10] else 0,
                'profit_loss_pct': float(result[11]) if result[11] else 0,
                'max_drawdown_pct': float(result[12]) if result[12] else 0,
                'total_trades': result[13],
                'winning_trades': result[14],
                'losing_trades': result[15],
                'win_rate': float(result[16]) if result[16] else 0,
                'max_position_size': float(result[17]) if result[17] else 0,
                'max_margin_used_pct': float(result[18]) if result[18] else 0,
                'liquidation_occurred': result[19],
                'executed_at': result[20],
                'execution_duration_seconds': result[21],
                'chart_path': result[22]
            }

            return render_template('backtest_detail.html', backtest=backtest)

    except Exception as e:
        logger.error(f"Error loading backtest detail: {e}")
        flash('Error loading backtest details', 'error')
        return redirect(url_for('index'))


@app.route('/api/backtest/<int:backtest_id>/chart')
@cache.cached(timeout=0, key_prefix=lambda: f'chart_{request.view_args["backtest_id"]}')
def get_backtest_chart(backtest_id):
    """
    API endpoint to serve chart image from database with server-side + client-side caching.

    Server-side cache: In-memory (resets on deploy), reduces DB queries for all users
    Client-side cache: Browser cache (1 year), eliminates requests after first load
    """
    try:
        with get_db() as conn:
            cursor = conn.cursor()

            # Fetch chart data from database
            cursor.execute("""
                SELECT chart_data
                FROM backtest_results
                WHERE id = %s AND chart_data IS NOT NULL
            """, (backtest_id,))

            result = cursor.fetchone()

            if not result or not result[0]:
                abort(404)

            # Convert memoryview to bytes (PostgreSQL BYTEA returns memoryview)
            chart_bytes = bytes(result[0])

            # Return PNG image with aggressive caching headers
            # Charts never change once created, so cache forever
            response = Response(chart_bytes, mimetype='image/png')
            response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'  # 1 year
            response.headers['ETag'] = f'"{backtest_id}"'  # Use backtest_id as ETag
            return response

    except Exception as e:
        logger.error(f"Error serving chart: {e}")
        abort(500)


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
