# DCA Bot - Product Roadmap

This document outlines the development roadmap for the DCA Bot trading platform.

## Current Status (November 2025)

### ✅ Phase 1: SaaS Platform Foundation - COMPLETE

**Multi-User Web Platform**
- ✅ Flask web application with Gunicorn
- ✅ User authentication system
- ✅ PostgreSQL database integration
- ✅ Encrypted API credential storage
- ✅ Multi-bot management per user
- ✅ Render.com deployment

**Authentication & Security**
- ✅ Google OAuth integration
- ✅ Password-based authentication
- ✅ Admin approval workflow
- ✅ Password reset functionality
- ✅ Fernet encryption for API keys
- ✅ Session management

**Bot Management Dashboard**
- ✅ Create/edit/delete bots
- ✅ Configure trading pairs
- ✅ Start/stop bots individually
- ✅ Real-time bot status monitoring
- ✅ Trading pair configuration UI

**Performance Analytics**
- ✅ Balance & position charts
- ✅ Unrealized PnL tracking
- ✅ Margin level monitoring
- ✅ Trade history display
- ✅ Execution metrics logging

**Database Infrastructure**
- ✅ Automatic migration system (SQL-based)
- ✅ Migration tracking and versioning
- ✅ Production database setup (Digital Ocean)
- ✅ Schema management tools

**Deployment & Operations**
- ✅ Render web service deployment
- ✅ Cron-based bot execution (5-minute intervals)
- ✅ Health check endpoints
- ✅ Auto-deploy from GitHub
- ✅ Zero-downtime deployments

---

## 🚀 Phase 2: Backtesting Integration (Next Priority)

### Goal
Integrate the existing backtesting framework into the SaaS web dashboard, allowing users to test strategies before running them with real funds.

---

### 2A. Weekly Backtest Dashboard - ✅ COMPLETE

**Goal**: Display weekly backtest performance for major symbols on the front page, showing which pairs are performing best with default strategy settings.

**Status**: Fully implemented, tested, and deployed to render.yaml. Front page now displays weekly backtest results with professional dark-themed performance cards.

