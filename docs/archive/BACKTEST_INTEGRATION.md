# Backtest Integration - SaaS Frontend

## Overview

Add backtesting to the web interface so users can **test their bot configuration before going live**. This is a killer feature that builds confidence and reduces risk.

## User Flow

```
1. User creates/edits bot configuration
   ↓
2. Clicks "Test Configuration" button
   ↓
3. Backtest runs (30-60 seconds)
   - Shows progress bar
   - "Testing BTCUSDT over 30 days..."
   ↓
4. Results displayed
   - Performance metrics (PnL, win rate, drawdown)
   - Balance chart (interactive)
   - Trade history table
   - Recommendation (Good/Caution/Risky)
   ↓
5. User decides: "Deploy Bot" or "Adjust Settings"
```

## Architecture

### Backend: Flask API Endpoint

```python
# saas/api/backtest.py

from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json

backtest_bp = Blueprint('backtest', __name__)

# Thread pool for running backtests without blocking
executor = ThreadPoolExecutor(max_workers=3)  # Max 3 concurrent backtests


@backtest_bp.route('/api/backtest/run', methods=['POST'])
@login_required
def run_backtest():
    """
    Run backtest for given configuration

    Request body:
    {
        "symbol": "BTCUSDT",
        "side": "Long",
        "leverage": 10,
        "balance": 200,
        "days": 30,
        "max_margin_pct": 0.50,
        "exchange": "phemex"
    }

    Returns:
    {
        "status": "success",
        "metrics": {...},
        "chart_data": {...},
        "trades": [...],
        "recommendation": "good"
    }
    """
    data = request.json

    # Validate inputs
    required = ['symbol', 'side', 'leverage', 'balance', 'days']
    if not all(k in data for k in required):
        return jsonify({'error': 'Missing required fields'}), 400

    # Run backtest in thread pool (non-blocking)
    try:
        result = executor.submit(
            run_backtest_sync,
            symbol=data['symbol'],
            side=data['side'],
            leverage=data.get('leverage', 10),
            balance=data.get('balance', 200),
            days=data.get('days', 30),
            max_margin_pct=data.get('max_margin_pct', 0.50),
            exchange=data.get('exchange', 'binance'),  # Default to binance for backtest data
            user_id=current_user.id
        ).result(timeout=120)  # 2 min timeout

        return jsonify(result), 200

    except Exception as e:
        return jsonify({
            'error': f'Backtest failed: {str(e)}'
        }), 500


def run_backtest_sync(symbol, side, leverage, balance, days, max_margin_pct, exchange, user_id):
    """
    Run backtest synchronously (called in thread pool)
    Returns JSON-serializable results
    """
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

    from backtest.backtest import BacktestEngine
    from backtest.data_fetcher import fetch_historical_data_ccxt
    from strategies.MartingaleTradingStrategy import MartingaleTradingStrategy
    from clients.PhemexClient import PhemexClient
    import logging

    # Setup dummy client (for backtest only, doesn't need real API keys)
    logger = logging.getLogger(__name__)
    client = PhemexClient(api_key='dummy', api_secret='dummy', logger=logger, testnet=True)

    # Create strategy with config
    strategy = MartingaleTradingStrategy(client=client, logger=logger, notifier=None)
    strategy.leverage = leverage
    strategy.max_margin_pct = max_margin_pct

    # Create backtest engine
    engine = BacktestEngine(
        client=client,
        strategy=strategy,
        initial_balance=balance,
        max_margin_pct=max_margin_pct
    )

    # Fetch historical data
    df = fetch_historical_data_ccxt(
        symbol=symbol,
        interval_minutes=1,  # Always 1-minute candles
        days=days,
        source=exchange
    )

    if df.empty:
        raise ValueError(f"No historical data available for {symbol}")

    # Run backtest
    engine.run_backtest(
        df=df,
        symbol=symbol,
        pos_side=side,
        ema_interval=1,
        automatic_mode=True
    )

    # Extract results
    results = {
        'status': 'success',
        'metrics': {
            'initial_balance': engine.initial_balance,
            'final_balance': engine.balance,
            'total_pnl': engine.balance - engine.initial_balance,
            'total_return_pct': ((engine.balance - engine.initial_balance) / engine.initial_balance) * 100,
            'total_trades': engine.total_trades,
            'winning_trades': engine.winning_trades,
            'losing_trades': engine.losing_trades,
            'win_rate': (engine.winning_trades / engine.total_trades * 100) if engine.total_trades > 0 else 0,
            'max_drawdown': engine.max_drawdown * 100,  # As percentage
            'total_fees': engine.total_fees,
            'sharpe_ratio': calculate_sharpe_ratio(engine.balance_history),
        },
        'chart_data': {
            'timestamps': [record['timestamp'].isoformat() for record in engine.balance_history],
            'balance': [record['balance'] for record in engine.balance_history],
            'total_value': [record['total_value'] for record in engine.balance_history],
            'position_margin': [record.get('position_margin', 0) for record in engine.balance_history],
            'prices': [record['price'] for record in engine.price_history],
            'ema_200': [record['ema_200'] for record in engine.price_history],
        },
        'trades': [
            {
                'timestamp': trade['timestamp'].isoformat(),
                'action': trade['action'],
                'price': trade['price'],
                'quantity': trade['qty'],
                'pnl': trade.get('pnl', 0),
                'balance_after': trade.get('balance_after', 0)
            }
            for trade in engine.trades[-20:]  # Last 20 trades only
        ],
        'recommendation': get_recommendation(engine)
    }

    return results


def calculate_sharpe_ratio(balance_history, risk_free_rate=0.02):
    """Calculate annualized Sharpe ratio"""
    if len(balance_history) < 2:
        return 0

    returns = []
    for i in range(1, len(balance_history)):
        prev_val = balance_history[i-1]['total_value']
        curr_val = balance_history[i]['total_value']
        returns.append((curr_val - prev_val) / prev_val if prev_val > 0 else 0)

    if not returns:
        return 0

    import numpy as np
    mean_return = np.mean(returns)
    std_return = np.std(returns)

    if std_return == 0:
        return 0

    # Annualize (assuming 5-min intervals, 288 per day)
    annualized_return = mean_return * 288 * 365
    annualized_volatility = std_return * np.sqrt(288 * 365)

    sharpe = (annualized_return - risk_free_rate) / annualized_volatility if annualized_volatility > 0 else 0

    return round(sharpe, 2)


def get_recommendation(engine):
    """
    Provide recommendation based on backtest results
    Returns: "excellent", "good", "caution", "risky"
    """
    total_return = ((engine.balance - engine.initial_balance) / engine.initial_balance) * 100
    win_rate = (engine.winning_trades / engine.total_trades * 100) if engine.total_trades > 0 else 0
    max_drawdown = engine.max_drawdown * 100

    # Excellent: High return, high win rate, low drawdown
    if total_return > 15 and win_rate > 85 and max_drawdown < 15:
        return "excellent"

    # Good: Profitable with reasonable metrics
    elif total_return > 5 and win_rate > 70 and max_drawdown < 25:
        return "good"

    # Caution: Breakeven or small profit, needs watching
    elif total_return > -5 and max_drawdown < 40:
        return "caution"

    # Risky: Negative return or high drawdown
    else:
        return "risky"
```

