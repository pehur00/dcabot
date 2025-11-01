# Render Deployment Guide - SaaS Solution

## Why Render for SaaS?

✅ **You're already using it** - Bot cron job runs there
✅ **Simple deployment** - Git push = automatic deploy
✅ **Free SSL** - Automatic HTTPS
✅ **Easy environment management** - Web UI for env vars
✅ **Background workers** - Built-in support
✅ **Auto-scaling** - Handles traffic spikes

**Cost**: $7/month (Starter web service) + $0 (using your DO PostgreSQL)

## Architecture: Render + Digital Ocean PostgreSQL

```
┌─────────────────────────────────────────────────────┐
│                   Render.com                        │
│                                                     │
│  ┌──────────────────────────────────────────────┐  │
│  │  Web Service (dcabot-saas-web)               │  │
│  │  - Flask app on port 8000                    │  │
│  │  - Handles HTTP requests                     │  │
│  │  - Auto-deploy from GitHub                   │  │
│  │  - Free SSL (dcabot.onrender.com)           │  │
│  └──────────────────────────────────────────────┘  │
│                      │                              │
│  ┌──────────────────────────────────────────────┐  │
│  │  Background Worker (dcabot-scheduler)        │  │
│  │  - Runs bot executor every 5 minutes         │  │
│  │  - Same repo as web service                  │  │
│  │  - Different start command                   │  │
│  └──────────────────────────────────────────────┘  │
│                      │                              │
│  ┌──────────────────────────────────────────────┐  │
│  │  Cron Job (existing standalone bot)         │  │
│  │  - Your current bot (keep running!)          │  │
│  │  - Runs every 5 minutes                      │  │
│  │  - Uses .env config (backward compatible)    │  │
│  └──────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
                          │
                          ▼ (internet connection)
┌─────────────────────────────────────────────────────┐
│     Digital Ocean Managed PostgreSQL                │
│                                                     │
│  Host: private-dbaas-db-...ondigitalocean.com      │
│  Port: 25060                                       │
│  Database: diptrader                               │
│  SSL: Required                                     │
│  Access: Public (with IP allowlist or open)       │
└─────────────────────────────────────────────────────┘
```

## Step 1: Make PostgreSQL Publicly Accessible

Your DO managed PostgreSQL is currently private. You need to allow external connections.

### Option A: Allow All IPs (Easiest for Render)

1. Go to Digital Ocean Dashboard
2. Navigate to **Databases** → **diptrader** (or your database cluster)
3. Click **Settings** tab
4. Scroll to **Trusted Sources**
5. Click **Edit**
6. Add **0.0.0.0/0** (allow all IPs)
   - Note: This is safe because PostgreSQL still requires username/password + SSL
7. Click **Save**

**Connection string for Render**:
```
postgresql://diptrader:YOUR_PASSWORD@private-dbaas-db-10215807-do-user-15659652-0.e.db.ondigitalocean.com:25060/diptrader?sslmode=require
```

### Option B: Allowlist Render IPs (More Secure, but complex)

Render doesn't provide static IPs on the free/starter plan. You'd need to:
- Upgrade to Render's paid plan with static IPs
- Add those IPs to DO's allowlist

**Recommendation**: Start with Option A. PostgreSQL is still secure with password + SSL.

### Test Connection from Your Local Machine

```bash
# Install psql client if needed
brew install postgresql  # macOS
# or: sudo apt install postgresql-client  # Ubuntu

# Test connection
psql "postgresql://diptrader:YOUR_PASSWORD@private-dbaas-db-10215807-do-user-15659652-0.e.db.ondigitalocean.com:25060/diptrader?sslmode=require"

# If successful, you'll see:
# diptrader=>
```

## Step 2: Prepare Repository for Render

### Create render.yaml (Blueprint)

Create `render.yaml` in your repo root:

```yaml
# render.yaml - Render Blueprint for DCA Bot SaaS
services:
  # Web Service (Flask dashboard)
  - type: web
    name: dcabot-saas-web
    env: python
    region: oregon  # or frankfurt (closer to DO database)
    plan: starter  # $7/month
    branch: main  # or feature/saas-transformation
    buildCommand: |
      pip install --upgrade pip
      pip install -r requirements.txt -r requirements-saas.txt
    startCommand: gunicorn -w 4 -b 0.0.0.0:$PORT saas.app:app
    healthCheckPath: /health
    envVars:
      - key: PYTHON_VERSION
        value: 3.11.0
      - key: DATABASE_URL
        sync: false  # Will set manually in Render dashboard
      - key: SECRET_KEY
        generateValue: true
      - key: ENCRYPTION_KEY
        sync: false  # Will set manually
      - key: FLASK_ENV
        value: production
      - key: DEBUG
        value: false

  # Background Worker (Bot Scheduler)
  - type: worker
    name: dcabot-scheduler
    env: python
    region: oregon
    plan: starter  # $7/month
    branch: main
    buildCommand: |
      pip install --upgrade pip
      pip install -r requirements.txt -r requirements-saas.txt
    startCommand: python saas/scheduler.py
    envVars:
      - key: PYTHON_VERSION
        value: 3.11.0
      - key: DATABASE_URL
        sync: false
      - key: ENCRYPTION_KEY
        sync: false

  # Existing Cron Job (Standalone Bot - keep as-is!)
  # This is your current bot running from main.py
  # No changes needed - continues to work with .env
```

**Cost Breakdown**:
- Web Service: $7/month (serves dashboard)
- Worker: $7/month (runs bots every 5 min)
- **Total: $14/month** (same as our original estimate!)

### Alternative: Cron Job Instead of Worker (Save $7/month)

If you want to save money, use a Render Cron Job instead of a background worker:

```yaml
services:
  - type: web
    name: dcabot-saas-web
    # ... same as above ...

  # Cron Job (runs bot executor every 5 minutes)
  - type: cron
    name: dcabot-scheduler-cron
    env: python
    region: oregon
    schedule: "*/5 * * * *"  # Every 5 minutes
    branch: main
    buildCommand: |
      pip install --upgrade pip
      pip install -r requirements.txt -r requirements-saas.txt
    startCommand: python saas/execute_all_bots.py
    envVars:
      - key: DATABASE_URL
        sync: false
      - key: ENCRYPTION_KEY
        sync: false
```

**With Cron Job option: Only $7/month total!** 🎉

## Step 3: Create Render-Specific Files

### Create Procfile (alternative to render.yaml)

If you prefer Procfile instead of render.yaml:

```
# Procfile
web: gunicorn -w 4 -b 0.0.0.0:$PORT saas.app:app
worker: python saas/scheduler.py
```

### Create requirements-saas.txt

```txt
# requirements-saas.txt
Flask==3.0.0
Flask-SQLAlchemy==3.1.1
Flask-Login==0.6.3
Flask-Limiter==3.5.0
gunicorn==21.2.0
psycopg2-binary==2.9.9
cryptography==41.0.7
Werkzeug==3.0.1
python-dotenv==1.0.0
```

### Create saas/execute_all_bots.py (for cron job option)

```python
#!/usr/bin/env python3
"""
Execute all active bots once (called by Render Cron Job)
This runs every 5 minutes via Render's cron schedule
"""
import os
import sys
import subprocess
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from saas.database import get_db

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def execute_bot(bot_id: int):
    """Execute a single bot by calling main.py with BOT_ID"""
    try:
        env = os.environ.copy()
        env['BOT_ID'] = str(bot_id)

        result = subprocess.run(
            ['python', 'main.py'],
            env=env,
            capture_output=True,
            text=True,
            timeout=120  # 2 min timeout per bot
        )

        if result.returncode == 0:
            logger.info(f"✅ Bot {bot_id} executed successfully")
        else:
            logger.error(f"❌ Bot {bot_id} failed: {result.stderr}")
            return False

        return True

    except subprocess.TimeoutExpired:
        logger.error(f"⏱ Bot {bot_id} execution timeout (>2 min)")
        return False
    except Exception as e:
        logger.error(f"❌ Bot {bot_id} error: {e}")
        return False


def main():
    logger.info("Starting bot execution cycle")

    try:
        # Get all active bots from database
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, name, user_id
                FROM bots
                WHERE status = 'running'
                ORDER BY id
            """)
            active_bots = cursor.fetchall()

        if not active_bots:
            logger.info("No active bots to execute")
            return

        logger.info(f"Found {len(active_bots)} active bots")

        # Execute each bot
        success_count = 0
        for bot_id, bot_name, user_id in active_bots:
            logger.info(f"Executing bot {bot_id} ({bot_name}) for user {user_id}")
            if execute_bot(bot_id):
                success_count += 1

        logger.info(f"Execution cycle complete: {success_count}/{len(active_bots)} successful")

    except Exception as e:
        logger.error(f"Execution cycle failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
```

