# DCA Bot SaaS - Render.com Deployment Guide

Complete guide to deploying the DCA Bot SaaS platform to Render.com.

## Prerequisites

- GitHub account with the repository
- Render.com account (free tier works)
- Digital Ocean PostgreSQL database (or any PostgreSQL provider)
- Generated encryption key

## Architecture Overview

Your deployment consists of two Render services:

```
┌─────────────────────────────────────────────┐
│ Render.com (Frankfurt)                      │
│                                             │
│ ┌─────────────────────────────────────┐   │
│ │ dcabot-saas-web (Web Service)       │   │
│ │ • Flask dashboard (port 3030)       │   │
│ │ • User management & admin panel     │   │
│ │ • Bot configuration UI              │   │
│ │ • Performance charts                │   │
│ │ Cost: $7/month                      │   │
│ └─────────────────────────────────────┘   │
│                                             │
│ ┌─────────────────────────────────────┐   │
│ │ dcabot-saas-scheduler (Cron Job)    │   │
│ │ • Runs every 5 minutes              │   │
│ │ • Executes all active bots          │   │
│ │ • Logs to database                  │   │
│ │ Cost: FREE                          │   │
│ └─────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
                    │
                    ├─────── (connects to) ──────┐
                    │                             │
         ┌──────────▼──────────┐    ┌────────────▼──────────┐
         │ PostgreSQL Database │    │ Phemex Exchange API   │
         │ (Digital Ocean)     │    │ (Testnet/Mainnet)     │
         │ • Users & bots      │    │ • Place orders        │
         │ • Metrics & logs    │    │ • Check positions     │
         │ • Trading pairs     │    │ • Get market data     │
         └─────────────────────┘    └───────────────────────┘
```

## Step 1: Prepare Encryption Key

Generate a Fernet encryption key for API credential encryption:

```bash
python -c "from cryptography.fernet import Fernet; print('ENCRYPTION_KEY=' + Fernet.generate_key().decode())"
```

**Output example**:
```
ENCRYPTION_KEY=gAAAAABhR8x...your_key_here...==
```

Save this key securely - you'll need it for Render configuration.

## Step 2: Configure Database Access

### Allow Render IP Addresses

Your PostgreSQL database must allow connections from Render's servers in Frankfurt.

1. Go to your database provider (Digital Ocean, AWS RDS, etc.)
2. Add these Render Frankfurt IPs to trusted sources:
   ```
   3.75.158.163
   3.125.183.140
   35.157.117.28
   74.220.51.0/24
   74.220.59.0/24
   ```

### Get Database Connection String

Format: `postgresql://username:password@host:port/database?sslmode=require`

**Example**:
```
postgresql://dcabot:mypassword@db-host.digitalocean.com:25060/dcabot_prod?sslmode=require
```

## Step 3: Database Migrations (Automatic)

**Migrations run automatically during Render deployment** via the build command. This step is **optional** - only needed if you want to verify migrations work before pushing to Render.

### Optional: Test Migrations Locally (First-Time Setup)

If this is your first deployment and you want to verify migrations work:

```bash
# Set your DATABASE_URL
export DATABASE_URL="postgresql://username:password@host:port/database?sslmode=require"

# Run migrations
python saas/migrate.py

# Verify
python saas/migrate.py --status
```

Expected output:
```
✅ Migrations tracking table ready
📊 Migration Status:
============================================================
✅ Applied       001_initial_schema.sql
✅ Applied       002_add_execution_metrics.sql
✅ Applied       003_add_admin_and_approval.sql
============================================================
Total: 3 migrations (3 applied, 0 pending)
```

> **Note**: When you deploy to Render, migrations run automatically during the build phase. You don't need to run them manually unless troubleshooting.

## Step 4: Push Code to GitHub

Ensure all code is committed and pushed:

```bash
git add .
git commit -m "Ready for Render deployment"
git push origin feature/saas-transformation
```

> 💡 **That's it!** Render will automatically run migrations during deployment. No manual database setup needed.

## Step 5: Deploy on Render

### Option A: Using Render Blueprint (Recommended)

1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click **New** → **Blueprint**
3. Connect your GitHub repository
4. Select branch: `feature/saas-transformation`
5. Render auto-detects `render.yaml`
6. Review services:
   - `dcabot-saas-web` (Web Service, $7/month)
   - `dcabot-saas-scheduler` (Cron Job, FREE)