### Frontend: Backtest UI

Create `saas/templates/backtest_modal.html`:

```html
<!-- Backtest Modal (shown when user clicks "Test Configuration") -->
<div id="backtestModal" class="modal" x-data="backtestData()" x-show="show" @keydown.escape="show = false">
    <div class="modal-content">
        <!-- Header -->
        <div class="modal-header">
            <h2>Test Bot Configuration</h2>
            <button @click="show = false">&times;</button>
        </div>

        <!-- Backtest Form -->
        <div class="modal-body" x-show="!running && !results">
            <form @submit.prevent="runBacktest()">
                <div class="form-group">
                    <label>Symbol</label>
                    <input type="text" x-model="config.symbol" required>
                </div>

                <div class="form-group">
                    <label>Side</label>
                    <select x-model="config.side">
                        <option value="Long">Long</option>
                        <option value="Short">Short</option>
                    </select>
                </div>

                <div class="form-group">
                    <label>Initial Balance (USDT)</label>
                    <input type="number" x-model="config.balance" min="50" step="10" required>
                </div>

                <div class="form-group">
                    <label>Test Period (days)</label>
                    <select x-model="config.days">
                        <option value="7">7 days (Quick)</option>
                        <option value="14">14 days</option>
                        <option value="30" selected>30 days (Recommended)</option>
                        <option value="60">60 days</option>
                        <option value="90">90 days (Thorough)</option>
                    </select>
                </div>

                <div class="form-group">
                    <label>Leverage</label>
                    <input type="number" x-model="config.leverage" min="1" max="20" required>
                </div>

                <div class="form-group">
                    <label>Max Margin Cap (%)</label>
                    <input type="number" x-model="config.max_margin_pct" min="0" max="1" step="0.05" required>
                    <small>Percentage of balance to use as margin (0.50 = 50%)</small>
                </div>

                <button type="submit" class="btn btn-primary">
                    🧪 Run Backtest
                </button>
            </form>
        </div>

        <!-- Loading State -->
        <div class="modal-body text-center" x-show="running">
            <div class="spinner"></div>
            <p class="mt-3">Testing configuration...</p>
            <p class="text-muted" x-text="'Analyzing ' + config.symbol + ' over ' + config.days + ' days'"></p>
            <div class="progress-bar">
                <div class="progress-fill" :style="'width: ' + progress + '%'"></div>
            </div>
        </div>

        <!-- Results -->
        <div class="modal-body" x-show="results">
            <!-- Recommendation Badge -->
            <div class="recommendation-badge" :class="'rec-' + results.recommendation">
                <span x-show="results.recommendation === 'excellent'">🌟 Excellent Configuration!</span>
                <span x-show="results.recommendation === 'good'">✅ Good Configuration</span>
                <span x-show="results.recommendation === 'caution'">⚠️ Use with Caution</span>
                <span x-show="results.recommendation === 'risky'">⛔ Risky Configuration</span>
            </div>

            <!-- Performance Metrics -->
            <div class="metrics-grid">
                <div class="metric-card">
                    <div class="metric-label">Total Return</div>
                    <div class="metric-value" :class="results.metrics.total_return_pct >= 0 ? 'positive' : 'negative'">
                        <span x-text="results.metrics.total_return_pct.toFixed(2)"></span>%
                    </div>
                </div>

                <div class="metric-card">
                    <div class="metric-label">Win Rate</div>
                    <div class="metric-value">
                        <span x-text="results.metrics.win_rate.toFixed(1)"></span>%
                    </div>
                </div>

                <div class="metric-card">
                    <div class="metric-label">Max Drawdown</div>
                    <div class="metric-value" :class="results.metrics.max_drawdown < 20 ? 'positive' : 'negative'">
                        <span x-text="results.metrics.max_drawdown.toFixed(2)"></span>%
                    </div>
                </div>

                <div class="metric-card">
                    <div class="metric-label">Total Trades</div>
                    <div class="metric-value">
                        <span x-text="results.metrics.total_trades"></span>
                    </div>
                </div>

                <div class="metric-card">
                    <div class="metric-label">Final Balance</div>
                    <div class="metric-value">
                        $<span x-text="results.metrics.final_balance.toFixed(2)"></span>
                    </div>
                </div>

                <div class="metric-card">
                    <div class="metric-label">Sharpe Ratio</div>
                    <div class="metric-value">
                        <span x-text="results.metrics.sharpe_ratio"></span>
                    </div>
                </div>
            </div>

            <!-- Balance Chart -->
            <div class="chart-container mt-4">
                <canvas id="backtestChart"></canvas>
            </div>

            <!-- Recent Trades -->
            <div class="trades-table mt-4">
                <h3>Recent Trades (Last 20)</h3>
                <table>
                    <thead>
                        <tr>
                            <th>Time</th>
                            <th>Action</th>
                            <th>Price</th>
                            <th>Quantity</th>
                            <th>PnL</th>
                        </tr>
                    </thead>
                    <tbody>
                        <template x-for="trade in results.trades">
                            <tr>
                                <td x-text="new Date(trade.timestamp).toLocaleString()"></td>
                                <td x-text="trade.action"></td>
                                <td>$<span x-text="trade.price.toFixed(4)"></span></td>
                                <td x-text="trade.quantity.toFixed(4)"></td>
                                <td :class="trade.pnl >= 0 ? 'positive' : 'negative'">
                                    $<span x-text="trade.pnl.toFixed(2)"></span>
                                </td>
                            </tr>
                        </template>
                    </tbody>
                </table>
            </div>

            <!-- Actions -->
            <div class="modal-actions mt-4">
                <button @click="show = false; results = null" class="btn btn-secondary">
                    Close
                </button>
                <button @click="deployBot()" class="btn btn-primary" x-show="results.recommendation !== 'risky'">
                    🚀 Deploy Bot with This Config
                </button>
                <button @click="adjustSettings()" class="btn btn-warning" x-show="results.recommendation === 'risky'">
                    ⚙️ Adjust Settings
                </button>
            </div>
        </div>
    </div>
</div>

<script>
function backtestData() {
    return {
        show: false,
        running: false,
        progress: 0,
        results: null,
        config: {
            symbol: 'BTCUSDT',
            side: 'Long',
            balance: 200,
            days: 30,
            leverage: 10,
            max_margin_pct: 0.50
        },

        async runBacktest() {
            this.running = true;
            this.progress = 0;

            // Simulate progress (actual backtest runs in backend)
            const progressInterval = setInterval(() => {
                if (this.progress < 90) {
                    this.progress += 10;
                }
            }, 3000);

            try {
                const response = await fetch('/api/backtest/run', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(this.config)
                });

                clearInterval(progressInterval);
                this.progress = 100;

                if (!response.ok) {
                    throw new Error('Backtest failed');
                }

                this.results = await response.json();
                this.renderChart();

            } catch (error) {
                alert('Backtest failed: ' + error.message);
            } finally {
                this.running = false;
            }
        },

        renderChart() {
            const ctx = document.getElementById('backtestChart').getContext('2d');

            new Chart(ctx, {
                type: 'line',
                data: {
                    labels: this.results.chart_data.timestamps.map(t => new Date(t).toLocaleDateString()),
                    datasets: [
                        {
                            label: 'Total Value',
                            data: this.results.chart_data.total_value,
                            borderColor: 'rgb(75, 192, 192)',
                            backgroundColor: 'rgba(75, 192, 192, 0.1)',
                            fill: true
                        },
                        {
                            label: 'Balance',
                            data: this.results.chart_data.balance,
                            borderColor: 'rgb(54, 162, 235)',
                            fill: false
                        }
                    ]
                },
                options: {
                    responsive: true,
                    plugins: {
                        title: {
                            display: true,
                            text: 'Balance Over Time'
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: false
                        }
                    }
                }
            });
        },

        deployBot() {
            // Save bot config and deploy
            window.location.href = '/bots/create?prefill=' + encodeURIComponent(JSON.stringify(this.config));
        },

        adjustSettings() {
            // Close modal, keep config for editing
            this.show = false;
            this.results = null;
        }
    };
}
</script>

<style>
/* Modal styles */
.modal {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
}

.modal-content {
    background: white;
    border-radius: 8px;
    padding: 2rem;
    max-width: 900px;
    max-height: 90vh;
    overflow-y: auto;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

.metrics-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 1rem;
    margin-top: 1rem;
}

.metric-card {
    padding: 1rem;
    border: 1px solid #e5e7eb;
    border-radius: 6px;
    text-align: center;
}

.metric-label {
    font-size: 0.875rem;
    color: #6b7280;
    margin-bottom: 0.5rem;
}

.metric-value {
    font-size: 1.5rem;
    font-weight: bold;
}

.metric-value.positive {
    color: #10b981;
}

.metric-value.negative {
    color: #ef4444;
}

.recommendation-badge {
    padding: 1rem;
    border-radius: 6px;
    text-align: center;
    font-weight: bold;
    margin-bottom: 1.5rem;
}

.rec-excellent {
    background: #d1fae5;
    color: #065f46;
}

.rec-good {
    background: #dbeafe;
    color: #1e40af;
}

.rec-caution {
    background: #fef3c7;
    color: #92400e;
}

.rec-risky {
    background: #fee2e2;
    color: #991b1b;
}

.progress-bar {
    width: 100%;
    height: 8px;
    background: #e5e7eb;
    border-radius: 4px;
    overflow: hidden;
    margin-top: 1rem;
}

.progress-fill {
    height: 100%;
    background: #3b82f6;
    transition: width 0.3s ease;
}

.spinner {
    border: 4px solid #f3f4f6;
    border-top: 4px solid #3b82f6;
    border-radius: 50%;
    width: 40px;
    height: 40px;
    animation: spin 1s linear infinite;
    margin: 0 auto;
}

@keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}
</style>
```

