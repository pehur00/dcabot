# SaaS Migration Plan - Backward Compatible

## Overview

This plan ensures the existing bot remains fully functional while gradually building the SaaS platform. You can run the bot as-is while developing the web interface.

## Architecture: Hybrid Mode

```
┌─────────────────────────────────────────────────────────┐
│         Existing Bot (Standalone Mode)                  │
│    - Runs via cron job or Render cron                   │
│    - Uses .env file for config                          │
│    - Works exactly as before                            │
│    - ✅ BACKWARD COMPATIBLE                             │
└─────────────────────────────────────────────────────────┘
                          OR
┌─────────────────────────────────────────────────────────┐
│            New SaaS Platform (Web Mode)                  │
│    - Runs via web interface                             │
│    - Uses database for config                           │
│    - Multi-user support                                 │
│    - Same bot logic, different config source            │
└─────────────────────────────────────────────────────────┘
```

## Code Changes for Backward Compatibility

### 1. Make Bot Config Source Pluggable

**Current: main.py loads from .env**
```python
# main.py (current)
api_key = os.getenv('API_KEY')
api_secret = os.getenv('API_SECRET')
symbol_sides = os.getenv('SYMBOL', '')
```

**New: Support both .env AND database**
```python
# config_loader.py (NEW FILE)
import os
from typing import Optional, List, Tuple

class ConfigSource:
    """Abstract config source - can be .env or database"""
    def get_api_credentials(self) -> Tuple[str, str]:
        raise NotImplementedError

    def get_symbols(self) -> List[Tuple[str, str, bool]]:
        raise NotImplementedError

    def get_ema_interval(self) -> int:
        raise NotImplementedError

    def is_testnet(self) -> bool:
        raise NotImplementedError


class EnvConfigSource(ConfigSource):
    """Load from .env file (BACKWARD COMPATIBLE)"""
    def get_api_credentials(self):
        return os.getenv('API_KEY'), os.getenv('API_SECRET')

    def get_symbols(self):
        symbol_sides = os.getenv('SYMBOL', '')
        return parse_symbols(symbol_sides)  # Existing function

    def get_ema_interval(self):
        return int(os.getenv('EMA_INTERVAL', 1))

    def is_testnet(self):
        return os.getenv('TESTNET', 'False').lower() in ('true', '1', 't')


class DatabaseConfigSource(ConfigSource):
    """Load from database (NEW for SaaS)"""
    def __init__(self, bot_id: int, db_connection):
        self.bot_id = bot_id
        self.db = db_connection

    def get_api_credentials(self):
        bot = self.db.get_bot(self.bot_id)
        return decrypt(bot.api_key), decrypt(bot.api_secret)

    def get_symbols(self):
        pairs = self.db.get_trading_pairs(self.bot_id)
        return [(p.symbol, p.side, p.automatic_mode) for p in pairs]

    def get_ema_interval(self):
        pairs = self.db.get_trading_pairs(self.bot_id)
        return pairs[0].ema_interval if pairs else 1

    def is_testnet(self):
        bot = self.db.get_bot(self.bot_id)
        return bot.testnet
```

**Updated main.py (supports both modes)**
```python
# main.py (UPDATED - backward compatible)
import asyncio
import logging
import os
from pathlib import Path
from dotenv import load_dotenv
from config_loader import EnvConfigSource, DatabaseConfigSource

async def main():
    # Detect mode: if BOT_ID env var is set, use database, else use .env
    bot_id = os.getenv('BOT_ID')

    if bot_id:
        # SaaS mode: load from database
        from database import get_db_connection
        db = get_db_connection()
        config = DatabaseConfigSource(bot_id, db)
        logging.info(f"Running in SaaS mode for bot_id={bot_id}")
    else:
        # Standalone mode: load from .env (BACKWARD COMPATIBLE)
        env_path = Path(__file__).parent / '.env'
        if env_path.exists():
            load_dotenv(env_path)
        config = EnvConfigSource()
        logging.info("Running in standalone mode (.env)")

    # Rest of the code stays the same!
    api_key, api_secret = config.get_api_credentials()
    symbol_side_map = config.get_symbols()
    ema_interval = config.get_ema_interval()
    testnet = config.is_testnet()

    # ... existing bot logic unchanged ...
```

**Key Benefits**:
- ✅ Existing bot works WITHOUT any changes to .env
- ✅ New SaaS mode works by setting `BOT_ID` environment variable
- ✅ All strategy code remains identical
- ✅ Can test both modes side-by-side

### 2. Shared Core, Separate Entry Points

