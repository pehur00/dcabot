# Minimal SaaS Plan - Single Server Deployment

## Overview

A lightweight, single-server SaaS version of the DCA bot that can run on:
- **Render.com** (Web Service + PostgreSQL)
- **Digital Ocean Droplet** ($12-24/month)
- **Railway.app** (All-in-one)

**Goal**: Get to market quickly with minimal infrastructure complexity and costs.

## Simplified Architecture

```
┌─────────────────────────────────────────────────┐
│           Single Server (Render/DO)             │
│                                                 │
│  ┌──────────────────────────────────────────┐  │
│  │   Flask/FastAPI Web App (Port 8000)      │  │
│  │   - REST API                              │  │
│  │   - JWT Authentication                    │  │
│  │   - Bot Management                        │  │
│  │   - Static Frontend (htmx/Alpine.js)     │  │
│  └──────────────────────────────────────────┘  │
│                      │                          │
│  ┌──────────────────────────────────────────┐  │
│  │   SQLite / PostgreSQL                    │  │
│  │   - All data in one DB                   │  │
│  └──────────────────────────────────────────┘  │
│                      │                          │
│  ┌──────────────────────────────────────────┐  │
│  │   APScheduler (Background Jobs)          │  │
│  │   - Runs in same process                 │  │
│  │   - Executes all bots every 5 min        │  │
│  └──────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

## Tech Stack (Minimal)

### Backend
- **Flask** (lightweight, simple) or **FastAPI** (if you prefer async)
- **SQLAlchemy** (ORM)
- **APScheduler** (in-process background jobs, no Celery needed)
- **Flask-Login** or **JWT** (authentication)
- **SQLite** (development) → **PostgreSQL** (production on Render)

### Frontend
- **htmx** + **Alpine.js** (no React build step, server-rendered)
- **TailwindCSS** (via CDN)
- **Chart.js** (for performance charts)

### Payment (Optional for v1)
- Start with **manual subscriptions** (you approve users)
- Add Stripe later when you have paying customers

## Simplified Database Schema

```sql
-- Minimal schema - 5 core tables

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    plan VARCHAR(20) DEFAULT 'free', -- free, basic, pro
    max_bots INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE bots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id),
    name VARCHAR(100) NOT NULL,
    exchange VARCHAR(20) NOT NULL, -- phemex, bybit
    testnet BOOLEAN DEFAULT TRUE,
    api_key TEXT NOT NULL, -- encrypted
    api_secret TEXT NOT NULL, -- encrypted
    status VARCHAR(20) DEFAULT 'stopped', -- running, stopped, error
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE trading_pairs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bot_id INTEGER REFERENCES bots(id),
    symbol VARCHAR(20) NOT NULL, -- BTCUSDT
    side VARCHAR(10) NOT NULL, -- Long, Short
    leverage INTEGER DEFAULT 10,
    config TEXT, -- JSON config (strategy params)
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bot_id INTEGER REFERENCES bots(id),
    symbol VARCHAR(20),
    action VARCHAR(20), -- OPENED, ADDED, REDUCED, CLOSED
    quantity DECIMAL(20,8),
    price DECIMAL(20,8),
    pnl DECIMAL(20,8),
    balance_after DECIMAL(20,8),
    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    details TEXT -- JSON with full details
);

CREATE TABLE bot_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bot_id INTEGER REFERENCES bots(id),
    level VARCHAR(10), -- INFO, WARNING, ERROR
    message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Minimal File Structure

```
dcabot-saas/
├── app.py                      # Main Flask app + scheduler
├── models.py                   # SQLAlchemy models
├── auth.py                     # Login/register routes
├── bots.py                     # Bot management routes
├── executor.py                 # Bot execution logic (reuses existing code)
├── requirements.txt
├── templates/
│   ├── base.html              # Base layout with htmx/Alpine
│   ├── login.html
│   ├── dashboard.html         # Bot overview
│   ├── bot_detail.html        # Single bot view
│   └── bot_create.html        # Create/edit bot
├── static/
│   └── style.css              # Minimal custom CSS
├── strategies/                # Copy from existing bot
│   └── MartingaleTradingStrategy.py
├── clients/                   # Copy from existing bot
│   ├── PhemexClient.py
│   └── BybitClient.py
└── migrations/                # Alembic for DB migrations
```

## Implementation Plan (Simplified)

### Week 1: Core Backend + Auth

**Day 1-2: Project Setup**
```bash
# Create new Flask app
flask init
pip install flask flask-sqlalchemy flask-login apscheduler cryptography

# Database models (models.py)
# - User, Bot, TradingPair, Trade, BotLog
```