### Integration into Bot Creation Flow

Update `saas/templates/bot_create.html` to include backtest button:

```html
<!-- In bot creation form -->
<div class="form-section">
    <h3>Trading Configuration</h3>

    <!-- ... existing fields ... -->

    <div class="test-config-section">
        <button type="button"
                class="btn btn-secondary"
                @click="$dispatch('open-backtest', {
                    symbol: form.symbol,
                    side: form.side,
                    balance: form.balance,
                    leverage: form.leverage,
                    max_margin_pct: form.max_margin_pct
                })">
            🧪 Test This Configuration First
        </button>
        <p class="help-text">
            Run a 30-day backtest to see how this bot would have performed
        </p>
    </div>
</div>

<!-- Include backtest modal -->
<div x-data @open-backtest.window="
    $refs.backtestModal.show = true;
    $refs.backtestModal.config = $event.detail;
" x-ref="backtestModal">
    {{ include('backtest_modal.html') }}
</div>
```

## Features

### 1. **Quick Test**
- Click button → backtest runs → see results in 30-60 seconds
- No need to deploy and wait

### 2. **Visual Feedback**
- Balance chart shows performance over time
- Color-coded metrics (green = good, red = bad)
- Recommendation badge (Excellent/Good/Caution/Risky)

### 3. **Smart Recommendations**
```python
Excellent: Return >15%, Win rate >85%, Drawdown <15%
Good:      Return >5%,  Win rate >70%, Drawdown <25%
Caution:   Return >-5%,                Drawdown <40%
Risky:     Anything worse
```