```
dcabot/
├── main.py                    # Standalone mode (existing, works as-is)
├── main_saas.py               # SaaS mode (new, calls same strategy)
├── config_loader.py           # NEW: Config abstraction
├── strategies/                # UNCHANGED
├── clients/                   # UNCHANGED
├── workflows/                 # UNCHANGED
└── saas/                      # NEW: SaaS-specific code
    ├── app.py                 # Flask web app
    ├── models.py              # Database models
    ├── routes/
    │   ├── auth.py
    │   ├── bots.py
    │   └── dashboard.py
    └── templates/
        └── ...
```

**Standalone usage (unchanged)**:
```bash
# Still works exactly as before!
dcabot-env/bin/python main.py
```

**SaaS usage (new)**:
```bash
# Web interface
dcabot-env/bin/python saas/app.py

# Execute specific bot (called by scheduler)
BOT_ID=123 dcabot-env/bin/python main.py
```

## Infrastructure: Using Your Existing Server

### 1. Database Setup on camproute-server

**Create new database on existing Postgres**:
```bash
ssh camproute-server

# Switch to postgres user
sudo -u postgres psql

# Create database and user
CREATE DATABASE dcabot;
CREATE USER dcabot WITH PASSWORD 'your_secure_password_here';
GRANT ALL PRIVILEGES ON DATABASE dcabot TO dcabot;

# Exit psql
\q
```

**Connection string for app**:
```bash
# .env on server
DATABASE_URL=postgresql://dcabot:your_secure_password_here@localhost:5432/dcabot
```

**Initialize schema**:
```bash
# On camproute-server
cd /var/www/dcabot-saas
source venv/bin/activate
python -c "from saas.models import init_db; init_db()"
```

### 2. Nginx Configuration (Following Your Pattern)

**Create nginx config for dcabot**:
```bash
ssh camproute-server
sudo nano /etc/nginx/sites-available/dcabot
```

**Config content** (following your camproute pattern):
```nginx
# /etc/nginx/sites-available/dcabot
server {
    server_name dcabot.yourdomain.com;  # Change to your domain

    # SaaS Web Interface
    location / {
        proxy_pass http://localhost:8000;  # Flask/FastAPI app
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;

        # Security headers
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-XSS-Protection "1; mode=block" always;
        add_header Referrer-Policy "no-referrer-when-downgrade" always;
    }

    # API endpoint (optional, if you want separate API subdomain)
    location /api/ {
        proxy_pass http://localhost:8000/api/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # CORS headers (if needed for API)
        add_header Access-Control-Allow-Origin "*" always;
        add_header Access-Control-Allow-Methods "GET, POST, PUT, DELETE, OPTIONS" always;
        add_header Access-Control-Allow-Headers "Authorization, Content-Type" always;
    }

    # SSL will be added by certbot (see next section)
    listen 80;
}
```

**Enable site**:
```bash
sudo ln -s /etc/nginx/sites-available/dcabot /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 3. Let's Encrypt SSL Setup (Using Your Pattern)

**Install certbot** (if not already installed):
```bash
ssh camproute-server
sudo apt update
sudo apt install certbot python3-certbot-nginx
```

**Generate SSL certificate**:
```bash
# This will automatically modify your nginx config
sudo certbot --nginx -d dcabot.yourdomain.com

# Follow prompts:
# - Enter email for renewal notifications
# - Agree to terms
# - Choose redirect HTTP to HTTPS (recommended: Yes)
```

**Auto-renewal** (already configured on your server):
```bash
# Check renewal cron job
sudo systemctl status certbot.timer

# Test renewal (dry run)
sudo certbot renew --dry-run
```

After certbot runs, your nginx config will look like:
```nginx
server {
    server_name dcabot.yourdomain.com;

    location / {
        proxy_pass http://localhost:8000;
        # ... proxy headers ...
    }

    listen 443 ssl; # managed by Certbot
    ssl_certificate /etc/letsencrypt/live/dcabot.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/dcabot.yourdomain.com/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;
}