7. Click **Apply**

### Option B: Manual Setup

**Create Web Service:**
1. New → Web Service
2. Connect GitHub repo → branch `feature/saas-transformation`
3. Configure:
   ```
   Name: dcabot-saas-web
   Region: Frankfurt (EU Central)
   Branch: feature/saas-transformation
   Runtime: Python 3
   Build Command: pip install -r requirements.txt -r requirements-saas.txt && python saas/migrate.py
   Start Command: gunicorn -w 4 -b 0.0.0.0:$PORT saas.app:app
   Plan: Starter ($7/month)
   ```

**Create Cron Job:**
1. New → Cron Job
2. Connect GitHub repo → branch `feature/saas-transformation`
3. Configure:
   ```
   Name: dcabot-saas-scheduler
   Region: Frankfurt (EU Central)
   Schedule: */5 * * * * (every 5 minutes)
   Build Command: pip install -r requirements.txt -r requirements-saas.txt
   Command: python saas/execute_all_bots.py
   ```

## Step 6: Configure Environment Variables

### For `dcabot-saas-web`:

Go to Service → Environment tab and add:

| Variable | Value | Description |
|----------|-------|-------------|
| `DATABASE_URL` | `postgresql://...` | PostgreSQL connection string |
| `ENCRYPTION_KEY` | `gAAAAABh...` | Fernet key from Step 1 |
| `SECRET_KEY` | (auto-generated) | Flask session key |
| `FLASK_ENV` | `production` | Flask environment |

### For `dcabot-saas-scheduler`:

Go to Service → Environment tab and add:

| Variable | Value | Description |
|----------|-------|-------------|
| `DATABASE_URL` | `postgresql://...` | PostgreSQL connection string (same as web) |
| `ENCRYPTION_KEY` | `gAAAAABh...` | Fernet key (same as web) |

## Step 7: Verify Deployment

### Check Web Service

1. Wait for deployment to complete (3-5 minutes)
2. Visit your Render URL: `https://dcabot-saas-web.onrender.com`
3. You should see the landing page
4. Go to `/register` and create an admin account

### Check Health Endpoint

```bash
curl https://dcabot-saas-web.onrender.com/health
```

Expected response:
```json
{
  "status": "healthy",
  "database": "connected",
  "active_bots": 0,
  "timestamp": "2025-11-01T17:30:00.000Z"
}
```

### Check Cron Job

1. Go to Render Dashboard → `dcabot-saas-scheduler`
2. Click "Logs"
3. Wait for next execution (every 5 minutes)
4. You should see:
   ```
   🤖 Starting bot execution cycle
   No active bots to execute
   ```

## Step 8: First User Setup

### Register Admin Account

1. Visit `https://your-app.onrender.com/register`
2. Create account with email/password
3. First user automatically becomes admin

### Create Your First Bot

1. Log in to dashboard
2. Click "New Bot"
3. Enter:
   - Name: "My Test Bot"
   - Exchange: Phemex
   - API Key: (from Phemex)
   - API Secret: (from Phemex)
   - Environment: Testnet (for testing)
4. Click "Create Bot"

### Add Trading Pair

1. Go to bot detail page
2. Click "+ Add Pair"
3. Configure:
   - Symbol: BTCUSDT
   - Side: Long
   - Leverage: 10x
   - Auto Mode: Yes
4. Click "Save"

### Start Bot

1. On bot detail page, click "Start Bot"
2. Bot status changes to "Running"
3. Wait 5 minutes for next cron execution
4. Check "Bot Activity Log" for results

## Monitoring

### Dashboard

Access at `https://your-app.onrender.com/dashboard`:
- View all bots
- Check running status
- See recent activity
- Monitor performance metrics

### Admin Panel

Access at `https://your-app.onrender.com/admin` (admin only):
- Approve pending user registrations
- Toggle registration on/off
- View all users

### Render Logs

**Web Service Logs**:
```
Dashboard → dcabot-saas-web → Logs
```

**Cron Job Logs**:
```
Dashboard → dcabot-saas-scheduler → Logs
```

### Database Logs

Check `bot_logs` table for execution history:
```sql
SELECT * FROM bot_logs
WHERE bot_id = 1
ORDER BY created_at DESC
LIMIT 20;
```

## Troubleshooting

### Build Fails with Migration Error

**Symptom**: Deployment fails during `python saas/migrate.py`

