# Quick Start: Building the SaaS Platform

## Database: diptrader (Ready!)

✅ Database created on camproute-server: `diptrader`
✅ Separate credentials configured

**Connection string**:
```bash
DATABASE_URL=postgresql://diptrader_user:password@localhost:5432/diptrader
```

## Step 1: Initialize Database Schema (Do This First!)

### Create SQL schema file

Create `saas/schema.sql`:

```sql
-- Users table
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    plan VARCHAR(20) DEFAULT 'free',
    max_bots INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Bots table
CREATE TABLE bots (
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
);

-- Trading pairs table
CREATE TABLE trading_pairs (
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
);

-- Trades table
CREATE TABLE trades (
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
);

-- Bot execution logs
CREATE TABLE bot_logs (
    id SERIAL PRIMARY KEY,
    bot_id INTEGER REFERENCES bots(id) ON DELETE CASCADE,
    level VARCHAR(10) NOT NULL,
    message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_bots_user_id ON bots(user_id);
CREATE INDEX idx_bots_status ON bots(status);
CREATE INDEX idx_trading_pairs_bot_id ON trading_pairs(bot_id);
CREATE INDEX idx_trades_bot_id ON trades(bot_id);
CREATE INDEX idx_trades_executed_at ON trades(executed_at DESC);
CREATE INDEX idx_bot_logs_bot_id ON bot_logs(bot_id);
CREATE INDEX idx_bot_logs_created_at ON bot_logs(created_at DESC);
```

### Run schema on server

```bash
# SSH to server
ssh camproute-server

# Apply schema
psql -h localhost -U diptrader_user -d diptrader -f /path/to/schema.sql

# Or copy-paste it
psql -h localhost -U diptrader_user -d diptrader
# Then paste the SQL
```

## Step 2: Add Config Abstraction (Backward Compatible!)

This makes the bot work with both .env AND database without breaking existing functionality.

### Create `config_loader.py`

```python
# config_loader.py
"""
Configuration loader supporting both .env (standalone) and database (SaaS)
Maintains backward compatibility with existing bot
"""
import os
import json
from typing import List, Tuple, Optional
from pathlib import Path
from dotenv import load_dotenv


class ConfigSource:
    """Abstract configuration source"""

    def get_api_credentials(self) -> Tuple[str, str]:
        """Returns (api_key, api_secret)"""
        raise NotImplementedError

    def get_symbols(self) -> List[Tuple[str, str, bool]]:
        """Returns list of (symbol, side, automatic_mode)"""
        raise NotImplementedError

    def get_ema_interval(self) -> int:
        """Returns EMA interval for indicators"""
        raise NotImplementedError

    def is_testnet(self) -> bool:
        """Returns True if using testnet"""
        raise NotImplementedError

    def get_telegram_config(self) -> Tuple[Optional[str], Optional[str]]:
        """Returns (bot_token, chat_id)"""
        raise NotImplementedError


class EnvConfigSource(ConfigSource):
    """
    Load configuration from .env file (STANDALONE MODE)
    This is the existing behavior - maintains backward compatibility
    """

    def __init__(self):
        # Load .env if it exists
        env_path = Path(__file__).parent / '.env'
        if env_path.exists():
            load_dotenv(env_path)

    def get_api_credentials(self):
        api_key = os.getenv('API_KEY')
        api_secret = os.getenv('API_SECRET')
        if not api_key or not api_secret:
            raise ValueError("API_KEY and API_SECRET must be set in .env")
        return api_key, api_secret

    def get_symbols(self):
        symbol_sides = os.getenv('SYMBOL', '')
        return self._parse_symbols(symbol_sides)

    def get_ema_interval(self):
        return int(os.getenv('EMA_INTERVAL', 1))

    def is_testnet(self):
        return os.getenv('TESTNET', 'False').lower() in ('true', '1', 't')

    def get_telegram_config(self):
        return os.getenv('TELEGRAM_BOT_TOKEN'), os.getenv('TELEGRAM_CHAT_ID')

    def _parse_symbols(self, symbol_sides: str) -> List[Tuple[str, str, bool]]:
        """Parse SYMBOL env var: 'BTCUSDT:Long:True,ETHUSDT:Short:False'"""
        symbol_side_map = []
        if symbol_sides:
            try:
                for item in symbol_sides.split(','):
                    if ':' in item:
                        symbol, side, automatic = item.split(':', 2)
                        automatic_bool = automatic.strip().lower() in ["true", "1", "yes"]
                        symbol_side_map.append((symbol.strip(), side.strip(), automatic_bool))
            except Exception as e:
                raise ValueError(f"Error parsing SYMBOL: {e}")
        return symbol_side_map


class DatabaseConfigSource(ConfigSource):
    """
    Load configuration from database (SAAS MODE)
    Used when BOT_ID environment variable is set
    """

    def __init__(self, bot_id: int):
        self.bot_id = bot_id
        self._load_bot_data()

    def _load_bot_data(self):
        """Load bot and trading pairs from database"""
        import psycopg2
        from saas.security import decrypt_api_key

        # Get database connection string from environment
        db_url = os.getenv('DATABASE_URL')
        if not db_url:
            raise ValueError("DATABASE_URL not set for SaaS mode")

        # Connect and fetch bot data
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()

        # Get bot info
        cursor.execute("""
            SELECT api_key_encrypted, api_secret_encrypted, testnet, exchange
            FROM bots
            WHERE id = %s AND status = 'running'
        """, (self.bot_id,))

        bot_row = cursor.fetchone()
        if not bot_row:
            raise ValueError(f"Bot {self.bot_id} not found or not running")

        self.api_key_encrypted, self.api_secret_encrypted, self.testnet_flag, self.exchange = bot_row

        # Get trading pairs
        cursor.execute("""
            SELECT symbol, side, ema_interval, automatic_mode, leverage, config
            FROM trading_pairs
            WHERE bot_id = %s AND is_active = TRUE
        """, (self.bot_id,))

        self.trading_pairs = cursor.fetchall()

        cursor.close()
        conn.close()

    def get_api_credentials(self):
        from saas.security import decrypt_api_key
        api_key = decrypt_api_key(self.api_key_encrypted)
        api_secret = decrypt_api_key(self.api_secret_encrypted)
        return api_key, api_secret

    def get_symbols(self):
        """Return trading pairs as (symbol, side, automatic_mode)"""
        return [(row[0], row[1], row[3]) for row in self.trading_pairs]

    def get_ema_interval(self):
        """Use interval from first trading pair"""
        if self.trading_pairs:
            return self.trading_pairs[0][2]  # ema_interval column
        return 1

    def is_testnet(self):
        return self.testnet_flag

    def get_telegram_config(self):
        # TODO: Load from user notification preferences
        return None, None


def get_config_source() -> ConfigSource:
    """
    Factory function: returns appropriate config source based on environment

    If BOT_ID is set → Database mode (SaaS)
    Otherwise → .env mode (Standalone)
    """
    bot_id = os.getenv('BOT_ID')

    if bot_id:
        # SaaS mode: load from database
        return DatabaseConfigSource(int(bot_id))
    else:
        # Standalone mode: load from .env
        return EnvConfigSource()
```

