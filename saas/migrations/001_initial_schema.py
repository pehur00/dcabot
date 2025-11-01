"""
Migration: Initial database schema
Date: 2025-11-01

This migration creates the base schema that already exists in production.
Includes: users, bots, trading_pairs, trades, bot_logs, bot_metrics, password_reset_tokens
"""

description = "Initial database schema with all core tables"


def upgrade(conn):
    """Create initial database schema"""
    cursor = conn.cursor()

    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email VARCHAR(255) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            plan VARCHAR(20) DEFAULT 'free',
            max_bots INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Bots table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bots (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            name VARCHAR(100) NOT NULL,
            exchange VARCHAR(20) NOT NULL,
            testnet BOOLEAN DEFAULT TRUE,
            api_key_encrypted TEXT NOT NULL,
            api_secret_encrypted TEXT NOT NULL,
            status VARCHAR(20) DEFAULT 'stopped',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Trading pairs table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trading_pairs (
            id SERIAL PRIMARY KEY,
            bot_id INTEGER REFERENCES bots(id) ON DELETE CASCADE,
            symbol VARCHAR(20) NOT NULL,
            side VARCHAR(10) NOT NULL,
            leverage INTEGER DEFAULT 10,
            ema_interval INTEGER DEFAULT 1,
            automatic_mode BOOLEAN DEFAULT TRUE,
            config JSONB,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Trades table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id SERIAL PRIMARY KEY,
            bot_id INTEGER REFERENCES bots(id) ON DELETE CASCADE,
            trading_pair_id INTEGER REFERENCES trading_pairs(id),
            symbol VARCHAR(20) NOT NULL,
            action VARCHAR(20) NOT NULL,
            side VARCHAR(10) NOT NULL,
            quantity DECIMAL(20,8),
            price DECIMAL(20,8),
            pnl DECIMAL(20,8),
            balance_after DECIMAL(20,8),
            executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            details JSONB
        )
    """)

    # Bot execution logs
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bot_logs (
            id SERIAL PRIMARY KEY,
            bot_id INTEGER REFERENCES bots(id) ON DELETE CASCADE,
            level VARCHAR(10) NOT NULL,
            message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Bot metrics table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bot_metrics (
            id SERIAL PRIMARY KEY,
            bot_id INTEGER REFERENCES bots(id) ON DELETE CASCADE,
            symbol VARCHAR(20),
            balance DECIMAL(20,8),
            position_value DECIMAL(20,8),
            unrealized_pnl DECIMAL(20,8),
            margin_level DECIMAL(10,4),
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Password reset tokens table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            token VARCHAR(64) UNIQUE NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            used BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bots_user_id ON bots(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bots_status ON bots(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_trading_pairs_bot_id ON trading_pairs(bot_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_bot_id ON trades(bot_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_executed_at ON trades(executed_at DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bot_logs_bot_id ON bot_logs(bot_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bot_logs_created_at ON bot_logs(created_at DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bot_metrics_bot_id ON bot_metrics(bot_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bot_metrics_timestamp ON bot_metrics(timestamp DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_token ON password_reset_tokens(token)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_user_id ON password_reset_tokens(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_expires_at ON password_reset_tokens(expires_at)")

    # Triggers for updated_at
    cursor.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ language 'plpgsql'
    """)

    cursor.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'update_users_updated_at') THEN
                CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
                FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
            END IF;
        END $$
    """)

    cursor.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'update_bots_updated_at') THEN
                CREATE TRIGGER update_bots_updated_at BEFORE UPDATE ON bots
                FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
            END IF;
        END $$
    """)

    conn.commit()