**Database Schema (Migration 004)**
- [x] Create migration file `saas/migrations/004_add_backtest_tables.sql` with:
  - `backtest_configs` table - Stores which symbols to test weekly
  - `backtest_results` table - Stores weekly backtest outcomes
  - `backtest_trades` table - Detailed trade logs (optional, for drill-down)
  - Default symbol configuration via INSERT statements
  - All indexes for performance

  ```sql
  -- Migration: Add backtest tables and weekly performance tracking
  -- Date: 2025-11-02
  -- Description: Tables for storing weekly backtest results to display on front page

  -- Stores which symbols to test weekly
  CREATE TABLE IF NOT EXISTS backtest_configs (
      id SERIAL PRIMARY KEY,
      symbol VARCHAR(50) NOT NULL UNIQUE,
      side VARCHAR(10) NOT NULL,
      leverage INTEGER DEFAULT 10,
      interval INTEGER DEFAULT 1,
      is_active BOOLEAN DEFAULT true,
      category VARCHAR(50),
      created_at TIMESTAMP DEFAULT NOW(),
      updated_at TIMESTAMP DEFAULT NOW()
  );

  -- Stores weekly backtest outcomes
  CREATE TABLE IF NOT EXISTS backtest_results (
      id SERIAL PRIMARY KEY,
      symbol VARCHAR(50) NOT NULL,
      side VARCHAR(10) NOT NULL,
      leverage INTEGER NOT NULL,
      interval INTEGER NOT NULL,
      test_period_days INTEGER NOT NULL,
      start_date TIMESTAMP NOT NULL,
      end_date TIMESTAMP NOT NULL,
      initial_balance DECIMAL(20,8) NOT NULL,
      final_balance DECIMAL(20,8) NOT NULL,
      profit_loss DECIMAL(20,8) NOT NULL,
      profit_loss_pct DECIMAL(10,4) NOT NULL,
      max_drawdown_pct DECIMAL(10,4),
      total_trades INTEGER DEFAULT 0,
      winning_trades INTEGER DEFAULT 0,
      losing_trades INTEGER DEFAULT 0,
      win_rate DECIMAL(5,2),
      max_position_size DECIMAL(20,8),
      max_margin_used_pct DECIMAL(5,2),
      liquidation_occurred BOOLEAN DEFAULT false,
      executed_at TIMESTAMP DEFAULT NOW(),
      execution_duration_seconds INTEGER,
      data_source VARCHAR(50),
      status VARCHAR(20) DEFAULT 'completed',
      error_message TEXT,
      UNIQUE(symbol, side, leverage, DATE(executed_at))
  );

  -- Detailed trade log for each backtest
  CREATE TABLE IF NOT EXISTS backtest_trades (
      id SERIAL PRIMARY KEY,
      backtest_result_id INTEGER REFERENCES backtest_results(id) ON DELETE CASCADE,
      trade_number INTEGER NOT NULL,
      timestamp TIMESTAMP NOT NULL,
      action VARCHAR(20) NOT NULL,
      side VARCHAR(10) NOT NULL,
      price DECIMAL(20,8) NOT NULL,
      quantity DECIMAL(20,8) NOT NULL,
      position_size DECIMAL(20,8),
      balance DECIMAL(20,8),
      pnl DECIMAL(20,8),
      margin_level DECIMAL(10,4)
  );

  -- Indexes
  CREATE INDEX IF NOT EXISTS idx_backtest_configs_active ON backtest_configs(is_active);
  CREATE INDEX IF NOT EXISTS idx_backtest_results_symbol ON backtest_results(symbol);
  CREATE INDEX IF NOT EXISTS idx_backtest_results_executed_at ON backtest_results(executed_at DESC);
  CREATE INDEX IF NOT EXISTS idx_backtest_results_status ON backtest_results(status);
  CREATE INDEX IF NOT EXISTS idx_backtest_trades_result_id ON backtest_trades(backtest_result_id);

  -- Insert default symbols to test weekly (idempotent)
  INSERT INTO backtest_configs (symbol, side, leverage, interval, category) VALUES
      ('BTCUSDT', 'Long', 10, 1, 'major'),
      ('ETHUSDT', 'Long', 10, 1, 'major'),
      ('SOLUSDT', 'Long', 10, 1, 'major'),
      ('BNBUSDT', 'Long', 10, 1, 'major'),
      ('ADAUSDT', 'Long', 10, 1, 'altcoin'),
      ('DOGEUSDT', 'Long', 10, 1, 'altcoin'),
      ('AVAXUSDT', 'Long', 10, 1, 'altcoin'),
      ('MATICUSDT', 'Long', 10, 1, 'altcoin'),
      ('u1000PEPEUSDT', 'Long', 10, 1, 'meme'),
      ('SHIBUSDT', 'Long', 10, 1, 'meme')
  ON CONFLICT (symbol) DO NOTHING;
  ```

**Weekly Backtest Execution**
- [x] Create `saas/run_weekly_backtests.py`
  - Fetch all active symbols from `backtest_configs`
  - Run backtest for each symbol (7-day period, $200 balance)
  - Store results in `backtest_results` and `backtest_trades`
  - Handle errors gracefully (store error message)
  - Logging for monitoring

- [x] Modify `backtest/backtest.py` to return structured results
  - Return dict with all metrics (instead of just printing)
  - Include trade list for storage
  - Execution time tracking

- [x] Schedule weekly execution
  - Option A: New cron job in `render.yaml` (Sunday 2 AM UTC) ✅

**Front Page Display**
- [x] Update `saas/templates/index.html`
  - Hero section with tagline
  - "Weekly Backtest Results" section
  - Performance grid (cards for each symbol)
  - Each card shows:
    - Symbol + leverage badge
    - P&L % (large, color-coded)
    - P&L amount in USD
    - Win rate, max drawdown, trade count
    - Test date range
  - Disclaimer about past performance
  - Call-to-action (Register button)

