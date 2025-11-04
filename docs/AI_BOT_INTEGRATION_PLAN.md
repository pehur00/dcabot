# Multi-Model AI Trading Bot Integration Plan

**Date:** November 4, 2025
**Goal:** Integrate AI-powered trading bots with model comparison dashboard

---

## 🎯 Overview

Add AI trading bots to the SaaS platform that:
- Use **multiple AI models** (GLM, DeepSeek, Claude, GPT) for comparison
- Make autonomous trading decisions based on **technical + sentiment + news**
- Log all reasoning and decision-making process
- Display performance comparison dashboard
- Run on same scheduler as Martingale bots

---

## 🏗️ Architecture

### High-Level Flow
```
┌─────────────────────────────────────────────────────────┐
│            SCHEDULED EXECUTOR (every 5 min)             │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────────┐    ┌──────────────────┐         │
│  │ Martingale Bots  │    │   AI Bots        │         │
│  │ (existing)       │    │   (NEW)          │         │
│  └──────────────────┘    └──────────────────┘         │
│                                   │                     │
│                          ┌────────┴────────┐           │
│                          │                 │           │
│                    ┌─────▼─────┐    ┌─────▼─────┐    │
│                    │ GLM-4.5   │    │ DeepSeek  │    │
│                    │ $1.20/mo  │    │ Free      │    │
│                    └───────────┘    └───────────┘    │
│                                                         │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
                  ┌────────────────┐
                  │   PostgreSQL   │
                  ├────────────────┤
                  │ - ai_decisions │
                  │ - ai_model_configs │
                  │ - trades       │
                  │ - bot_metrics  │
                  └────────────────┘
                           │
                           ▼
                  ┌────────────────┐
                  │  Dashboard UI  │
                  ├────────────────┤
                  │ - Model PNL Chart │
                  │ - Decision Logs │
                  │ - Reasoning Sidebar │
                  └────────────────┘
```

---

## 📊 Database Schema Changes

### New Tables

#### 1. `ai_model_configs`
```sql
CREATE TABLE ai_model_configs (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,           -- "GLM-4.5-Air", "DeepSeek-Chat", etc.
    provider VARCHAR(50) NOT NULL,        -- "z.ai", "deepseek", "anthropic", "openai"
    api_endpoint TEXT NOT NULL,
    model_identifier VARCHAR(100) NOT NULL, -- "glm-4.5-air", "deepseek-chat"
    cost_per_1k_input DECIMAL(10, 6),     -- $0.20 per 1M = 0.0002
    cost_per_1k_output DECIMAL(10, 6),    -- $1.10 per 1M = 0.0011
    logo_url TEXT,                        -- For UI display
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Seed data
INSERT INTO ai_model_configs (name, provider, api_endpoint, model_identifier, cost_per_1k_input, cost_per_1k_output, logo_url) VALUES
('GLM-4.5-Air', 'z.ai', 'https://api.z.ai/api/paas/v4/chat/completions', 'glm-4.5-air', 0.0002, 0.0011, '/static/logos/zhipu.png'),
('GLM-4.5-Flash', 'z.ai', 'https://api.z.ai/api/paas/v4/chat/completions', 'glm-4.5-flash', 0.0, 0.0, '/static/logos/zhipu.png'),
('DeepSeek-Chat', 'deepseek', 'https://api.deepseek.com/v1/chat/completions', 'deepseek-chat', 0.00027, 0.0011, '/static/logos/deepseek.png'),
('Claude-3.5-Sonnet', 'anthropic', 'https://api.anthropic.com/v1/messages', 'claude-3-5-sonnet-20241022', 0.003, 0.015, '/static/logos/anthropic.png');
```