## Step 4: Deploy to Render

### Method 1: Via Render Dashboard (Recommended First Time)

1. **Push code to GitHub**:
   ```bash
   git add .
   git commit -m "Add Render deployment files"
   git push origin feature/saas-transformation
   ```

2. **Create Web Service**:
   - Go to https://render.com/dashboard
   - Click **New** → **Web Service**
   - Connect your GitHub repo
   - Select branch: `feature/saas-transformation` (or `main`)
   - Configure:
     - **Name**: `dcabot-saas-web`
     - **Region**: Oregon (or Frankfurt if closer to DO database)
     - **Branch**: `feature/saas-transformation`
     - **Build Command**: `pip install -r requirements.txt -r requirements-saas.txt`
     - **Start Command**: `gunicorn -w 4 -b 0.0.0.0:$PORT saas.app:app`
     - **Plan**: Starter ($7/month)

3. **Set Environment Variables** (in Render dashboard):
   ```
   DATABASE_URL = postgresql://diptrader:YOUR_PASSWORD@private-dbaas-db-10215807-do-user-15659652-0.e.db.ondigitalocean.com:25060/diptrader?sslmode=require

   SECRET_KEY = (generate with: python -c "import os; print(os.urandom(32).hex())")

   ENCRYPTION_KEY = (generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

   FLASK_ENV = production
   DEBUG = False
   PYTHON_VERSION = 3.11.0
   ```

4. **Create Background Worker or Cron Job**:

   **Option A: Background Worker** ($7/month)
   - Click **New** → **Background Worker**
   - Connect same repo
   - **Start Command**: `python saas/scheduler.py`
   - Use same environment variables as web service

   **Option B: Cron Job** (Free!)
   - Click **New** → **Cron Job**
   - Connect same repo
   - **Schedule**: `*/5 * * * *` (every 5 minutes)
   - **Command**: `python saas/execute_all_bots.py`
   - Use same environment variables as web service

5. **Deploy**:
   - Click **Create Web Service**
   - Render will build and deploy automatically
   - Wait for build to complete (~3-5 minutes)
   - Access at: `https://dcabot-saas-web.onrender.com`

### Method 2: Via Blueprint (render.yaml)

1. **Commit render.yaml**:
   ```bash
   git add render.yaml
   git commit -m "Add Render blueprint"
   git push
   ```

2. **Deploy Blueprint**:
   - Go to https://render.com/dashboard
   - Click **New** → **Blueprint**
   - Connect your GitHub repo
   - Select `render.yaml`
   - Review services
   - Set environment variables (DATABASE_URL, ENCRYPTION_KEY)
   - Click **Apply**

3. **Done!** Render deploys everything automatically.

## Step 5: Initialize Database Schema

After deployment, run the schema on your DO database:

```bash
# From your local machine
psql "postgresql://diptrader:YOUR_PASSWORD@private-dbaas-db-10215807-do-user-15659652-0.e.db.ondigitalocean.com:25060/diptrader?sslmode=require" -f saas/schema.sql
```

Or use Render Shell:
```bash
# In Render dashboard, go to your web service
# Click "Shell" tab
# Run:
python -c "
from saas.database import get_db
import open('saas/schema.sql').read() as sql
with get_db() as conn:
    conn.cursor().execute(sql)
"
```

## Step 6: Custom Domain (Optional)

### Add Your Own Domain

1. **In Render Dashboard**:
   - Go to your web service
   - Click **Settings**
   - Scroll to **Custom Domain**
   - Add: `dcabot.yourdomain.com`

2. **Update DNS** (in your domain registrar):
   ```
   Type: CNAME
   Name: dcabot
   Value: dcabot-saas-web.onrender.com
   ```