- [x] Update `saas/static/css/style.css`
  - Performance card styling (dark theme)
  - Gradient borders and hover effects
  - Color coding (green=profit, red=loss)
  - Responsive grid layout
  - Trading platform aesthetic (match existing design)

**API Endpoints**
- [x] `GET /api/backtests/latest`
  - Returns most recent backtest for each symbol
  - Sorted by profit_loss_pct DESC
  - Used by front page

- [x] `GET /api/backtests/<symbol>/history`
  - Returns last 12 weeks of results for a symbol
  - For historical trend charts (future enhancement)

- [x] Update `GET /` (index route)
  - Fetch latest backtest results
  - Pass to template for rendering
  - Handle errors gracefully (empty state)

**Admin Interface**
- [ ] `GET/POST /admin/backtests`
  - List all configured symbols
  - Add/remove symbols
  - Enable/disable symbols for testing
  - View last execution time and status

**Monitoring & Alerts**
- [x] Log backtest execution to console
- [x] Track execution time
- [ ] Alert on failures (optional Telegram notification) - Future enhancement

**Testing Strategy**
- [x] Test migration locally: `python saas/migrate.py`
- [x] Verify default symbols inserted into `backtest_configs`
- [x] Test backtest runner with 2-3 symbols
- [x] Verify results stored correctly in `backtest_results` and `backtest_trades`
- [x] Test front page rendering with real data (verified with Chrome DevTools MCP)
- [x] Test error handling (invalid symbol, API failure)
- [x] Test API endpoints return correct data

**Estimated Timeline**
- Database migration (004): 1 hour
- Backtest runner script: 3-4 hours
- Modify backtest.py: 1-2 hours
- Front page UI: 3 hours
- API endpoints: 2 hours
- Testing & refinement: 2 hours
- **Total: 12-14 hours**

---

### 2B. User-Initiated Backtests (Future)

**Backtest Configuration UI**
- [ ] Web form to configure backtest parameters
  - Symbol selection
  - Time period (days/date range)
  - Starting balance
  - Side (Long/Short/Both)
  - Leverage selection
  - Strategy parameters override
- [ ] Saved backtest configurations per user
- [ ] Quick-test with recommended parameters

**Backtest Execution**
- [ ] Backend API endpoint to run backtests
- [ ] Queue system for backtest jobs
- [ ] Progress tracking for long-running backtests
- [ ] Email/notification on completion
- [ ] Concurrent backtest limit per user

**Results Visualization**
- [ ] Interactive charts using Chart.js/D3.js
  - Balance history over time
  - Position size evolution
  - PnL tracking
  - Drawdown visualization
  - Margin level monitoring
- [ ] Statistical summary dashboard
  - Total return %
  - Max drawdown
  - Sharpe ratio
  - Win rate
  - Average trade duration
  - Number of trades

**Historical Data Management**
- [ ] Cache historical data for faster backtests
- [ ] Data source selection (Binance/Phemex)
- [ ] Data quality validation
- [ ] Historical data refresh mechanism

**Backtest History**
- [ ] Store past backtest results per user
- [ ] Compare multiple backtest runs
- [ ] Export results (CSV/JSON/PDF)
- [ ] Share backtest results (optional)

**Strategy Optimization**
- [ ] Parameter sweep interface
- [ ] Grid search for optimal parameters
- [ ] Heatmap visualization of results
- [ ] Recommended parameter sets

**UI/UX Improvements**
- [ ] Backtest wizard (step-by-step configuration)
- [ ] Template library (common backtest scenarios)
- [ ] One-click backtest from bot configuration
- [ ] Compare backtest vs live performance

---

## Phase 3: Advanced Analytics & Monitoring

**Real-Time Performance**
- [ ] Live P&L tracking
- [ ] Position alerts and notifications
- [ ] Risk metrics dashboard
- [ ] Portfolio overview (all bots combined)