#### 2. `ai_bots`
```sql
CREATE TABLE ai_bots (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    model_config_id INTEGER NOT NULL REFERENCES ai_model_configs(id),
    symbol VARCHAR(20) NOT NULL,          -- "BTCUSDT"
    side VARCHAR(10) NOT NULL,            -- "Long" or "Short"
    leverage INTEGER DEFAULT 5,
    max_position_size DECIMAL(10, 6) DEFAULT 0.03,  -- 3% of balance
    is_active BOOLEAN DEFAULT true,
    automatic_mode BOOLEAN DEFAULT true,

    -- API keys (encrypted)
    exchange_api_key TEXT NOT NULL,
    exchange_api_secret TEXT NOT NULL,
    ai_api_key TEXT NOT NULL,             -- For the AI model

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(user_id, name)
);

CREATE INDEX idx_ai_bots_user_active ON ai_bots(user_id, is_active);
```

#### 3. `ai_decisions`
```sql
CREATE TABLE ai_decisions (
    id SERIAL PRIMARY KEY,
    ai_bot_id INTEGER NOT NULL REFERENCES ai_bots(id) ON DELETE CASCADE,
    symbol VARCHAR(20) NOT NULL,

    -- Market data at decision time
    current_price DECIMAL(20, 8),
    ema20_1m DECIMAL(20, 8),
    ema50_5m DECIMAL(20, 8),
    ema100_1h DECIMAL(20, 8),
    rsi_14 DECIMAL(5, 2),
    volume_trend VARCHAR(50),

    -- AI Decision
    decision VARCHAR(10) NOT NULL,        -- "BUY", "SELL", "HOLD"
    confidence INTEGER,                   -- 0-100
    reasoning TEXT NOT NULL,              -- AI's explanation
    risk_level VARCHAR(10),               -- "LOW", "MEDIUM", "HIGH"
    stop_loss DECIMAL(20, 8),
    take_profit DECIMAL(20, 8),

    -- Action taken
    action_taken VARCHAR(10),             -- "EXECUTED", "SKIPPED", "MANUAL_OVERRIDE"
    skip_reason TEXT,                     -- Why was it skipped?

    -- Model performance
    input_tokens INTEGER,
    output_tokens INTEGER,
    api_cost DECIMAL(10, 6),              -- Cost of this call
    response_time_ms INTEGER,

    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_ai_decisions_bot ON ai_decisions(ai_bot_id, created_at DESC);
CREATE INDEX idx_ai_decisions_action ON ai_decisions(action_taken, created_at DESC);
```

#### 4. `ai_model_performance`
```sql
CREATE TABLE ai_model_performance (
    id SERIAL PRIMARY KEY,
    ai_bot_id INTEGER NOT NULL REFERENCES ai_bots(id) ON DELETE CASCADE,
    model_config_id INTEGER NOT NULL REFERENCES ai_model_configs(id),

    -- Snapshot metrics
    balance DECIMAL(20, 8),
    pnl_percentage DECIMAL(10, 4),
    total_trades INTEGER,
    winning_trades INTEGER,
    losing_trades INTEGER,
    win_rate DECIMAL(5, 2),

    -- Cost tracking
    total_api_cost DECIMAL(10, 4),
    total_api_calls INTEGER,

    snapshot_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_ai_performance_bot ON ai_model_performance(ai_bot_id, snapshot_at DESC);
```

---

## 🔧 Backend Implementation

### 1. AI Decision Engine (`strategies/AITradingStrategy.py`)