**Day 3-4: Authentication**
```python
# auth.py
@app.route('/register', methods=['GET', 'POST'])
def register():
    # Simple form, create user, hash password
    pass

@app.route('/login', methods=['GET', 'POST'])
def login():
    # Check credentials, create session
    pass

@app.route('/logout')
def logout():
    pass
```

**Day 5: Bot CRUD**
```python
# bots.py
@app.route('/bots')
@login_required
def list_bots():
    # Show user's bots
    pass

@app.route('/bots/create', methods=['GET', 'POST'])
@login_required
def create_bot():
    # Form to create bot with API keys
    # Encrypt and save
    pass

@app.route('/bots/<int:bot_id>')
@login_required
def bot_detail(bot_id):
    # Show trades, performance, logs
    pass
```

### Week 2: Bot Execution Integration

**Copy Existing Bot Code**
```bash
# Copy these folders from existing bot
cp -r strategies/ dcabot-saas/strategies/
cp -r clients/ dcabot-saas/clients/
cp -r indicators/ dcabot-saas/indicators/
cp -r utils/ dcabot-saas/utils/
```

**Create Multi-User Executor**
```python
# executor.py
from strategies.MartingaleTradingStrategy import MartingaleTradingStrategy
from clients.PhemexClient import PhemexClient

class BotExecutor:
    def __init__(self, bot):
        self.bot = bot
        self.api_key = decrypt(bot.api_key)
        self.api_secret = decrypt(bot.api_secret)

    def execute(self):
        """Execute strategy for this bot's trading pairs"""
        client = PhemexClient(
            self.api_key,
            self.api_secret,
            logger=self.get_logger(),
            testnet=self.bot.testnet
        )

        strategy = MartingaleTradingStrategy(client, logger, notifier=None)

        for pair in self.bot.trading_pairs:
            if not pair.is_active:
                continue

            try:
                # Load config from pair.config JSON
                config = json.loads(pair.config)

                # Execute strategy (copied from main.py)
                result = strategy.manage_position(
                    symbol=pair.symbol,
                    pos_side=pair.side,
                    # ... other params
                )

                # Log result to database
                self.log_execution(pair, result)

            except Exception as e:
                # Log error to database
                self.log_error(pair, str(e))

    def log_execution(self, pair, result):
        # Save to bot_logs table
        log = BotLog(
            bot_id=self.bot.id,
            level='INFO',
            message=f'{pair.symbol}: {result}'
        )
        db.session.add(log)
        db.session.commit()

    def log_error(self, pair, error):
        log = BotLog(
            bot_id=self.bot.id,
            level='ERROR',
            message=f'{pair.symbol}: {error}'
        )
        db.session.add(log)
        db.session.commit()
```

**Setup Scheduler**
```python
# app.py
from apscheduler.schedulers.background import BackgroundScheduler
from executor import BotExecutor

scheduler = BackgroundScheduler()

def execute_all_active_bots():
    """Run every 5 minutes - executes all active bots"""
    bots = Bot.query.filter_by(status='running').all()

    for bot in bots:
        try:
            executor = BotExecutor(bot)
            executor.execute()
        except Exception as e:
            # Log error, update bot status if needed
            app.logger.error(f'Bot {bot.id} execution failed: {e}')

# Schedule to run every 5 minutes
scheduler.add_job(
    execute_all_active_bots,
    'interval',
    minutes=5,
    id='bot_executor'
)

scheduler.start()

if __name__ == '__main__':
    app.run()
```

### Week 3: Frontend Dashboard

**Simple htmx Dashboard**
```html
<!-- templates/dashboard.html -->
<!DOCTYPE html>
<html>
<head>
    <title>DCA Bot Dashboard</title>
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
    <script src="https://unpkg.com/alpinejs@3.13.3"></script>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body class="bg-gray-100">
    <div class="container mx-auto px-4 py-8">
        <h1 class="text-3xl font-bold mb-6">My Bots</h1>

        <!-- Bot Cards -->
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {% for bot in bots %}
            <div class="bg-white rounded-lg shadow p-6">
                <div class="flex justify-between items-start mb-4">
                    <h3 class="text-xl font-semibold">{{ bot.name }}</h3>
                    <span class="px-2 py-1 rounded text-sm
                        {% if bot.status == 'running' %}bg-green-100 text-green-800
                        {% elif bot.status == 'stopped' %}bg-gray-100 text-gray-800
                        {% else %}bg-red-100 text-red-800{% endif %}">
                        {{ bot.status }}
                    </span>
                </div>

                <p class="text-gray-600 mb-2">{{ bot.exchange }}</p>
                <p class="text-sm text-gray-500 mb-4">
                    {{ bot.trading_pairs|length }} trading pairs
                </p>

                <div class="flex gap-2">
                    <a href="/bots/{{ bot.id }}" class="btn btn-primary">View</a>

                    {% if bot.status == 'stopped' %}
                    <button hx-post="/bots/{{ bot.id }}/start"
                            hx-swap="outerHTML"
                            class="btn btn-success">Start</button>
                    {% else %}
                    <button hx-post="/bots/{{ bot.id }}/stop"
                            hx-swap="outerHTML"
                            class="btn btn-warning">Stop</button>
                    {% endif %}
                </div>
            </div>
            {% endfor %}
        </div>

        <a href="/bots/create" class="btn btn-primary mt-6">+ Create New Bot</a>
    </div>
</body>
</html>
```