### 4. **One-Click Deploy**
- If backtest looks good → "Deploy Bot with This Config" button
- Auto-fills bot creation form with tested config

## Performance Considerations

### Backend Optimization

1. **Thread Pool**: Run backtests in separate threads (non-blocking)
   ```python
   executor = ThreadPoolExecutor(max_workers=3)
   ```

2. **Timeout**: 2-minute max per backtest
   ```python
   result = executor.submit(...).result(timeout=120)
   ```

3. **Rate Limiting**: Max 3 backtests per user per hour
   ```python
   @limiter.limit("3 per hour")
   ```

4. **Caching**: Cache backtest results for 1 hour
   ```python
   cache_key = f"backtest:{symbol}:{days}:{config_hash}"
   ```

### Frontend Optimization

1. **Progress Bar**: Fake progress (actual backtest time varies)
2. **Lazy Load Charts**: Only render chart when results ready
3. **Debounce**: Prevent double-clicks

## Database Schema Addition

Add backtest results table (optional, for history):

```sql
CREATE TABLE backtest_results (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    symbol VARCHAR(20),
    side VARCHAR(10),
    days INTEGER,
    total_return DECIMAL(10,4),
    win_rate DECIMAL(5,2),
    max_drawdown DECIMAL(5,2),
    recommendation VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_backtest_user ON backtest_results(user_id);
```