```python
class AITradingStrategy:
    def __init__(self, bot_config, model_config):
        self.bot_config = bot_config
        self.model_config = model_config
        self.api_key = decrypt_api_key(bot_config['ai_api_key'])

    def get_trading_decision(self, market_data: Dict) -> Dict:
        """
        Call AI model with enriched market data
        Returns: decision dict with reasoning
        """
        # Build comprehensive prompt
        prompt = self.build_enriched_prompt(market_data)

        # Call AI model
        start_time = time.time()
        response = self.call_ai_model(prompt)
        response_time = (time.time() - start_time) * 1000  # ms

        # Parse decision
        decision = self.parse_ai_response(response)
        decision['response_time_ms'] = response_time
        decision['api_cost'] = self.calculate_cost(response)

        # Log decision to database
        self.log_decision(market_data, decision)

        return decision

    def build_enriched_prompt(self, market_data: Dict) -> str:
        """
        Build comprehensive prompt with multiple data sources
        """
        return f"""
You are an expert cryptocurrency trading AI. Analyze ALL available data sources:

**TECHNICAL ANALYSIS:**
Symbol: {market_data['symbol']}
Current Price: ${market_data['current_price']:,.2f}

EMAs:
- EMA20 (1min): ${market_data['ema20_1m']:,.2f} ({'ABOVE' if market_data['current_price'] > market_data['ema20_1m'] else 'BELOW'} price)
- EMA50 (5min): ${market_data['ema50_5m']:,.2f}
- EMA100 (1h): ${market_data['ema100_1h']:,.2f}

Momentum:
- RSI(14): {market_data['rsi']} ({'OVERSOLD' if market_data['rsi'] < 30 else 'OVERBOUGHT' if market_data['rsi'] > 70 else 'NEUTRAL'})
- Volume Trend: {market_data['volume_trend']}

Price Changes:
- 24h: {market_data['change_24h']:+.2f}%
- 1h: {market_data['change_1h']:+.2f}%

**CURRENT POSITION:**
{market_data.get('current_position', 'None')}

**SENTIMENT ANALYSIS:**
{market_data.get('sentiment', 'No sentiment data available')}

**RECENT NEWS:**
{market_data.get('recent_news', 'No recent news')}

**TRADING RULES:**
- Only LONG positions (no shorts)
- Max position size: {self.bot_config['max_position_size'] * 100}% of balance
- Leverage: {self.bot_config['leverage']}x
- Always set stop-loss (2% below entry)

**YOUR TASK:**
Analyze all data sources (technical, sentiment, news) and provide:

1. **Decision:** BUY | SELL | HOLD
2. **Confidence:** 0-100 (based on signal strength)
3. **Reasoning:** 3-4 sentences explaining:
   - What technical signals support this?
   - What sentiment/news factors influenced this?
   - What are the key risks?
4. **Risk Level:** LOW | MEDIUM | HIGH
5. **Stop Loss:** Price level for stop loss
6. **Take Profit:** Price level for take profit

Output as JSON:
{{
  "decision": "BUY|SELL|HOLD",
  "confidence": 75,
  "reasoning": "Technical analysis shows...",
  "risk_level": "MEDIUM",
  "stop_loss": 67500.0,
  "take_profit": 70000.0
}}
"""

    def call_ai_model(self, prompt: str) -> Dict:
        """Call the configured AI model API"""
        endpoint = self.model_config['api_endpoint']
        model = self.model_config['model_identifier']

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "You are an expert trading AI."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 2000
        }

        response = requests.post(endpoint, headers=headers, json=payload, timeout=90)
        return response.json()
```

### 2. Market Data Fetcher (`data/market_data_fetcher.py`)

```python
class MarketDataFetcher:
    """Fetch comprehensive market data for AI analysis"""

    def fetch_all_data(self, symbol: str) -> Dict:
        """Fetch technical + sentiment + news data"""
        return {
            **self.fetch_technical_data(symbol),
            **self.fetch_sentiment_data(symbol),
            **self.fetch_news_data(symbol)
        }

    def fetch_technical_data(self, symbol: str) -> Dict:
        """Fetch from Binance API (like test_glm_api.py)"""
        # Reuse logic from test script
        pass

    def fetch_sentiment_data(self, symbol: str) -> Dict:
        """
        Fetch sentiment from social media / Fear & Greed Index

        Sources:
        - Alternative.me Fear & Greed Index
        - Twitter/X mentions (via API)
        - Reddit sentiment (via API)
        """
        sentiment_score = self.get_fear_greed_index()
        social_buzz = self.get_social_mentions(symbol)

        return {
            "sentiment": f"Fear & Greed: {sentiment_score}/100, Social buzz: {social_buzz}"
        }

    def fetch_news_data(self, symbol: str) -> Dict:
        """
        Fetch recent news headlines

        Sources:
        - CoinDesk API
        - CoinTelegraph RSS
        - Crypto News APIs
        """
        headlines = self.get_recent_headlines(symbol)

        return {
            "recent_news": "\n".join(headlines[:5])  # Top 5 headlines
        }
```

### 3. Executor Integration (`saas/execute_ai_bots.py`)

