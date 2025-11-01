# Your Custom Deployment Guide - dcabot-saas

## Your Configuration

✅ **Region**: Frankfurt (EU)
✅ **Execution**: Cron Job (free, runs every 5 minutes)
✅ **Database**: Digital Ocean PostgreSQL (diptrader) with IP allowlist
✅ **Domain**: dcabot-saas.onrender.com
✅ **Existing Bot**: Keep running (backward compatible)
✅ **Deployment**: Blueprint (render.yaml)

**Total Cost**: $7/month (web service only)
**Upgrade Path**: Switch to Background Worker ($14/month) when you have >10 active bots

---

## Step 1: Allow Render to Access Your Database (5 minutes)

### Update Digital Ocean Database Firewall

1. Go to https://cloud.digitalocean.com/databases
2. Click on your **diptrader** database cluster
3. Click **Settings** tab
4. Scroll to **Trusted Sources**
5. Click **Edit** or **Add trusted source**
6. Add these Render IP addresses (one at a time):

```
3.75.158.163
3.125.183.140
35.157.117.28
74.220.51.0/24
74.220.59.0/24
```

7. Click **Save**

**Verification**: Your database now accepts connections from Render's Frankfurt region.

---

## Step 2: Generate Security Keys (2 minutes)

Run these commands locally:

```bash
# Generate encryption key (for API key encryption)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Output: Something like "abc123def456..."
# SAVE THIS - you'll need it in Step 4

# Generate secret key (for Flask sessions)
python -c "import os; print(os.urandom(32).hex())"
# Output: Something like "a1b2c3d4e5f6..."
# SAVE THIS - you'll need it in Step 4
```

**Important**: Keep these keys safe! Don't commit them to Git.

---

## Step 3: Create Required Files

### 3.1 Create saas/execute_all_bots.py

This file runs all active bots once (called by cron job):

```bash
mkdir -p saas
```

Create `saas/execute_all_bots.py`:

```python
#!/usr/bin/env python3
"""
Execute all active bots once (called by Render Cron Job every 5 minutes)
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
            return True
        else:
            logger.error(f"❌ Bot {bot_id} failed: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        logger.error(f"⏱ Bot {bot_id} execution timeout (>2 min)")
        return False
    except Exception as e:
        logger.error(f"❌ Bot {bot_id} error: {e}")
        return False


def main():
    logger.info("🤖 Starting bot execution cycle")

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

        logger.info(f"✅ Execution cycle complete: {success_count}/{len(active_bots)} successful")

    except Exception as e:
        logger.error(f"❌ Execution cycle failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
```

### 3.2 Create saas/__init__.py

```bash
touch saas/__init__.py
```

### 3.3 Verify render.yaml exists