**Advanced Charting**
- [ ] TradingView-style charts
- [ ] Custom indicator overlays
- [ ] Strategy signal visualization
- [ ] Entry/exit markers on charts

**Reporting**
- [ ] Daily/weekly/monthly reports
- [ ] Tax reporting (trades export)
- [ ] Performance attribution
- [ ] Custom report builder

**Notifications & Alerts**
- [ ] Email notifications
- [ ] Webhook integrations
- [ ] SMS alerts (Twilio)
- [ ] Discord/Slack integration
- [ ] Custom alert rules

---

## Phase 4: Strategy Enhancement

**Multiple Strategy Support**
- [ ] Strategy marketplace/library
- [ ] Custom strategy builder (visual)
- [ ] A/B testing different strategies
- [ ] Strategy versioning

**Risk Management Tools**
- [ ] Portfolio-level risk limits
- [ ] Automatic circuit breakers
- [ ] Correlation analysis
- [ ] Position sizing calculator

**Advanced Features**
- [ ] Grid trading strategy
- [ ] Mean reversion strategy
- [ ] Trend following strategy
- [ ] Arbitrage detection

---

## Phase 5: Platform Scaling

**Performance Optimization**
- [ ] Redis caching layer
- [ ] WebSocket real-time updates
- [ ] Background job queue (Celery)
- [ ] Database query optimization

**Multi-Exchange Support**
- [ ] Binance integration
- [ ] Bybit integration
- [ ] OKX integration
- [ ] Unified exchange interface

**Enterprise Features**
- [ ] Team/organization accounts
- [ ] Role-based access control
- [ ] API access for developers
- [ ] White-label deployment option

**Billing & Subscriptions**
- [ ] Stripe payment integration
- [ ] Tiered pricing plans
- [ ] Usage-based billing
- [ ] Free trial period

---

## Phase 6: Mobile & API

**Mobile Application**
- [ ] React Native mobile app
- [ ] Push notifications
- [ ] Mobile-optimized charts
- [ ] Quick actions & widgets

**Developer API**
- [ ] RESTful API
- [ ] WebSocket API
- [ ] API documentation (OpenAPI/Swagger)
- [ ] Rate limiting
- [ ] API key management

**Third-Party Integrations**
- [ ] TradingView alerts
- [ ] Portfolio trackers (CoinTracking, etc.)
- [ ] Tax software integration
- [ ] Analytics platforms

---

## Technical Debt & Maintenance

**Code Quality**
- [ ] Comprehensive unit tests (>80% coverage)
- [ ] Integration tests for critical paths
- [ ] End-to-end testing (Playwright)
- [ ] Code documentation (Sphinx)

**Infrastructure**
- [ ] Kubernetes deployment option
- [ ] Monitoring & logging (Datadog/Sentry)
- [ ] Automated backups
- [ ] Disaster recovery plan

**Security**
- [ ] Security audit
- [ ] Penetration testing
- [ ] GDPR compliance
- [ ] SOC2 certification

---

## Ideas for Future Consideration

- Copy trading (follow successful traders)
- Social features (leaderboards, sharing results)
- ML/AI-powered parameter optimization
- Sentiment analysis integration
- News-based trading triggers
- Automated portfolio rebalancing
- Paper trading mode with real market data
- Strategy backtesting against specific market events
- Multi-timeframe analysis
- Custom indicator development framework

---

## Success Metrics

**User Growth**
- Monthly active users
- User retention rate
- Average bots per user
- Trading volume

**Platform Performance**
- Uptime (target: 99.9%)
- Average response time
- Database query performance
- Backtest completion time

**Financial Metrics**
- Monthly recurring revenue
- Customer acquisition cost
- Lifetime value
- Churn rate

**Product Quality**
- Bug report rate
- User satisfaction (NPS)
- Feature adoption rate
- Support ticket volume

---

## Contributing

Have ideas for new features? Open a GitHub issue or submit a pull request!

For major changes, please discuss in an issue first to coordinate development efforts.

---

**Last Updated**: November 2025
**Next Review**: December 2025