```python
def execute_ai_bot(bot_id: int):
    """Execute single AI bot's decision cycle"""

    # Get bot config
    bot = db.get_ai_bot(bot_id)
    model_config = db.get_model_config(bot['model_config_id'])

    # Fetch market data
    fetcher = MarketDataFetcher()
    market_data = fetcher.fetch_all_data(bot['symbol'])

    # Get AI decision
    strategy = AITradingStrategy(bot, model_config)
    decision = strategy.get_trading_decision(market_data)

    # Execute trade if confidence high enough
    if decision['decision'] != 'HOLD' and decision['confidence'] >= 70:
        if bot['automatic_mode']:
            execute_trade(bot, decision)
        else:
            log_decision_skipped(bot, decision, "Manual mode enabled")
    else:
        log_decision_skipped(bot, decision, f"Low confidence: {decision['confidence']}")

    # Update performance metrics
    update_ai_bot_metrics(bot_id)

def execute_all_ai_bots():
    """Called by scheduler every 5 minutes"""
    active_bots = db.get_active_ai_bots()

    for bot in active_bots:
        try:
            execute_ai_bot(bot['id'])
        except Exception as e:
            logger.error(f"AI bot {bot['id']} failed: {e}")
            notify_error(bot, e)
```

---

## 🎨 Frontend UI

### 1. AI Bot Comparison Dashboard (`/ai-bots`)

```html
<!-- saas/templates/ai_bot_dashboard.html -->

<div class="ai-dashboard">
    <!-- Header with Model Selector -->
    <div class="model-selector">
        <h2>AI Trading Bot Comparison</h2>
        <div class="model-chips">
            <button class="chip active" data-model="all">All Models</button>
            <button class="chip" data-model="glm">
                <img src="/static/logos/zhipu.png" /> GLM-4.5-Air
            </button>
            <button class="chip" data-model="deepseek">
                <img src="/static/logos/deepseek.png" /> DeepSeek
            </button>
            <button class="chip" data-model="claude">
                <img src="/static/logos/anthropic.png" /> Claude
            </button>
        </div>
    </div>

    <!-- Main Chart: PNL Comparison -->
    <div class="chart-container">
        <canvas id="modelComparisonChart"></canvas>
    </div>

    <!-- Stats Grid -->
    <div class="stats-grid">
        <div class="stat-card" v-for="model in models">
            <img :src="model.logo" class="model-logo" />
            <h3>{{ model.name }}</h3>
            <div class="metric">
                <label>PNL</label>
                <span :class="model.pnl >= 0 ? 'profit' : 'loss'">
                    {{ model.pnl >= 0 ? '+' : '' }}{{ model.pnl }}%
                </span>
            </div>
            <div class="metric">
                <label>Win Rate</label>
                <span>{{ model.win_rate }}%</span>
            </div>
            <div class="metric">
                <label>API Cost</label>
                <span>${{ model.total_cost }}</span>
            </div>
            <div class="metric">
                <label>Trades</label>
                <span>{{ model.total_trades }}</span>
            </div>
        </div>
    </div>

    <!-- Decision Log Table -->
    <div class="decision-log">
        <h3>Recent AI Decisions</h3>
        <table>
            <thead>
                <tr>
                    <th>Time</th>
                    <th>Model</th>
                    <th>Symbol</th>
                    <th>Decision</th>
                    <th>Confidence</th>
                    <th>Action</th>
                    <th>Details</th>
                </tr>
            </thead>
            <tbody>
                <!-- Populated via JavaScript -->
            </tbody>
        </table>
    </div>
</div>
```

### 2. Decision Detail Sidebar

