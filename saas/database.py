"""
Database connection and utilities
Supports both local postgres (Docker) and Digital Ocean managed database
"""
import os
from contextlib import contextmanager
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse


def get_db_config():
    """Parse DATABASE_URL and return connection parameters"""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is not set")

    # Parse the URL
    result = urlparse(database_url)

    # Extract SSL mode from query parameters
    sslmode = 'prefer'  # default
    if result.query:
        params = dict(param.split('=') for param in result.query.split('&'))
        sslmode = params.get('sslmode', 'prefer')

    return {
        'host': result.hostname,
        'port': result.port or 5432,
        'database': result.path[1:],  # Remove leading slash
        'user': result.username,
        'password': result.password,
        'sslmode': sslmode
    }


def get_connection():
    """
    Get a database connection
    Works with both local postgres and Digital Ocean managed database
    """
    config = get_db_config()

    conn = psycopg2.connect(
        host=config['host'],
        port=config['port'],
        database=config['database'],
        user=config['user'],
        password=config['password'],
        sslmode=config['sslmode'],
        connect_timeout=10
    )

    return conn


@contextmanager
def get_db():
    """
    Context manager for database connections
    Automatically handles commit/rollback and connection cleanup

    Usage:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users")
            results = cursor.fetchall()
    """
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def execute_query(query, params=None, fetch=True):
    """
    Execute a query and optionally fetch results

    Args:
        query: SQL query string
        params: Query parameters (tuple or dict)
        fetch: If True, return results; if False, return rowcount

    Returns:
        List of dicts (if fetch=True) or rowcount (if fetch=False)
    """
    with get_db() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(query, params)

        if fetch:
            return cursor.fetchall()
        else:
            return cursor.rowcount


def test_connection():
    """
    Test database connection
    Returns True if successful, raises exception otherwise
    """
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            assert result[0] == 1
        return True
    except Exception as e:
        print(f"Database connection failed: {e}")
        raise


# SQLAlchemy setup (optional, for ORM if needed later)
try:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker, scoped_session
    from sqlalchemy.ext.declarative import declarative_base

    database_url = os.getenv('DATABASE_URL')
    if database_url:
        # SQLAlchemy engine
        engine = create_engine(
            database_url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,  # Verify connections before using
            echo=False  # Set to True for SQL logging
        )

        # Session factory
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        Session = scoped_session(SessionLocal)

        # Base class for ORM models
        Base = declarative_base()

        def get_session():
            """Get a new database session"""
            return Session()

        @contextmanager
        def session_scope():
            """Provide a transactional scope for session operations"""
            session = Session()
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

except ImportError:
    # SQLAlchemy not installed, skip ORM setup
    pass


if __name__ == '__main__':
    # Test connection
    print("Testing database connection...")
    try:
        config = get_db_config()
        print(f"Connecting to: {config['host']}:{config['port']}/{config['database']}")
        print(f"SSL mode: {config['sslmode']}")

        if test_connection():
            print("✅ Database connection successful!")

            # Show some database info
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT version()")
                version = cursor.fetchone()[0]
                print(f"PostgreSQL version: {version}")

                cursor.execute("""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                    ORDER BY table_name
                """)
                tables = cursor.fetchall()
                if tables:
                    print(f"\nExisting tables:")
                    for table in tables:
                        print(f"  - {table[0]}")
                else:
                    print("\nNo tables found. Run schema.sql to create tables.")

    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        exit(1)


# ============================================================================
# AI Bot Helper Functions
# ============================================================================

def get_active_ai_bots():
    """Get all active AI bots with their model configurations"""
    query = """
        SELECT
            ab.*,
            amc.name as model_name,
            amc.provider as model_provider,
            amc.api_endpoint,
            amc.model_identifier,
            amc.cost_per_1m_input,
            amc.cost_per_1m_output
        FROM ai_bots ab
        JOIN ai_model_configs amc ON ab.model_config_id = amc.id
        WHERE ab.is_active = true
        ORDER BY ab.id
    """
    return execute_query(query, fetch=True)


def get_ai_bot_by_id(bot_id):
    """Get specific AI bot with model config"""
    query = """
        SELECT
            ab.*,
            amc.name as model_name,
            amc.provider as model_provider,
            amc.api_endpoint,
            amc.model_identifier,
            amc.cost_per_1m_input,
            amc.cost_per_1m_output,
            amc.logo_url
        FROM ai_bots ab
        JOIN ai_model_configs amc ON ab.model_config_id = amc.id
        WHERE ab.id = %s
    """
    results = execute_query(query, (bot_id,), fetch=True)
    return results[0] if results else None