3. **SSL**: Render automatically provisions SSL (Let's Encrypt)

4. **Done!** Access at `https://dcabot.yourdomain.com`

## Migration Strategy: Run Both Systems in Parallel

### Phase 1: Deploy SaaS (Week 1)
- ✅ Deploy web service and scheduler to Render
- ✅ Keep existing cron job running (standalone mode)
- ✅ Both systems work independently

### Phase 2: Test with Personal Bot (Week 2)
- 📝 Create your bot via web interface
- 📝 Test execution via SaaS scheduler
- ✅ Standalone cron job still running (fallback)

### Phase 3: Migrate Fully (Week 3)
- 📝 Disable standalone cron job
- 📝 Use SaaS for all bots
- 🎉 Invite first users!

## Render vs camproute-server Comparison

| Feature | Render | camproute-server |
|---------|--------|------------------|
| **Cost** | $7-14/month | $0 (already paying for server) |
| **Setup Time** | 30 minutes | 2-3 hours |
| **SSL** | Automatic (free) | Manual (Let's Encrypt) |
| **Deployment** | Git push = deploy | Manual SSH + restart |
| **Scaling** | Automatic | Manual |
| **Monitoring** | Built-in logs/metrics | Setup yourself |
| **Existing Bot** | Runs alongside SaaS | Runs alongside SaaS |
| **Database** | Use DO managed PostgreSQL | Use DO managed PostgreSQL |
| **Maintenance** | Render handles it | You handle it |

**Recommendation**: Start with Render because:
1. ✅ You're already using it
2. ✅ Faster to market (30 min vs 3 hours)
3. ✅ Less maintenance overhead
4. ✅ Easy to migrate later if needed
5. ✅ Can switch to camproute-server anytime

## Cost Optimization

### Cheapest Option: $7/month
- Web Service: $7/month
- Cron Job: FREE
- Database: Your existing DO PostgreSQL
- **Total: $7/month**

### Recommended Option: $14/month
- Web Service: $7/month
- Background Worker: $7/month (more reliable than cron)
- Database: Your existing DO PostgreSQL
- **Total: $14/month**

### Breakeven
- **2 paid users** at $19/month (Basic plan) = $38 revenue
- Profit: $38 - $14 = $24/month 🎉

## Health Checks & Monitoring

### Create Health Check Endpoint

In `saas/app.py`:

```python
@app.route('/health')
def health():
    """Health check for Render monitoring"""
    try:
        # Check database connection
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")

        return {
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat()
        }, 200
    except Exception as e:
        return {
            'status': 'unhealthy',
            'error': str(e)
        }, 500
```

Render automatically monitors this endpoint and alerts if it fails.

### View Logs

```bash
# Real-time logs from Render dashboard
# Or via CLI:
render logs -s dcabot-saas-web
render logs -s dcabot-scheduler
```

## Troubleshooting

### Build Fails

**Error**: `No module named 'psycopg2'`
**Fix**: Add `psycopg2-binary` to `requirements-saas.txt`

**Error**: `Could not connect to database`
**Fix**:
1. Check DATABASE_URL is set correctly in Render env vars
2. Verify DO PostgreSQL allows external connections (0.0.0.0/0)
3. Test connection from your local machine first

### Worker Not Running

**Error**: Worker starts then stops immediately
**Fix**: Check logs in Render dashboard → Worker → Logs
- Likely database connection issue
- Or missing environment variables

### Cron Job Not Executing

**Check**:
1. Go to Render dashboard → Cron Job → Logs
2. Verify schedule is correct: `*/5 * * * *`
3. Check if `saas/execute_all_bots.py` exists

## Security Checklist

- [ ] DATABASE_URL contains strong password
- [ ] ENCRYPTION_KEY is generated and stored securely
- [ ] SECRET_KEY is generated (not using default)
- [ ] FLASK_ENV=production
- [ ] DEBUG=False
- [ ] DO PostgreSQL requires SSL (sslmode=require)
- [ ] API keys encrypted in database
- [ ] Passwords hashed (bcrypt)

## Next Steps After Deployment

1. ✅ Access your app: `https://dcabot-saas-web.onrender.com`
2. 📝 Create first user account
3. 📝 Create test bot via web interface
4. 📝 Verify bot executes every 5 minutes
5. 📝 Check trades logged to database
6. 🎉 Share with friends for beta testing!

## Quick Start Commands

```bash
# 1. Generate encryption key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# 2. Generate secret key
python -c "import os; print(os.urandom(32).hex())"

# 3. Test database connection
psql "postgresql://diptrader:PASSWORD@private-dbaas-db-10215807-do-user-15659652-0.e.db.ondigitalocean.com:25060/diptrader?sslmode=require"

# 4. Apply schema
psql "postgresql://diptrader:PASSWORD@..." -f saas/schema.sql

# 5. Push to GitHub
git push origin feature/saas-transformation

# 6. Deploy on Render (via dashboard)
# → Connect repo
# → Set env vars
# → Deploy!
```

Ready to deploy? 🚀

**Time estimate**: 30-60 minutes for complete Render setup