### Update `main.py` to use config abstraction

```python
# main.py (UPDATE)
import asyncio
import logging
import os
from pathlib import Path

from pythonjsonlogger import json as jsonlogger
from config_loader import get_config_source  # NEW IMPORT

from strategies.MartingaleTradingStrategy import MartingaleTradingStrategy
from workflows.MartingaleTradingWorkflow import MartingaleTradingWorkflow
from clients.PhemexClient import PhemexClient
from notifications.TelegramNotifier import TelegramNotifier


async def main():
    # Setup logging
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    root_logger.setLevel(logging.INFO)

    log_handler = logging.StreamHandler()
    formatter = jsonlogger.JsonFormatter(
        '%(asctime)s %(levelname)s %(message)s %(symbol)s %(action)s %(json)s'
    )
    log_handler.setFormatter(formatter)
    root_logger.addHandler(log_handler)

    logger = logging.getLogger(__name__)
    logger.propagate = True

    # ====== NEW: Load config from appropriate source ======
    config = get_config_source()

    bot_mode = "SaaS" if os.getenv('BOT_ID') else "Standalone"
    logger.info(f"Running in {bot_mode} mode")

    # Get configuration (works for both .env and database!)
    api_key, api_secret = config.get_api_credentials()
    symbol_side_map = config.get_symbols()
    ema_interval = config.get_ema_interval()
    testnet = config.is_testnet()
    telegram_token, telegram_chat = config.get_telegram_config()
    # ====== END NEW CODE ======

    # Validate we have symbols to trade
    if not symbol_side_map:
        raise ValueError("No trading symbols configured")

    # Initialize Phemex client (unchanged)
    client = PhemexClient(api_key, api_secret, logger, testnet)

    # Initialize Telegram notifier (unchanged)
    notifier = TelegramNotifier(logger=logger)

    # Send startup notification if requested
    if os.getenv('BOT_STARTUP', 'False').lower() in ('true', '1', 't'):
        notifier.notify_bot_started(symbol_side_map, testnet)

    # Initialize trading strategy (unchanged)
    strategy = MartingaleTradingStrategy(
        client=client,
        logger=logger,
        notifier=notifier
    )

    workflow = MartingaleTradingWorkflow(strategy, logger)

    # Execute strategy for each symbol (unchanged)
    for symbol, pos_side, automatic_mode in symbol_side_map:
        await execute_symbol_strategy(
            symbol, workflow, ema_interval,
            pos_side, automatic_mode, notifier
        )


async def execute_symbol_strategy(symbol, workflow, ema_interval, pos_side, automatic_mode, notifier=None):
    """Execute strategy for a single trading pair (unchanged)"""
    try:
        await asyncio.to_thread(
            workflow.execute,
            symbol=symbol,
            ema_interval=ema_interval,
            pos_side=pos_side,
            automatic_mode=automatic_mode
        )
        logging.info(f'Successfully executed strategy for {symbol}')
    except Exception as e:
        error_msg = str(e)
        logging.error(f'Error executing strategy for {symbol}: {error_msg}')

        if notifier:
            notifier.notify_error(
                error_type="Strategy Execution Failed",
                symbol=symbol,
                error_message=error_msg
            )


if __name__ == '__main__':
    asyncio.run(main())
```