def get_model_config(model_config_id):
    """Get AI model configuration by ID"""
    query = "SELECT * FROM ai_model_configs WHERE id = %s"
    results = execute_query(query, (model_config_id,), fetch=True)
    return results[0] if results else None


def log_ai_decision(decision_data):
    """
    Log AI decision to database

    Args:
        decision_data: Dict with all decision fields

    Returns:
        Decision ID
    """
    query = """
        INSERT INTO ai_decisions (
            ai_bot_id, symbol,
            current_price, ema20_1m, ema50_5m, ema100_1h,
            rsi_14, volume_trend, trend_description,
            decision, confidence, reasoning, risk_level,
            stop_loss, take_profit,
            action_taken, skip_reason, trade_id,
            input_tokens, output_tokens, api_cost, response_time_ms
        ) VALUES (
            %(ai_bot_id)s, %(symbol)s,
            %(current_price)s, %(ema20_1m)s, %(ema50_5m)s, %(ema100_1h)s,
            %(rsi_14)s, %(volume_trend)s, %(trend_description)s,
            %(decision)s, %(confidence)s, %(reasoning)s, %(risk_level)s,
            %(stop_loss)s, %(take_profit)s,
            %(action_taken)s, %(skip_reason)s, %(trade_id)s,
            %(input_tokens)s, %(output_tokens)s, %(api_cost)s, %(response_time_ms)s
        )
        RETURNING id
    """
    results = execute_query(query, decision_data, fetch=True)
    return results[0]['id'] if results else None


def update_ai_decision_action(decision_id, action_taken, skip_reason=None, trade_id=None):
    """Update action taken for a decision"""
    query = """
        UPDATE ai_decisions
        SET action_taken = %s, skip_reason = %s, trade_id = %s
        WHERE id = %s
    """
    execute_query(query, (action_taken, skip_reason, trade_id, decision_id), fetch=False)


def save_ai_bot_performance(performance_data):
    """Save AI bot performance snapshot"""
    query = """
        INSERT INTO ai_model_performance (
            ai_bot_id, model_config_id,
            balance, pnl_percentage, pnl_amount,
            total_trades, winning_trades, losing_trades, win_rate,
            open_positions, total_position_value,
            total_api_cost, total_api_calls
        ) VALUES (
            %(ai_bot_id)s, %(model_config_id)s,
            %(balance)s, %(pnl_percentage)s, %(pnl_amount)s,
            %(total_trades)s, %(winning_trades)s, %(losing_trades)s, %(win_rate)s,
            %(open_positions)s, %(total_position_value)s,
            %(total_api_cost)s, %(total_api_calls)s
        )
    """
    execute_query(query, performance_data, fetch=False)


def get_ai_bot_recent_decisions(bot_id, limit=10):
    """Get recent decisions for an AI bot"""
    query = """
        SELECT * FROM ai_decisions
        WHERE ai_bot_id = %s
        ORDER BY created_at DESC
        LIMIT %s
    """
    return execute_query(query, (bot_id, limit), fetch=True)


def get_ai_bot_stats(bot_id):
    """Get aggregated stats for an AI bot"""
    query = """
        SELECT
            COUNT(*) as total_decisions,
            COUNT(CASE WHEN action_taken = 'EXECUTED' THEN 1 END) as executed_count,
            COUNT(CASE WHEN action_taken = 'SKIPPED' THEN 1 END) as skipped_count,
            AVG(confidence) as avg_confidence,
            SUM(api_cost) as total_api_cost,
            AVG(response_time_ms) as avg_response_time
        FROM ai_decisions
        WHERE ai_bot_id = %s
    """
    results = execute_query(query, (bot_id,), fetch=True)
    return results[0] if results else None


def get_ai_bot_trade_stats(bot_id):
    """
    Get trade statistics for an AI bot

    Note: Currently we count executed trades from ai_decisions.
    Winning vs losing trades would require tracking individual trade PnL,
    which is planned for future enhancement.

    Returns:
        dict with total_trades, winning_trades, losing_trades
    """
    query = """
        SELECT
            COUNT(CASE WHEN action_taken = 'EXECUTED' THEN 1 END) as total_trades,
            0 as winning_trades,
            0 as losing_trades
        FROM ai_decisions
        WHERE ai_bot_id = %s
    """
    results = execute_query(query, (bot_id,), fetch=True)
    return results[0] if results else {'total_trades': 0, 'winning_trades': 0, 'losing_trades': 0}