**Bot Detail Page**
```html
<!-- templates/bot_detail.html -->
<div class="container mx-auto px-4 py-8">
    <h1 class="text-3xl font-bold mb-6">{{ bot.name }}</h1>

    <!-- Status and Actions -->
    <div class="bg-white rounded-lg shadow p-6 mb-6">
        <div class="flex justify-between items-center">
            <div>
                <p class="text-gray-600">Status: <span class="font-semibold">{{ bot.status }}</span></p>
                <p class="text-gray-600">Exchange: {{ bot.exchange }}</p>
            </div>
            <div class="flex gap-2">
                <button hx-post="/bots/{{ bot.id }}/start">Start</button>
                <button hx-post="/bots/{{ bot.id }}/stop">Stop</button>
            </div>
        </div>
    </div>

    <!-- Performance Chart -->
    <div class="bg-white rounded-lg shadow p-6 mb-6">
        <h2 class="text-xl font-semibold mb-4">Balance History</h2>
        <canvas id="balanceChart"></canvas>
    </div>

    <!-- Recent Trades -->
    <div class="bg-white rounded-lg shadow p-6">
        <h2 class="text-xl font-semibold mb-4">Recent Trades</h2>
        <table class="w-full">
            <thead>
                <tr>
                    <th>Time</th>
                    <th>Symbol</th>
                    <th>Action</th>
                    <th>Price</th>
                    <th>PnL</th>
                </tr>
            </thead>
            <tbody>
                {% for trade in trades %}
                <tr>
                    <td>{{ trade.executed_at|format_datetime }}</td>
                    <td>{{ trade.symbol }}</td>
                    <td>{{ trade.action }}</td>
                    <td>${{ trade.price }}</td>
                    <td class="{% if trade.pnl > 0 %}text-green-600{% else %}text-red-600{% endif %}">
                        ${{ trade.pnl }}
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</div>

<script>
// Simple Chart.js integration
const ctx = document.getElementById('balanceChart');
new Chart(ctx, {
    type: 'line',
    data: {
        labels: {{ trade_dates|tojson }},
        datasets: [{
            label: 'Balance',
            data: {{ balance_history|tojson }},
            borderColor: 'rgb(75, 192, 192)',
            tension: 0.1
        }]
    }
});
</script>
```

### Week 4: Deployment + Polish

**Deployment to Render**
```yaml
# render.yaml
services:
  - type: web
    name: dcabot-saas
    env: python
    buildCommand: "pip install -r requirements.txt"
    startCommand: "gunicorn app:app"
    envVars:
      - key: PYTHON_VERSION
        value: 3.11.0
      - key: SECRET_KEY
        generateValue: true
      - key: DATABASE_URL
        fromDatabase:
          name: dcabot-db
          property: connectionString

databases:
  - name: dcabot-db
    databaseName: dcabot
    user: dcabot
```

**Or Digital Ocean Droplet**
```bash
# Deploy to DO (Ubuntu 22.04)
ssh root@your-droplet-ip

# Install dependencies
apt update
apt install python3 python3-pip postgresql nginx

# Clone repo
git clone https://github.com/yourusername/dcabot-saas.git
cd dcabot-saas

# Setup virtualenv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Setup PostgreSQL
sudo -u postgres createdb dcabot
sudo -u postgres createuser dcabot

# Run migrations
flask db upgrade

# Setup systemd service
cat > /etc/systemd/system/dcabot.service <<EOF
[Unit]
Description=DCA Bot SaaS
After=network.target

[Service]
User=root
WorkingDirectory=/root/dcabot-saas
Environment="PATH=/root/dcabot-saas/venv/bin"
ExecStart=/root/dcabot-saas/venv/bin/gunicorn -w 4 -b 0.0.0.0:8000 app:app

[Install]
WantedBy=multi-user.target
EOF

systemctl enable dcabot
systemctl start dcabot

# Setup Nginx reverse proxy
cat > /etc/nginx/sites-available/dcabot <<EOF
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
    }
}
EOF

ln -s /etc/nginx/sites-available/dcabot /etc/nginx/sites-enabled/
systemctl restart nginx

# SSL with Let's Encrypt
apt install certbot python3-certbot-nginx
certbot --nginx -d yourdomain.com
```