## MVP Implementation (Week 1)

**Minimum viable backtest feature**:

1. ✅ API endpoint: `/api/backtest/run`
2. ✅ Simple modal with form
3. ✅ Show 6 key metrics (return, win rate, drawdown, trades, balance, Sharpe)
4. ✅ Line chart (balance over time)
5. ✅ Recommendation badge
6. ✅ "Deploy" button

**Time estimate**: 1 day of development

## Future Enhancements (v1.1)

- [ ] Compare multiple configurations side-by-side
- [ ] Monte Carlo simulation (best/worst/average scenarios)
- [ ] Downloadable PDF report
- [ ] Share backtest results (public link)
- [ ] Backtest history (view past tests)
- [ ] Parameter sweep (test multiple leverages/margins)
- [ ] Multi-symbol backtesting
- [ ] Custom date ranges

## User Benefits

1. **Confidence**: "I tested it, it worked, let's deploy"
2. **Risk Reduction**: Avoid bad configurations
3. **Learning**: Understand how bot behaves
4. **Optimization**: Try different settings, pick the best
5. **Transparency**: Users see exactly what to expect

## Example UX Flow

```
User: "I want to trade BTCUSDT Long with 10x leverage"

[Fills out bot form]

User clicks: "🧪 Test This Configuration First"

[Modal opens, shows form pre-filled]

User clicks: "Run Backtest"

[Progress bar: "Testing BTCUSDT over 30 days..."]

30 seconds later:

✅ Good Configuration
Total Return: +12.5%
Win Rate: 78%
Max Drawdown: 18%

[Shows balance chart going up]

User: "Looks good!"

User clicks: "🚀 Deploy Bot with This Config"

[Bot created and deployed]
```

## Cost & Performance

- **Execution Time**: 30-60 seconds (30-day backtest)
- **Server Load**: Low (3 concurrent max via thread pool)
- **Data Source**: Binance public API (free, no auth needed)
- **Storage**: Minimal (cache results temporarily)

## Next Steps

1. Implement `saas/api/backtest.py` (backend)
2. Create `saas/templates/backtest_modal.html` (frontend)
3. Test with real symbols
4. Add to bot creation flow
5. 🎉 Ship it!

This feature will make your SaaS stand out from competitors who just let users deploy blindly! 🚀