### Test backward compatibility

```bash
# Should work EXACTLY as before!
dcabot-env/bin/python main.py
```

If it works → ✅ Backward compatibility maintained!

## Step 3: Create Security Module

Create `saas/security.py`:

```python
# saas/security.py
"""
Security utilities for encrypting API keys and hashing passwords
"""
import os
from cryptography.fernet import Fernet
from werkzeug.security import generate_password_hash, check_password_hash


# Load encryption key from environment
# Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY')
if not ENCRYPTION_KEY:
    raise ValueError("ENCRYPTION_KEY environment variable must be set")

cipher = Fernet(ENCRYPTION_KEY.encode())


def encrypt_api_key(api_key: str) -> str:
    """Encrypt user's exchange API key before storing in database"""
    if not api_key:
        raise ValueError("API key cannot be empty")
    return cipher.encrypt(api_key.encode()).decode()


def decrypt_api_key(encrypted: str) -> str:
    """Decrypt user's exchange API key when needed for bot execution"""
    if not encrypted:
        raise ValueError("Encrypted API key cannot be empty")
    return cipher.decrypt(encrypted.encode()).decode()


def hash_password(password: str) -> str:
    """Hash user password for storage (bcrypt via werkzeug)"""
    return generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify user password against stored hash"""
    return check_password_hash(password_hash, password)


# Generate encryption key (run once, store in .env)
def generate_encryption_key():
    """Generate a new Fernet encryption key"""
    return Fernet.generate_key().decode()


if __name__ == '__main__':
    # Generate a new key
    print("New encryption key (add to .env):")
    print(f"ENCRYPTION_KEY={generate_encryption_key()}")
```

### Generate encryption key

```bash
python saas/security.py
```

Copy the output and add to your `.env` file on the server.

## Step 4: Environment Setup on Server

Create `/var/www/dcabot-saas/.env`:

```bash
# Database
DATABASE_URL=postgresql://diptrader_user:your_password@localhost:5432/diptrader

# Security
SECRET_KEY=your_flask_secret_key_here_use_openssl_rand
ENCRYPTION_KEY=your_encryption_key_from_step3

# App
FLASK_ENV=production
DEBUG=False
```

Generate SECRET_KEY:
```bash
python -c "import os; print(os.urandom(32).hex())"
```

## Step 5: Test Database Mode

### Create a test bot manually in database

```sql
-- Connect to database
psql -h localhost -U diptrader_user -d diptrader

-- Create test user
INSERT INTO users (email, password_hash, plan, max_bots)
VALUES ('test@example.com', 'hash_here', 'basic', 3);

-- Create test bot (you'll need to encrypt API keys first)
INSERT INTO bots (user_id, name, exchange, testnet, api_key_encrypted, api_secret_encrypted, status)
VALUES (1, 'Test Bot', 'phemex', true, 'encrypted_key_here', 'encrypted_secret_here', 'running');

-- Add trading pair
INSERT INTO trading_pairs (bot_id, symbol, side, leverage, ema_interval, automatic_mode)
VALUES (1, 'BTCUSDT', 'Long', 10, 1, true);
```

### Test bot execution in SaaS mode

```bash
# Set BOT_ID to use database config
export BOT_ID=1
export DATABASE_URL=postgresql://diptrader_user:password@localhost:5432/diptrader
export ENCRYPTION_KEY=your_key_here

# Run bot
dcabot-env/bin/python main.py
```

If it works → ✅ Database mode works!

## Next Steps

Once the above is working:

1. **Build Flask web app** (`saas/app.py`) - Week 2
2. **Create dashboard templates** - Week 3
3. **Deploy to camproute-server** - Week 4
4. **Setup nginx + SSL** - Week 4
5. **Test with real users** - Week 5

## Troubleshooting

**"ImportError: No module named psycopg2"**
```bash
pip install psycopg2-binary
```

**"DatabaseConfigSource: Database connection failed"**
- Check DATABASE_URL is correct
- Verify diptrader database exists
- Check user permissions

**"ENCRYPTION_KEY not set"**
- Run `python saas/security.py` to generate key
- Add to .env file
- Export in environment before running bot

**"Bot not found or not running"**
- Check bot ID exists in database
- Verify bot status is 'running'
- Check BOT_ID environment variable is set

## File Checklist

After Step 1-3, you should have:

```
dcabot/
├── main.py (UPDATED with config_loader)
├── config_loader.py (NEW)
├── saas/
│   ├── __init__.py (empty file)
│   ├── schema.sql (NEW)
│   └── security.py (NEW)
├── .env (contains your existing config)
└── ... (existing files unchanged)
```

Ready to start? Begin with Step 1! 🚀