**Solution**:
1. Check Render build logs for specific SQL error
2. Fix the migration file locally
3. Test: `export DATABASE_URL="..." && python saas/migrate.py`
4. Push fix: `git commit -am "Fix migration" && git push`
5. Render will auto-retry

### Database Connection Timeout

**Symptom**: `could not connect to server` error

**Solution**:
1. Verify DATABASE_URL is correct
2. Check database allows Render IPs
3. Ensure database is running
4. Test connection:
   ```bash
   psql "$DATABASE_URL" -c "SELECT 1"
   ```

### Cron Job Not Executing Bots

**Symptom**: Logs show "No active bots" despite having running bots

**Solution**:
1. Check bot status in dashboard (should be "running")
2. Verify DATABASE_URL is set in cron job
3. Check cron job logs for errors
4. Manually test:
   ```bash
   export DATABASE_URL="..."
   export BOT_ID=1
   python main.py
   ```

### Charts Not Displaying Data

**Symptom**: Bot detail page shows empty charts

**Solution**:
1. Bot needs at least one execution cycle (wait 5 minutes)
2. Check `/api/bots/1/metrics` endpoint
3. Verify `execution_metrics` table has data:
   ```sql
   SELECT COUNT(*) FROM execution_metrics WHERE bot_id = 1;
   ```

### "Access Denied" When Logging In

**Symptom**: User account pending approval

**Solution**:
1. Admin must approve in `/admin` panel
2. Or manually approve:
   ```sql
   UPDATE users SET is_approved = TRUE WHERE email = 'user@example.com';
   ```

## Updating the Platform

### Deploy New Changes

```bash
# 1. Make changes locally
git add .
git commit -m "Add new feature"

# 2. Push to GitHub
git push origin feature/saas-transformation

# 3. Render auto-deploys
# - Migrations run automatically during build
# - Zero downtime deployment
```

### New Database Migration

```bash
# 1. Create migration file
cat > saas/migrations/004_add_feature.sql << 'EOF'
ALTER TABLE bots ADD COLUMN description TEXT;
EOF

# 2. Test locally
export DATABASE_URL="..."
python saas/migrate.py

# 3. Commit and push
git add saas/migrations/004_add_feature.sql
git commit -m "Add bot description field"
git push

# 4. Render runs migration automatically
```

See [DATABASE_MIGRATIONS.md](DATABASE_MIGRATIONS.md) for details.

## Scaling

### When to Upgrade

**Starter Plan ($7/month)** is sufficient for:
- Up to 10 active bots
- Up to 100 users
- Light to moderate usage

**Upgrade to Worker** when you have:
- More than 10 active bots
- Cron job taking > 2 minutes to complete
- Need guaranteed execution (cron can have delays)

### How to Upgrade

Change `render.yaml`:

```yaml
# FROM (Cron Job - Free):
- type: cron
  schedule: "*/5 * * * *"

# TO (Background Worker - $7/month):
- type: worker
  plan: starter
```

Push changes → Render redeploys as always-on worker.

**Cost**: $14/month ($7 web + $7 worker)

## Cost Breakdown

| Component | Type | Cost |
|-----------|------|------|
| Web Service | Starter | $7/month |
| Cron Job | Free tier | $0/month |
| PostgreSQL | External | ~$15/month |
| **Total** | | **~$22/month** |

**Notes**:
- Cron job is free (< 1 hour/month runtime)
- If upgraded to worker: $7 additional
- Database cost varies by provider

## Security Checklist

- ✅ API keys encrypted with Fernet
- ✅ Passwords hashed with bcrypt
- ✅ Database connections use SSL
- ✅ Environment variables not in code
- ✅ Registration approval system
- ✅ Admin-only routes protected
- ✅ SQL injection prevented (parameterized queries)
- ✅ CSRF protection (Flask built-in)

## Support

For deployment issues:
- Check [Render documentation](https://render.com/docs)
- Review [DATABASE_MIGRATIONS.md](DATABASE_MIGRATIONS.md)
- See main [README.md](../README.md)

## Summary

✅ **Two services** on Render (web + cron)
✅ **PostgreSQL database** (external)
✅ **Automatic migrations** on deploy
✅ **Zero downtime** updates
✅ **$7/month** base cost
✅ **EU Frankfurt** region

Your DCA Bot SaaS platform is now deployed and running!