## Subscription Plans (Simplified)

### Free Tier
- 1 bot
- Testnet only
- 2 trading pairs
- Manual approval required

### Basic ($19/month)
- 3 bots
- Testnet + Mainnet
- 5 trading pairs per bot
- Email support

### Pro ($49/month)
- 10 bots
- Unlimited trading pairs
- Priority support
- Telegram notifications

**Implementation**: Simple boolean check in code
```python
@app.route('/bots/create', methods=['POST'])
@login_required
def create_bot():
    user = current_user

    # Check bot limit
    existing_bots = Bot.query.filter_by(user_id=user.id).count()

    if existing_bots >= user.max_bots:
        flash('Bot limit reached. Please upgrade your plan.')
        return redirect('/account/upgrade')

    # Create bot...
```

**Billing**: Manual for now (Stripe later)
```python
# Admin manually updates user:
# UPDATE users SET plan='pro', max_bots=10 WHERE email='user@example.com';
```

## Cost Breakdown

### Render (Recommended for beginners)
- **Web Service**: $7/month (Starter plan)
- **PostgreSQL**: $7/month (Starter plan)
- **Total**: $14/month

### Digital Ocean
- **Droplet**: $12/month (2GB RAM, 1 CPU)
- **Managed PostgreSQL**: $15/month (optional, can use on-droplet)
- **Total**: $12-27/month

### Breakeven
- At 2 paid users (Basic): $38 revenue vs $14 costs
- **Immediate profitability** with just 2-3 users!

## Feature Roadmap

### MVP (4 weeks)
- [x] User registration/login
- [x] Create/edit bots
- [x] Add trading pairs
- [x] Bot execution (every 5 min)
- [x] Trade history
- [x] Basic dashboard

### Version 1.1 (2-3 weeks after launch)
- [ ] Stripe integration (automated billing)
- [ ] Email notifications
- [ ] Telegram notifications
- [ ] Bot performance charts
- [ ] Backtest integration

### Version 1.2 (1-2 months after launch)
- [ ] Mobile-responsive design improvements
- [ ] Copy trading (follow other users)
- [ ] More exchanges (Binance, Kraken)
- [ ] API for advanced users

## Security (Simplified but Safe)

1. **Password Hashing**: bcrypt with salt
2. **API Key Encryption**: Fernet (symmetric encryption)
   ```python
   from cryptography.fernet import Fernet

   # Store encryption key in environment variable
   cipher = Fernet(os.getenv('ENCRYPTION_KEY'))

   def encrypt_api_key(api_key):
       return cipher.encrypt(api_key.encode()).decode()

   def decrypt_api_key(encrypted):
       return cipher.decrypt(encrypted.encode()).decode()
   ```
3. **HTTPS**: Let's Encrypt (free)
4. **Session Security**: Flask-Login with secure cookies
5. **SQL Injection**: SQLAlchemy ORM (parameterized queries)

## Monitoring (Keep It Simple)

1. **Logs**: Just use `app.logger` → save to file
   ```python
   import logging
   logging.basicConfig(filename='app.log', level=logging.INFO)
   ```

2. **Health Check**: Simple endpoint for uptime monitoring
   ```python
   @app.route('/health')
   def health():
       return {'status': 'ok', 'bots_running': Bot.query.filter_by(status='running').count()}
   ```

3. **UptimeRobot**: Free monitoring (checks /health every 5 min)

4. **Sentry**: Free tier for error tracking (optional)

## Launch Checklist

- [ ] Basic functionality tested
- [ ] Deploy to Render/DO
- [ ] Domain name connected
- [ ] SSL certificate active
- [ ] Create 3-5 test accounts
- [ ] Run bots on testnet for 1 week
- [ ] Document common issues
- [ ] Create simple landing page
- [ ] Soft launch to friends/small community
- [ ] Collect feedback
- [ ] Add Stripe (when first user asks to pay)

## Summary: Why This Approach?

✅ **Fast to market**: 4 weeks vs 22 weeks
✅ **Low cost**: $14/month vs $500/month
✅ **Simple to maintain**: One codebase, one server
✅ **Easy to debug**: All logs in one place
✅ **Scalable**: Can handle 50-100 users easily
✅ **No DevOps complexity**: No Kubernetes, no microservices
✅ **Iterate quickly**: Make changes and deploy in minutes

**When to upgrade to complex architecture?**
- When you have 100+ active paying users
- When single server hits performance limits
- When you need geographic distribution
- Not before! 🚀