server {
    if ($host = dcabot.yourdomain.com) {
        return 301 https://$host$request_uri;
    }

    listen 80;
    server_name dcabot.yourdomain.com;
    return 404;
}
```

### 4. Systemd Service for SaaS App

**Create service file**:
```bash
sudo nano /etc/systemd/system/dcabot-saas.service
```

**Service content**:
```ini
[Unit]
Description=DCA Bot SaaS Web Application
After=network.target postgresql.service
Requires=postgresql.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/var/www/dcabot-saas
Environment="PATH=/var/www/dcabot-saas/venv/bin"
Environment="DATABASE_URL=postgresql://dcabot:password@localhost:5432/dcabot"
Environment="SECRET_KEY=your_secret_key_here_generate_with_openssl_rand"
Environment="ENCRYPTION_KEY=your_encryption_key_here_for_api_keys"
ExecStart=/var/www/dcabot-saas/venv/bin/gunicorn -w 4 -b 127.0.0.1:8000 saas.app:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Enable and start**:
```bash
sudo systemctl daemon-reload
sudo systemctl enable dcabot-saas
sudo systemctl start dcabot-saas
sudo systemctl status dcabot-saas
```

### 5. Bot Scheduler Service

**Create scheduler service**:
```bash
sudo nano /etc/systemd/system/dcabot-scheduler.service
```

**Service content**:
```ini
[Unit]
Description=DCA Bot Scheduler (executes all active bots)
After=network.target postgresql.service dcabot-saas.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/var/www/dcabot-saas
Environment="PATH=/var/www/dcabot-saas/venv/bin"
Environment="DATABASE_URL=postgresql://dcabot:password@localhost:5432/dcabot"
ExecStart=/var/www/dcabot-saas/venv/bin/python saas/scheduler.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Scheduler script** (`saas/scheduler.py`):
```python
#!/usr/bin/env python3
"""
Scheduler that runs all active bots every 5 minutes
"""
import time
import subprocess
import logging
from saas.models import get_db, Bot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def execute_bot(bot_id: int):
    """Execute a single bot by calling main.py with BOT_ID"""
    try:
        result = subprocess.run(
            ['python', 'main.py'],
            env={'BOT_ID': str(bot_id)},
            capture_output=True,
            text=True,
            timeout=120  # 2 min timeout per bot
        )

        if result.returncode == 0:
            logger.info(f"Bot {bot_id} executed successfully")
        else:
            logger.error(f"Bot {bot_id} failed: {result.stderr}")

    except subprocess.TimeoutExpired:
        logger.error(f"Bot {bot_id} execution timeout")
    except Exception as e:
        logger.error(f"Bot {bot_id} error: {e}")

def main():
    logger.info("DCA Bot Scheduler started")

    while True:
        try:
            # Get all active bots from database
            db = get_db()
            active_bots = db.query(Bot).filter(Bot.status == 'running').all()

            logger.info(f"Executing {len(active_bots)} active bots")

            for bot in active_bots:
                execute_bot(bot.id)

            # Wait 5 minutes before next cycle
            time.sleep(300)

        except Exception as e:
            logger.error(f"Scheduler error: {e}")
            time.sleep(60)  # Wait 1 min on error

if __name__ == '__main__':
    main()
```

**Enable scheduler**:
```bash
sudo systemctl enable dcabot-scheduler
sudo systemctl start dcabot-scheduler
```

## Security Hardening for Public Usage

### 1. Database Security

**Restrict PostgreSQL access**:
```bash
# Edit pg_hba.conf
sudo nano /etc/postgresql/14/main/pg_hba.conf

# Ensure local connections only
# Add this line (if not present):
local   dcabot      dcabot                                  scram-sha-256
host    dcabot      dcabot      127.0.0.1/32                scram-sha-256

# Reload PostgreSQL
sudo systemctl reload postgresql
```

**Regular backups**:
```bash
# Create backup script
sudo nano /usr/local/bin/backup-dcabot.sh
```

```bash
#!/bin/bash
# /usr/local/bin/backup-dcabot.sh
BACKUP_DIR="/var/backups/dcabot"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup database
sudo -u postgres pg_dump dcabot > "$BACKUP_DIR/dcabot_$DATE.sql"

# Keep only last 7 days of backups
find $BACKUP_DIR -name "dcabot_*.sql" -mtime +7 -delete

echo "Backup completed: dcabot_$DATE.sql"
```

```bash
chmod +x /usr/local/bin/backup-dcabot.sh

# Add to crontab (daily at 2 AM)
sudo crontab -e
# Add line:
0 2 * * * /usr/local/bin/backup-dcabot.sh >> /var/log/dcabot-backup.log 2>&1
```

### 2. Application Security

**Environment variables** (never commit these):
```bash
# /var/www/dcabot-saas/.env
DATABASE_URL=postgresql://dcabot:secure_password@localhost:5432/dcabot
SECRET_KEY=$(openssl rand -hex 32)  # Flask session signing
ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
```

**API Key Encryption** (`saas/security.py`):
```python
import os
from cryptography.fernet import Fernet

# Load from environment (stored securely)
cipher = Fernet(os.getenv('ENCRYPTION_KEY').encode())