Check that `render.yaml` exists in your repo root (I've already created it).

---

## Step 4: Initialize Database Schema (3 minutes)

Apply the database schema to your diptrader database:

```bash
# From your local machine
psql "postgresql://diptrader:YOUR_PASSWORD@private-dbaas-db-10215807-do-user-15659652-0.e.db.ondigitalocean.com:25060/diptrader?sslmode=require" -f saas/schema.sql
```

**Expected output**: Tables created successfully

**Verify**:
```bash
psql "postgresql://diptrader:YOUR_PASSWORD@..." -c "\dt"
```

You should see: users, bots, trading_pairs, trades, bot_logs

---

## Step 5: Commit and Push to GitHub (2 minutes)

```bash
# Make sure you're on the feature branch
git status

# Add all files
git add .

# Commit
git commit -m "Add Render deployment files for SaaS

- render.yaml configured for Frankfurt region
- Cron job execution (free tier)
- saas/execute_all_bots.py for bot execution
- Backward compatible with existing standalone bot

Ready to deploy to dcabot-saas.onrender.com"

# Push to GitHub
git push origin feature/saas-transformation
```

---

## Step 6: Deploy to Render (10 minutes)

### 6.1 Create New Blueprint

1. Go to https://dashboard.render.com
2. Click **New** → **Blueprint**
3. Connect your GitHub account (if not already)
4. Select your repository
5. Select branch: `feature/saas-transformation`
6. Render will detect `render.yaml`
7. Click **Apply**

### 6.2 Set Environment Variables

Render will prompt you to set environment variables:

**For dcabot-saas-web** (Web Service):

```
DATABASE_URL = postgresql://diptrader:YOUR_PASSWORD@private-dbaas-db-10215807-do-user-15659652-0.e.db.ondigitalocean.com:25060/diptrader?sslmode=require

ENCRYPTION_KEY = [paste the encryption key from Step 2]

# SECRET_KEY is auto-generated by Render, no need to set
```

**For dcabot-saas-scheduler** (Cron Job):

```
DATABASE_URL = [same as above]

ENCRYPTION_KEY = [same as above]
```

### 6.3 Deploy

1. Click **Create Services**
2. Render will:
   - Build both services
   - Deploy web service
   - Schedule cron job
3. Wait 3-5 minutes for build to complete

**Access your app**: https://dcabot-saas.onrender.com

---

## Step 7: Verify Everything Works (5 minutes)

### 7.1 Check Web Service

1. Visit https://dcabot-saas.onrender.com
2. You should see the login/register page
3. Check health endpoint: https://dcabot-saas.onrender.com/health
   - Should return: `{"status": "healthy"}`

### 7.2 Check Cron Job

1. In Render dashboard → **dcabot-saas-scheduler**
2. Click **Logs**
3. Wait for next execution (within 5 minutes)
4. You should see: "No active bots to execute" (normal, you haven't created any yet)

### 7.3 Check Database Connection

In Render web service logs, you should see successful database connections.

---

## Step 8: Create Your First Bot (5 minutes)

1. Go to https://dcabot-saas.onrender.com
2. Register an account
3. Login
4. Create a bot via web interface
5. Add trading pairs
6. Set status to "running"
7. Wait 5 minutes for next cron execution
8. Check logs to verify bot executed

---

## Backward Compatibility Verification

Your existing standalone bot (the one running as a Render cron job already) will continue to work:

1. It uses `.env` file (no changes needed)
2. It runs `main.py` directly (no BOT_ID set)
3. Completely independent from SaaS system
4. Both can run in parallel safely

**To verify**:
```bash
# Check your existing cron job is still there
# In Render dashboard, you should see TWO cron jobs:
# 1. Your original bot (existing)
# 2. dcabot-saas-scheduler (new)
```

---

## Upgrading to Background Worker (when needed)

When you have >10 active bots and cron job is taking too long:

### Signs you need to upgrade:
- Cron job logs show "execution took >4 minutes"
- Bots miss execution windows
- Users report delayed trades

### How to upgrade (5 minutes):

1. Edit `render.yaml`:
   ```yaml
   # Comment out the cron service
   # Uncomment the worker service (lines at bottom of file)
   ```

2. Commit and push:
   ```bash
   git add render.yaml
   git commit -m "Upgrade to background worker for better scaling"
   git push
   ```

3. Render automatically redeploys with worker

4. New cost: $14/month ($7 web + $7 worker)

**Benefits**:
- Processes bots in parallel
- Never misses execution windows
- Better for 10+ bots

---

## Monitoring & Logs

### Web Service Logs
```
Render Dashboard → dcabot-saas-web → Logs
```

### Cron Job Logs
```
Render Dashboard → dcabot-saas-scheduler → Logs
```

### Database Logs
```
Digital Ocean → Databases → diptrader → Insights
```

---

## Troubleshooting

### "Could not connect to database"

**Check**:
1. DATABASE_URL is correct in Render env vars
2. Render IPs are in DO database allowlist
3. Database password is correct
4. SSL mode is `require`

**Test connection**:
```bash
# In Render web service shell:
python -c "from saas.database import test_connection; test_connection()"
```

### "No module named 'saas'"

**Fix**: Make sure `saas/__init__.py` exists
```bash
touch saas/__init__.py
git add saas/__init__.py
git commit -m "Add saas package init"
git push
```

### Cron job not running

**Check**:
1. Render Dashboard → dcabot-saas-scheduler → Settings
2. Verify schedule is `*/5 * * * *`
3. Check logs for errors

### Web service won't start

**Check**:
1. Build logs for errors
2. Ensure `requirements-saas.txt` includes all dependencies
3. Verify `saas/app.py` exists

---

## Cost Summary

**Current setup** (Cron Job):
- Web Service: $7/month
- Cron Job: FREE
- **Total: $7/month**

**When you upgrade** (Background Worker):
- Web Service: $7/month
- Worker: $7/month
- **Total: $14/month**

**Breakeven**: 2 paying users at $19/month = $38 revenue
**Profit**: $38 - $14 = $24/month 🎉

---

## Next Steps

1. ✅ Deploy (follow steps above)
2. 📝 Test with your own account
3. 🐛 Fix any issues
4. 👥 Invite 2-3 beta testers
5. 🚀 Public launch!

**Estimated time to deploy**: 30-40 minutes

Need help? Check logs in Render dashboard or review docs/RENDER_DEPLOYMENT.md for more details.

Good luck! 🚀