```html
<!-- Sidebar that slides in when clicking "Details" -->
<div class="decision-sidebar" id="decisionSidebar">
    <div class="sidebar-header">
        <h3>AI Decision Details</h3>
        <button class="close-btn">&times;</button>
    </div>

    <div class="sidebar-content">
        <!-- Model Info -->
        <div class="section">
            <h4><img src="{{ decision.model_logo }}" /> {{ decision.model_name }}</h4>
            <div class="timestamp">{{ decision.created_at }}</div>
        </div>

        <!-- Market Conditions -->
        <div class="section">
            <h4>Market Conditions</h4>
            <div class="data-grid">
                <div><label>Price:</label> ${{ decision.current_price }}</div>
                <div><label>RSI:</label> {{ decision.rsi_14 }}</div>
                <div><label>Volume:</label> {{ decision.volume_trend }}</div>
                <div><label>24h Change:</label> {{ decision.change_24h }}%</div>
            </div>
        </div>

        <!-- AI Reasoning -->
        <div class="section">
            <h4>AI Reasoning</h4>
            <div class="reasoning-box">
                <p>{{ decision.reasoning }}</p>
            </div>
        </div>

        <!-- Decision -->
        <div class="section">
            <h4>Decision</h4>
            <div class="decision-box" :class="decision.decision.toLowerCase()">
                <div class="decision-action">{{ decision.decision }}</div>
                <div class="confidence-bar">
                    <div class="confidence-fill" :style="{width: decision.confidence + '%'}"></div>
                    <span>{{ decision.confidence }}% Confidence</span>
                </div>
                <div class="risk-level">Risk: {{ decision.risk_level }}</div>
            </div>
        </div>

        <!-- Action Taken -->
        <div class="section">
            <h4>Action Taken</h4>
            <div class="action-status" :class="decision.action_taken.toLowerCase()">
                {{ decision.action_taken }}
            </div>
            <div class="skip-reason" v-if="decision.skip_reason">
                {{ decision.skip_reason }}
            </div>
        </div>

        <!-- Trade Details (if executed) -->
        <div class="section" v-if="decision.trade_id">
            <h4>Trade Executed</h4>
            <div class="trade-details">
                <div><label>Entry:</label> ${{ decision.entry_price }}</div>
                <div><label>Stop Loss:</label> ${{ decision.stop_loss }}</div>
                <div><label>Take Profit:</label> ${{ decision.take_profit }}</div>
                <div><label>Size:</label> {{ decision.position_size }}</div>
            </div>
        </div>

        <!-- Performance -->
        <div class="section">
            <h4>API Performance</h4>
            <div class="api-stats">
                <div><label>Response Time:</label> {{ decision.response_time_ms }}ms</div>
                <div><label>Tokens:</label> {{ decision.input_tokens + decision.output_tokens }}</div>
                <div><label>Cost:</label> ${{ decision.api_cost }}</div>
            </div>
        </div>
    </div>
</div>
```

### 3. Chart.js Configuration

```javascript
// Multi-line chart comparing model PNL over time
const ctx = document.getElementById('modelComparisonChart').getContext('2d');
const modelChart = new Chart(ctx, {
    type: 'line',
    data: {
        labels: timestamps,  // Fetched from API
        datasets: [
            {
                label: 'GLM-4.5-Air',
                data: glmPnlData,
                borderColor: '#4A90E2',
                backgroundColor: 'rgba(74, 144, 226, 0.1)',
                borderWidth: 2,
            },
            {
                label: 'DeepSeek',
                data: deepseekPnlData,
                borderColor: '#50E3C2',
                backgroundColor: 'rgba(80, 227, 194, 0.1)',
                borderWidth: 2,
            },
            {
                label: 'Claude',
                data: claudePnlData,
                borderColor: '#F5A623',
                backgroundColor: 'rgba(245, 166, 35, 0.1)',
                borderWidth: 2,
            }
        ]
    },
    options: {
        responsive: true,
        plugins: {
            legend: { display: true, position: 'top' },
            tooltip: {
                callbacks: {
                    label: function(context) {
                        return context.dataset.label + ': ' +
                               (context.parsed.y >= 0 ? '+' : '') +
                               context.parsed.y.toFixed(2) + '%';
                    }
                }
            }
        },
        scales: {
            y: {
                beginAtZero: true,
                ticks: {
                    callback: function(value) {
                        return (value >= 0 ? '+' : '') + value + '%';
                    }
                }
            }
        }
    }
});
```

---

## 📅 Implementation Roadmap