def encrypt_api_key(api_key: str) -> str:
    """Encrypt user's exchange API key before storing in DB"""
    return cipher.encrypt(api_key.encode()).decode()

def decrypt_api_key(encrypted: str) -> str:
    """Decrypt user's exchange API key when needed for execution"""
    return cipher.decrypt(encrypted.encode()).decode()
```

**Password Hashing** (`saas/auth.py`):
```python
from werkzeug.security import generate_password_hash, check_password_hash

def hash_password(password: str) -> str:
    # bcrypt with salt, cost factor 12
    return generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)

def verify_password(password: str, hash: str) -> bool:
    return check_password_hash(hash, password)
```

**Rate Limiting** (Flask-Limiter):
```python
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"  # Or use Redis for production
)

@app.route('/api/login', methods=['POST'])
@limiter.limit("5 per minute")  # Prevent brute force
def login():
    # ... login logic ...
    pass
```

### 3. Firewall Configuration

**UFW setup**:
```bash
ssh camproute-server

# Check current status
sudo ufw status

# Allow only necessary ports
sudo ufw allow 22/tcp      # SSH
sudo ufw allow 80/tcp      # HTTP (redirects to HTTPS)
sudo ufw allow 443/tcp     # HTTPS

# Deny everything else by default
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Enable firewall
sudo ufw enable
```

### 4. Nginx Security Headers

**Additional security headers** (add to nginx config):
```nginx
# /etc/nginx/sites-available/dcabot
server {
    # ... existing config ...

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' https://unpkg.com https://cdn.jsdelivr.net https://cdn.tailwindcss.com; style-src 'self' 'unsafe-inline'; img-src 'self' data:;" always;

    # Hide nginx version
    server_tokens off;

    # Limit request size (prevent large payload attacks)
    client_max_body_size 10M;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=login_limit:10m rate=5r/m;

    location /api/login {
        limit_req zone=login_limit burst=3 nodelay;
        proxy_pass http://localhost:8000;
        # ... other proxy settings ...
    }
}
```

### 5. Application Monitoring & Logs

**Structured logging**:
```python
# saas/app.py
import logging
import json
from datetime import datetime

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        if hasattr(record, 'user_id'):
            log_data['user_id'] = record.user_id
        return json.dumps(log_data)