def get_all_ai_models():
    """Get all available AI model configurations"""
    query = "SELECT * FROM ai_model_configs WHERE is_active = true ORDER BY name"
    return execute_query(query, fetch=True)


def update_virtual_balance(bot_id, balance_change, change_reason, decision_id=None, trade_id=None):
    """
    Update AI bot virtual balance and log the change

    Args:
        bot_id: AI bot ID
        balance_change: Amount to add/subtract from balance
        change_reason: 'api_cost', 'trade_pnl', 'trade_fee', etc.
        decision_id: Optional decision ID
        trade_id: Optional trade ID
    """
    query = """
        WITH updated_bot AS (
            UPDATE ai_bots
            SET virtual_balance = virtual_balance + %s
            WHERE id = %s
            RETURNING id, model_config_id, virtual_balance
        )
        INSERT INTO ai_bot_balance_history (
            ai_bot_id, model_config_id, virtual_balance, balance_change,
            change_reason, decision_id, trade_id
        )
        SELECT id, model_config_id, virtual_balance, %s, %s, %s, %s
        FROM updated_bot
        RETURNING virtual_balance
    """
    results = execute_query(
        query,
        (balance_change, bot_id, balance_change, change_reason, decision_id, trade_id),
        fetch=True
    )
    return results[0]['virtual_balance'] if results else None


def get_balance_history_for_chart(bot_ids=None, model_config_ids=None, hours=72):
    """
    Get balance history for charting (multi-line chart)

    Args:
        bot_ids: List of bot IDs (optional, for filtering)
        model_config_ids: List of model config IDs (optional, for filtering)
        hours: Hours of history to fetch (default 72)

    Returns:
        List of balance history records grouped by model
    """
    conditions = [f"created_at >= NOW() - INTERVAL '{hours} hours'"]
    params = []

    if bot_ids:
        conditions.append(f"ai_bot_id = ANY(%s)")
        params.append(bot_ids)

    if model_config_ids:
        conditions.append(f"model_config_id = ANY(%s)")
        params.append(model_config_ids)

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    query = f"""
        SELECT
            bh.ai_bot_id,
            bh.model_config_id,
            amc.name as model_name,
            amc.provider,
            amc.logo_url,
            bh.virtual_balance,
            bh.balance_change,
            bh.change_reason,
            bh.created_at
        FROM ai_bot_balance_history bh
        JOIN ai_model_configs amc ON bh.model_config_id = amc.id
        WHERE {where_clause}
        ORDER BY bh.created_at ASC
    """
    return execute_query(query, tuple(params) if params else None, fetch=True)


def get_ai_bot_leaderboard(user_id):
    """Get leaderboard stats for user's AI bots (bot-centric, not model-centric)"""
    query = """
        SELECT
            ab.id as bot_id,
            ab.name as bot_name,
            amc.id as model_config_id,
            amc.name as model_name,
            amc.provider,
            amc.logo_url,
            amp.balance as avg_balance,
            COUNT(ad.id) as total_decisions,
            COUNT(CASE WHEN ad.decision = 'BUY' THEN 1 END) as buy_signals,
            COUNT(CASE WHEN ad.decision = 'SELL' THEN 1 END) as sell_signals,
            COUNT(CASE WHEN ad.decision = 'HOLD' THEN 1 END) as hold_signals,
            COUNT(CASE WHEN ad.action_taken = 'EXECUTED' THEN 1 END) as total_trades,
            AVG(ad.confidence) as avg_confidence,
            SUM(ad.api_cost) as total_api_cost,
            AVG(ad.response_time_ms) as avg_response_time
        FROM ai_bots ab
        JOIN ai_model_configs amc ON amc.id = ab.model_config_id
        LEFT JOIN ai_decisions ad ON ab.id = ad.ai_bot_id
        LEFT JOIN LATERAL (
            SELECT balance
            FROM ai_model_performance
            WHERE ai_bot_id = ab.id
            ORDER BY snapshot_at DESC
            LIMIT 1
        ) amp ON true
        WHERE ab.user_id = %s AND ab.is_active = true
        GROUP BY ab.id, ab.name, amc.id, amc.name, amc.provider, amc.logo_url, amp.balance
        ORDER BY total_decisions DESC NULLS LAST
    """
    return execute_query(query, (user_id,), fetch=True)
