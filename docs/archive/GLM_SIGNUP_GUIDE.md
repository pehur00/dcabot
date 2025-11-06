# GLM API Signup & Testing Guide

**Quick Start:** Get your GLM API key and test in 10 minutes!

---

## 🚀 Step 1: Sign Up for z.ai (5 minutes)

### Option A: Direct Signup (Recommended)
1. **Visit:** https://open.bigmodel.cn
2. **Click:** Register/注册 (top right)
3. **Options:**
   - Use email + verification code
   - Or sign in with WeChat (if you have it)
4. **Verify** your email
5. **Done!** You're in

### Option B: Chat Interface First
1. **Visit:** https://chat.z.ai
2. **Try the chat** (no signup needed initially)
3. **Then sign up** at https://open.bigmodel.cn for API access

---

## 🔑 Step 2: Get Your API Key (2 minutes)

### After Logging In:
1. **Go to:** https://open.bigmodel.cn/usercenter/apikeys
   - Or look for "API Keys" / "API密钥" in the menu
2. **Click:** "Create New API Key" / "创建新的API密钥"
3. **Name it:** "DCABot Trading" (or anything you like)
4. **Copy the key** - Save it immediately! (You won't see it again)
5. **Important:** Keep this key SECRET!

### Example API Key Format:
```
1234567890abcdef.1234567890abcdef
```

---

## 💰 Step 3: Check Your Free Credits (1 minute)

New accounts typically get **FREE credits** to test!

1. **Check balance:** Look for "余额" (Balance) in dashboard
2. **You should see:** Free trial credits or tokens
3. **Enough for:** 100+ test calls to start

**Note:** Even without free credits, it's only $0.0015 per call!

---

## 🧪 Step 4: Test the API (2 minutes)

### Set Your API Key

**On Mac/Linux:**
```bash
export ZHIPU_API_KEY="your_key_here"
```

**Or add to `.env` file:**
```bash
echo 'ZHIPU_API_KEY="your_key_here"' >> .env
```

### Run the Test Script

```bash
cd /Users/jasperpoc/pocs/dcatrader/dcabot

# With virtual environment
./dcabot-env/bin/python test_glm_api.py

# Or directly
python test_glm_api.py
```

---

## 📊 What the Test Does

### Test 1: Connection Check
- Verifies your API key works
- Tests basic API call

### Test 2: BTC Bullish Scenario
```
Market: BTCUSDT @ $42,500
Setup: All EMAs bullish, RSI 65, increasing volume
Expected: Probably BUY decision
```

### Test 3: SOL Crash Scenario
```
Market: SOLUSDT @ $165 (down from $185)
Setup: Strong downtrend, all EMAs bearish, panic selling
Expected: Probably SELL decision or avoid
```

---

## ✅ Expected Output

```
🔌 Testing GLM API connection...
✅ Connection successful!

============================================================
📊 Testing Scenario: BTC Bullish Setup
============================================================

⏳ Calling GLM API...
✅ Response received in 2.34s

============================================================
🤖 GLM TRADING DECISION
============================================================
Decision:    BUY
Confidence:  78/100
Risk Level:  MEDIUM
Stop Loss:   $41,850
Take Profit: $43,500

Reasoning:
Strong bullish setup with aligned EMAs across all timeframes.
RSI at 65 shows room for further upside. Increasing volume
confirms buying pressure. Good risk/reward at 1:3 ratio.
Entry at slight pullback to EMA20 offers optimal positioning.

============================================================

💰 API Usage:
   Input Tokens:  456
   Output Tokens: 234
   Total Cost:    $0.000116
   Response Time: 2.34s
```

---

## 🔍 Troubleshooting

### Error: "401 Unauthorized"
**Problem:** Invalid API key
**Solution:**
- Check you copied the full key
- Verify no extra spaces
- Generate a new key if needed

### Error: "Rate limit exceeded"
**Problem:** Too many calls too fast
**Solution:**
- Wait 60 seconds
- GLM has rate limits for free tier

### Error: "Insufficient balance"
**Problem:** No credits/balance
**Solution:**
- Add credits at https://open.bigmodel.cn/usercenter/balance
- Very cheap: $5 = ~3,300 calls!

### Error: "Connection timeout"
**Problem:** Network or API down
**Solution:**
- Check your internet connection
- Try again in a few minutes
- Check status at https://status.zhipuai.cn (if exists)

---

## 💡 Understanding the Results

### Good Signs ✅
- ✅ API responds in 2-5 seconds
- ✅ Decisions make logical sense
- ✅ Reasoning is detailed and coherent
- ✅ Confidence scores are reasonable (60-80%)
- ✅ Stop-loss and take-profit levels are sensible

### Red Flags ⚠️
- ❌ Nonsensical decisions (BUY in obvious downtrend)
- ❌ Very low confidence (<40%) consistently
- ❌ No reasoning provided
- ❌ Responses in Chinese only (should be English)
- ❌ JSON parsing errors

---

## 📈 Next Steps After Testing

### If Test Goes Well ✅

1. **Review Decision Quality**
   - Did GLM make sensible trading decisions?
   - Is the reasoning logical?
   - Are stop-loss/take-profit levels reasonable?

2. **Compare with Your Judgment**
   - For BTC bullish setup, would you buy?
   - For SOL crash, would you sell/avoid?
   - Does GLM's analysis match yours?

3. **Check Cost**
   - Is $0.0015 per decision acceptable?
   - At 3,000 calls/month = $4.50 (very cheap!)

4. **Proceed to Integration**
   - Build data pipeline (real-time market data)
   - Create GLMTradingStrategy class
   - Add to bot executor
   - Paper trade for 1 week

### If Test Fails ❌

1. **Debug API Connection**
   - Check error messages
   - Verify API key
   - Test with simple prompt

2. **Try Alternative**
   - Use GPT-3.5 ($30/month)
   - Use Claude ($150/month)
   - Use traditional adaptive algorithm (FREE)

---

## 💰 Cost Calculator

### Free Tier
- **Free Credits:** Usually enough for 100+ calls
- **Duration:** Test as much as you want!

### Paid Usage
```
GLM-4 Pricing:
- Input:  $0.11 per 1M tokens
- Output: $0.28 per 1M tokens

Average per call: $0.0015

Monthly Estimates:
- 1,000 calls:  $1.50
- 3,000 calls:  $4.50  ← Our target
- 10,000 calls: $15.00

Compare to:
- Claude: $150/month (100x more expensive!)
- GPT-4: $240/month (160x more expensive!)
```

---

## 📞 Support

### GLM/Zhipu AI Support
- **Website:** https://open.bigmodel.cn
- **Docs:** https://open.bigmodel.cn/dev/api
- **Status:** Check for any outages

### Our Support
- **Check logs:** Look at test script output
- **Review docs:** `docs/GLM_INTEGRATION_PLAN.md`
- **Ask questions:** Debug together!

---

## 🎯 Success Criteria

You're ready to proceed if:

✅ API key works
✅ Test script completes successfully
✅ Decisions make logical sense
✅ Reasoning is detailed and coherent
✅ Cost is acceptable ($0.0015 per call)
✅ Response time is fast (2-5 seconds)

---

## 🚀 Ready to Test?

### Quick Commands

```bash
# 1. Set your API key
export ZHIPU_API_KEY="your_key_here"

# 2. Run the test
cd /Users/jasperpoc/pocs/dcatrader/dcabot
python test_glm_api.py

# 3. Review results and decide next steps!
```

**Time to complete:** 10 minutes
**Cost:** FREE (with trial credits) or $0.003 total

---

**Let's revolutionize trading with AI!** 🤖💰