### Phase 1: Backend Foundation (Week 1)
- [ ] Create database migrations (ai_model_configs, ai_bots, ai_decisions, ai_model_performance)
- [ ] Implement `AITradingStrategy` class
- [ ] Create `MarketDataFetcher` with technical data
- [ ] Test GLM-4.5-Air integration end-to-end

**Deliverable:** AI bot can make decisions and log to database

---

### Phase 2: Scheduler Integration (Week 1-2)
- [ ] Create `execute_ai_bots.py`
- [ ] Add to Render cron job (runs every 5 min alongside Martingale bots)
- [ ] Implement trade execution logic
- [ ] Add error handling and Telegram notifications

**Deliverable:** AI bots running autonomously on schedule

---

### Phase 3: Multi-Model Support (Week 2)
- [ ] Add DeepSeek model config
- [ ] Add Claude model config
- [ ] Implement model abstraction layer
- [ ] Create cost tracking per model
- [ ] Test all 3 models in parallel

**Deliverable:** 3+ AI models running simultaneously

---

### Phase 4: Enhanced Prompts (Week 2-3)
- [ ] Integrate Fear & Greed Index API
- [ ] Add Twitter/social sentiment (via API)
- [ ] Add crypto news headlines (CoinDesk/CoinTelegraph)
- [ ] Enrich prompt with all data sources
- [ ] Test decision quality improvement

**Deliverable:** AI receives technical + sentiment + news data

---

### Phase 5: Frontend Dashboard (Week 3-4)
- [ ] Create `/ai-bots` route and template
- [ ] Build model comparison chart (Chart.js)
- [ ] Create decision log table
- [ ] Build decision detail sidebar
- [ ] Add model filtering and date range selection

**Deliverable:** Beautiful AI bot comparison dashboard

---

### Phase 6: Bot Management UI (Week 4)
- [ ] Create AI bot form (symbol, model, max position, etc.)
- [ ] Add API key management for AI models
- [ ] Build bot edit/delete functionality
- [ ] Add manual override controls

**Deliverable:** Users can create/manage AI bots

---

### Phase 7: Testing & Optimization (Week 4-5)
- [ ] Paper trade for 1 week
- [ ] A/B test models on same market conditions
- [ ] Optimize prompts based on results
- [ ] Fine-tune confidence thresholds
- [ ] Document best practices

**Deliverable:** Production-ready AI trading bots

---

## 💰 Expected Costs

| Model | Calls/Day | Monthly Calls | Monthly Cost |
|-------|-----------|---------------|--------------|
| GLM-4.5-Flash | 288 (every 5min) | ~8,640 | **FREE** |
| GLM-4.5-Air | 288 | ~8,640 | **$2.50** |
| DeepSeek | 288 | ~8,640 | **$3.50** |
| Claude | 288 | ~8,640 | **$150** |

**Recommended:** Run GLM-4.5-Air + DeepSeek simultaneously = **$6/month total**

Compare with Claude-only: **Save $144/month** per bot!

---

## 🎯 Success Metrics

### Decision Quality
- ✅ Win rate > 60%
- ✅ Avg profit per trade > 1.5%
- ✅ Max drawdown < 10%
- ✅ Reasoning is coherent and actionable

### System Performance
- ✅ Decision response time < 10s
- ✅ All decisions logged to database
- ✅ Dashboard loads < 2s
- ✅ No missed executions

### Cost Efficiency
- ✅ Monthly API cost < $10/bot
- ✅ Cost per decision < $0.002
- ✅ ROI positive (profit > API cost)

---

## 🚀 Next Steps

**Option A: Start with Backend (Recommended)**
1. Create database migrations
2. Implement `AITradingStrategy`
3. Test with GLM-4.5-Air
4. Add to scheduler

**Option B: Start with UI Mockup**
1. Create dashboard HTML/CSS
2. Use fake data for charts
3. Design decision sidebar
4. Get user feedback on UX

**Option C: Enhance Prompts First**
1. Integrate sentiment APIs
2. Add news fetching
3. Test with current test_glm_api.py
4. Compare decision quality

---

**Which approach would you like to start with?**

Let me know and I'll begin implementation! 🤖💰