# Configure logging
handler = logging.FileHandler('/var/log/dcabot-saas/app.log')
handler.setFormatter(JSONFormatter())
app.logger.addHandler(handler)
app.logger.setLevel(logging.INFO)
```

**Log rotation**:
```bash
# /etc/logrotate.d/dcabot-saas
/var/log/dcabot-saas/*.log {
    daily
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 www-data www-data
    sharedscripts
    postrotate
        systemctl reload dcabot-saas
    endscript
}
```

**Health check endpoint**:
```python
@app.route('/health')
def health():
    """Health check for monitoring (e.g., UptimeRobot)"""
    try:
        # Check database connection
        db.session.execute('SELECT 1')

        # Check active bots
        active_bots = Bot.query.filter_by(status='running').count()

        return {
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'active_bots': active_bots,
            'database': 'connected'
        }, 200
    except Exception as e:
        return {
            'status': 'unhealthy',
            'error': str(e)
        }, 500
```

### 6. Fail2ban for Brute Force Protection

**Install and configure fail2ban**:
```bash
sudo apt install fail2ban

# Create filter for DCA bot
sudo nano /etc/fail2ban/filter.d/dcabot.conf
```

```ini
# /etc/fail2ban/filter.d/dcabot.conf
[Definition]
failregex = ^.*"Failed login attempt".*"ip":"<HOST>".*$
ignoreregex =
```

```bash
# Configure jail
sudo nano /etc/fail2ban/jail.local
```

```ini
[dcabot]
enabled = true
port = http,https
filter = dcabot
logpath = /var/log/dcabot-saas/app.log
maxretry = 5
bantime = 3600
findtime = 600
```

```bash
sudo systemctl restart fail2ban
```

## Migration Strategy: Step-by-Step

### Phase 1: Keep Running Standalone (Week 1)
- ✅ Bot continues running via cron/Render as-is
- 📝 Build SaaS infrastructure in parallel
- 📝 Create database schema
- 📝 Build Flask app skeleton

**During this phase**: No changes to production bot!

### Phase 2: Add Config Abstraction (Week 2)
- 📝 Add `config_loader.py` with `EnvConfigSource`
- 📝 Update `main.py` to use config abstraction
- ✅ Test standalone bot still works identically
- 📝 Add `DatabaseConfigSource` (not used yet)

**During this phase**: Standalone bot updated but still works the same way

### Phase 3: Build Web Interface (Week 3)
- 📝 Build auth, dashboard, bot creation
- 📝 Deploy to camproute-server alongside existing bot
- 📝 Create your first bot via web interface
- ✅ Test bot execution via `BOT_ID=1 python main.py`

**During this phase**: Both modes coexist!

### Phase 4: Run Both in Parallel (Week 4)
- ✅ Standalone bot runs your personal trading
- ✅ SaaS bots run for test users
- 📝 Monitor both for 1 week
- 📝 Compare results, fix any differences

### Phase 5: Full Migration (Week 5+)
- 📝 Migrate your personal bot config to database
- 📝 Disable standalone cron job
- 📝 Use web interface for all bots
- 🎉 Invite first real users!

## Cost Analysis

### Using camproute-server (Your Existing Server)

**Current costs**: Already paying for the droplet
**Additional costs for DCA Bot SaaS**:
- $0 - Uses existing PostgreSQL instance
- $0 - Uses existing nginx/SSL setup
- $0 - Shares server resources

**Only new cost**: Domain name (if not using subdomain)
- Option 1: `dcabot.yourdomain.com` (subdomain) = $0
- Option 2: New domain `dcabot.com` = ~$12/year

**Resource usage on camproute-server**:
- Database: ~500MB - 2GB (depends on trade history)
- CPU: Minimal (bots run every 5 min, Flask is lightweight)
- RAM: ~200-500MB (Flask app + scheduler)
- Disk: ~1GB (app + logs + backups)

**Will it fit?** Check current usage:
```bash
ssh camproute-server
df -h           # Disk usage
free -h         # RAM usage
top             # CPU usage
```

If droplet is getting full, consider:
- Upgrading droplet ($12 → $24/month)
- Or using separate droplet for DCA Bot ($12/month)

**Breakeven**: Still just 2-3 paying users! 🎉

## Testing Checklist

### Before Going Public

**Standalone bot testing**:
- [ ] Existing bot runs without issues
- [ ] All trades execute correctly
- [ ] Notifications work (Telegram)
- [ ] No regressions introduced

**SaaS mode testing**:
- [ ] User registration works
- [ ] Login/logout works
- [ ] Bot creation via web interface
- [ ] Bot execution via `BOT_ID` env var
- [ ] Trades logged to database
- [ ] Dashboard shows correct data
- [ ] SSL certificate works
- [ ] Health check endpoint responds

**Security testing**:
- [ ] Cannot access other users' bots
- [ ] API keys encrypted in database
- [ ] Passwords hashed correctly
- [ ] Rate limiting works
- [ ] SQL injection attempts blocked
- [ ] XSS attempts blocked
- [ ] HTTPS enforced (HTTP redirects)

**Load testing** (optional):
```bash
# Use Apache Bench to test
ab -n 1000 -c 10 https://dcabot.yourdomain.com/health
```

## Rollback Plan

If something goes wrong:

**Immediate rollback**:
```bash
ssh camproute-server

# Stop SaaS services
sudo systemctl stop dcabot-saas
sudo systemctl stop dcabot-scheduler

# Re-enable standalone bot cron
crontab -e
# Uncomment the original cron line
```

**Database rollback**:
```bash
# Restore from backup
psql dcabot < /var/backups/dcabot/dcabot_YYYYMMDD_HHMMSS.sql
```

**Nginx rollback**:
```bash
# Disable SaaS site
sudo rm /etc/nginx/sites-enabled/dcabot
sudo systemctl reload nginx
```

**Your standalone bot keeps working** - it never stopped! ✅

## Summary

**Key Advantages of This Approach**:
1. ✅ Zero downtime - standalone bot keeps running
2. ✅ Gradual migration - test at each step
3. ✅ Backward compatible - can always revert
4. ✅ Minimal cost - uses existing infrastructure
5. ✅ Same bot logic - no strategy changes
6. ✅ Production-ready security with Let's Encrypt
7. ✅ Battle-tested pattern (following your camproute setup)

**Timeline**:
- Week 1: Infrastructure setup
- Week 2: Backend development
- Week 3: Frontend development
- Week 4: Testing both modes
- Week 5: Soft launch to friends
- Week 6+: Public launch

**Next steps**:
1. Review this plan
2. Choose domain name (subdomain or new)
3. Start with Phase 1 (build SaaS alongside existing bot)
4. Test thoroughly before migrating your personal trading

Ready to start building? 🚀
