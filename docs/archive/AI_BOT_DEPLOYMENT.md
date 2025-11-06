# AI Trading Bot Feature - Deployment Checklist

**Status:** Ready for Production Deployment
**Branch:** `feature/ai-glm-trading-bot` → merge to `feature/saas-transformation`
**Estimated Downtime:** 3-5 minutes (only during build/deploy)
**Risk Level:** 🟢 LOW (No changes to Martingale bot code)
**Deployment:** Fully automated via Render Blueprint (render.yaml)

---

## Quick Deployment Steps

### 1. Local Testing (5 minutes)
```bash
cd saas

# Test migration
python -c "from database import run_migrations; run_migrations()"

# Test executor
./run_executor.sh

# Test web app
./run_local_app.sh
# Visit: http://localhost:5001/ai-bots/dashboard
```

### 2. Merge to Production Branch (2 minutes)
```bash
git checkout feature/saas-transformation
git pull origin feature/saas-transformation
git merge feature/ai-glm-trading-bot
git push origin feature/saas-transformation
```

### 3. Monitor Render Deployment (3-5 minutes)
Render Blueprint will automatically deploy ALL services (including new AI executor cron job).

```bash
# Watch logs
render logs -s dcabot-saas-web --tail

# Look for:
# ✅ "Running migration: 012_add_ai_bots_tables.sql"
# ✅ "Migration successful"
# ✅ "Gunicorn is running"
```

### 4. Verify All Services Created (1 minute)
```bash
# Check all services
render services list

# Should see:
# ✅ dcabot-saas-web (running)
# ✅ dcabot-saas-scheduler (running) - Martingale bots
# ✅ dcabot-ai-executor (running) - AI bots ← NEW!
# ✅ dcabot-weekly-backtests (running)

# Test web app
curl https://dcabot-saas.onrender.com/health
curl https://dcabot-saas.onrender.com/ai-bots/dashboard
```

### 5. Monitor First AI Execution (5 minutes)
```bash
render logs -s dcabot-ai-executor --tail

# Look for:
# ✅ "Executing AI bot #X"
# ✅ "GLM-4.5-Air decision: BUY (confidence: 75%)"
# ✅ "Trade execution: EXECUTED"
# ✅ "Performance metrics updated"
```

---

## Render Configuration Changes

### ✅ FULLY AUTOMATED via Blueprint (render.yaml)
- ✅ Branch: Already monitoring `feature/saas-transformation`
- ✅ New cron job: `dcabot-ai-executor` - Created automatically from blueprint
- ✅ Build command: Unchanged
- ✅ Start command: Unchanged
- ✅ Environment variables: No new vars required
- ✅ Web service: No changes

### ❌ No Manual Changes Required!
The updated `render.yaml` blueprint includes the AI executor cron job, so it will be created automatically when you push to the branch.

---

## Post-Deployment Verification

### Check Martingale Bots (Should Be Unaffected)
```bash
# Visit: https://dcabot-saas.onrender.com/bots/dashboard
# ✅ Verify bots still executing
# ✅ Check last execution timestamp
```

### Check AI Bots
```bash
# Visit: https://dcabot-saas.onrender.com/ai-bots/dashboard
# ✅ Create test AI bot (GLM-4.5-Flash - FREE)
# ✅ Watch for decisions every 5 minutes
# ✅ Verify chart updates
# ✅ Check MODELCHAT tab for colored decision boxes
```

### Check Database
```bash
psql $DATABASE_URL

# Verify migration
SELECT * FROM schema_migrations WHERE version = '012';

# Check AI tables
\dt ai_*

# Check data
SELECT COUNT(*) FROM ai_bots;
SELECT COUNT(*) FROM ai_decisions;
```

---

## Rollback Plan

### If Migration Fails:
```bash
# Render keeps old version running automatically
git checkout feature/saas-transformation
git revert HEAD
git push origin feature/saas-transformation
```

### If AI Executor Has Issues:
- In Render Dashboard → `dcabot-ai-executor` → "Suspend" or "Delete"
- Martingale bots continue running unaffected

### If Web App Has Issues:
- In Render Dashboard → `dcabot-saas-web` → "Rollback" to previous version

---

## Key Features Deployed

### Trade Execution (`saas/execute_ai_bots.py`)
- ✅ Live trading on Phemex (testnet/mainnet)
- ✅ Position sizing with leverage
- ✅ Trading fee tracking (0.15%)
- ✅ Virtual balance management
- ✅ Confidence threshold (70%)
- ✅ Multi-symbol support

### Dashboard UI (`/ai-bots/dashboard`)
- ✅ Model-specific colors (Orange/Blue/Purple/Cyan/Red)
- ✅ Real-time crypto price ticker
- ✅ 70/30 split layout (large chart)
- ✅ 520px tall chart
- ✅ Bot carousel with colored borders
- ✅ MODELCHAT tab with colored decision boxes
- ✅ Auto-refresh (30s polling)
- ✅ Bot management (create/pause/delete)

### Database Schema (Migration 012)
- ✅ `ai_model_configs` - Model specifications
- ✅ `ai_bots` - User AI bots
- ✅ `ai_decisions` - Decision history
- ✅ `ai_model_performance` - Performance tracking

---

## Cost Impact

**Monthly Costs (per bot):**
- GLM-4.5-Flash: **FREE** (3,000 decisions/month)
- GLM-4.5-Air: **$2.50** (3,000 decisions/month)
- DeepSeek-Chat: **$3.50** (3,000 decisions/month)
- Claude-3.5-Sonnet: **$150** (3,000 decisions/month)

**Render Infrastructure:** No additional cost (uses existing services)

---

## Support Contacts

**Issues?**
- Render Logs: `render logs -s <service-name> --tail`
- Database: `psql $DATABASE_URL`
- GitHub: https://github.com/pehur00/dcabot

**Monitoring:**
- Dashboard: https://dcabot-saas.onrender.com/ai-bots/dashboard
- Render: https://dashboard.render.com

---

**Deployment Date:** _____________
**Deployed By:** _____________
**Status:** [ ] Success  [ ] Rollback Required
