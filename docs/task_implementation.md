# TFT Trader — Task Implementation & Weekly Roadmap (Polished)

Version: 1.4
Last updated: 2026-02-15T18:30:00Z
Author: TFT Trader Development Team

**🎯 IMMEDIATE ACTION ITEMS (Priority Order)**
======================================================

### **RIGHT NOW - DO THIS NEXT** 🔥
```
Week 2 — Task #5: Docker Compose Dev Setup (1-2 hours)
├─ Create docker/docker-compose.dev.yml (Redis + Postgres + Celery)
├─ Add Celery beat scheduler  
├─ Document: docker-compose up
└─ Verify hourly scraper runs with real data
   Status: READY TO START ✅
   Blocker: None
   Unblocks: Team can use consistent local environment
```

### **JUST COMPLETED** ✅
```
Week 2 — Task #4: Data Validation & Integration Testing (✅ DONE)
├─ ✅ Created /api/v1/posts/scrape/{subreddit} endpoint (105 lines)
├─ ✅ Added deduplication logic (checks post_id before insert)
├─ ✅ Configured rate limiting (5 requests/hour)
├─ ✅ Created 320-line integration test suite
├─ ✅ All 4 critical tests PASSING
└─ ✅ Ready for Task #5 Docker setup
   Status: COMPLETE ✅
   Tests: 4 PASSED, 1 SKIPPED (optional real Reddit test)
   Details: See docs/task4_completion.md
```

### **THEN (Week 3)**
```
Week 3 — Feature Builder + Snapshots (2-3 hours)
├─ Implement backend/ml/features/build.py
├─ Create feature snapshots with snapshot_id
├─ Build 30-day sequence arrays
└─ Add tests for feature pipeline
   Status: BLOCKED (waiting for Task #5)
   Blocker: Task #5 (need hourly scraper running)
   Unblocks: Week 4 (training)
```

---

**📌 CRITICAL DEPENDENCY CHAIN** (Why order matters):
```
Task #4 (Data Validation)                    ✅ COMPLETE
     ↓ (produces real data → DB)
Task #5 (Docker Compose Setup)              ⏳ DO THIS SECOND
     ↓ (enables consistent dev)
Week 3 (Feature Builder)                    ⏳ DO THIS THIRD
     ↓ (creates snapshots → training input)
Week 4 (Baseline Training)                  ⏳ AFTER WEEK 3
     ↓ (trains models)
Week 5 (Tuning)                             ⏳ AFTER WEEK 4
     ↓ (optimizes models)
Week 6 (Inference + Risk Manager)           ⏳ AFTER WEEK 5
     ↓ (daily signal generation)
Week 7-12 (Frontend, Deployment, etc.)      ⏳ AFTER WEEK 6
```

**Why this order?**
- **Task #4 FIRST** — Need real Reddit data in database before anything else
- **Task #5 SECOND** — Then setup dev environment for team consistency
- **Week 3 THIRD** — Only then can we build features from the real data
- **Week 4+** — Only then can we train models on those features

**If you skip Task #4:** Week 3 has no real data to build features from → training fails
**If you skip Task #5:** Each dev has different local setup → hard to debug issues
**Bottom line:** Do them in order → no wasted work!

---

Purpose
-------
Provide a single, actionable source of truth that converts the project roadmap into a week-by-week implementation plan. This file documents: what is currently implemented, what is actively in progress, a point-wise analysis of gaps and risks, detailed weekly tasks (Weeks 2–12), prioritized TODOs, and an immediate 2-week sprint with explicit acceptance criteria and owner suggestions.

Recent Updates
--------------
- ✅ **2026-02-15**: Completed Task #3 — Scraper hardening with retry/backoff framework
  - Added `backend/utils/retry.py` (330+ lines): RetryConfig class, should_retry() function, @retry_with_backoff and @retry_with_backoff_async decorators, RateLimiter class
  - Applied decorators to reddit_scraper.scrape_posts(), reddit_scraper.get_post_comments(), stock_scraper._fetch_sync(), stock_scraper._get_price_sync()
  - Created `tests/integration/test_scraper_retry.py` (24 comprehensive tests, all passing)
  - Automatic retry on 429 rate limits, timeouts, 5xx errors; fail fast on 401/403/404; exponential backoff with jitter
- ✅ **2026-02-15**: Completed Task #2 — Risk Manager implementation
  - Added `backend/services/risk_manager.py` (495 lines) with 6 validation rules: confidence (70%), price levels, risk/reward (1:2), position sizing (20%), portfolio constraints (5 positions, 15% drawdown)
  - Created `tests/unit/test_risk_manager.py` (450 lines with 29 comprehensive tests, all passing in 0.03s)
- ✅ **2026-02-15**: Completed Task #1 — Configuration & Credentials setup
  - Added `.env.example` with 70+ variables and inline documentation
  - Created `docs/credentials.md` with 400+ lines of step-by-step setup guides for Reddit, Neon DB, Redis Cloud, AWS RDS, security keys
  - Created `scripts/setup.sh` for automated environment initialization
- ✅ **Day 1 (Week 2)**: Implemented rate limiting for all Stock API endpoints (11 dependency functions, 14 endpoints with Redis-backed counters)

Current snapshot (what's implemented and ongoing)
-------------------------------------------------
Note: "Evidence" lines point to repository paths that demonstrate implemented code.

1) Configuration & Credentials — **NEW: COMPLETE** ✅
- Status: Implemented
- What exists: .env.example (comprehensive), docs/credentials.md (detailed guides), scripts/setup.sh (automated setup)
- Explanation: Complete developer setup workflow with step-by-step instructions for obtaining all API credentials (Reddit, database, Redis, secrets)
- Evidence: [.env.example](.env.example), [docs/credentials.md](docs/credentials.md), [scripts/setup.sh](scripts/setup.sh)
- Next actions: Developers follow docs/credentials.md to configure their local environment
- Priority: ✅ Complete — unblocks all other work

2) Scrapers: Reddit & Stock
- Status: Hardened with retry/backoff ✅ **COMPLETE**
- What exists: backend/scrapers/reddit_scraper.py, backend/scrapers/stock_scraper.py, backend/utils/retry.py (exponential backoff + decorators)
- Explanation: Both scrapers now have @retry_with_backoff decorators that automatically retry on transient errors (rate limits, timeouts, 5xx) and fail fast on permanent errors (401, 403, 404). Includes exponential backoff with jitter, configurable per API type (Reddit: 2s base → 120s cap, yfinance: 1s base → 30s cap).
- Evidence: [backend/scrapers/reddit_scraper.py](backend/scrapers/reddit_scraper.py) (lines 47, 114 show @retry_with_backoff decorators), [backend/scrapers/stock_scraper.py](backend/scrapers/stock_scraper.py) (lines 33, 151 show decorators), [backend/utils/retry.py](backend/utils/retry.py) (330+ lines with RetryConfig class, should_retry() logic, and decorators)
- Tests: [tests/integration/test_scraper_retry.py](tests/integration/test_scraper_retry.py) (24 tests covering rate limits, timeouts, 404s, error classification, backoff timing)
- Next actions: Apply to other services (news scraper), monitor retry patterns in production logs
- Priority: ✅ Complete — scrapers now production-ready for rate limiting resilience

3) API Rate Limiting — **NEW: COMPLETE** ✅
- Status: Implemented and tested
- What exists: backend/api/middleware/rate_limit.py, backend/config/rate_limits.py, rate limit checks on all Stock endpoints
- Explanation: Redis-backed rate limiting with configurable per-endpoint limits (100-200/min for reads, 2-20/min for writes, 2/day for destructive ops). All 14 stock endpoints protected with inline documentation.
- Evidence: [backend/api/routes/stocks.py](backend/api/routes/stocks.py) (lines 18-258 show all rate limit dependency functions)
- Next actions: Extend to other routes (posts, predictions, auth) if needed
- Priority: ✅ Complete

4) Data Validation & Scraping Integration — **NEW: COMPLETE** ✅
- Status: Complete with full test coverage
- What exists: 
  - Endpoint: POST `/api/v1/posts/scrape/{subreddit}` (105 lines with full error handling)
  - Deduplication: Checks post_id exists before inserting
  - Rate limiting: 5 requests/hour (respects Reddit API quotas)
  - Tests: 320-line integration test suite (4 PASSED, 1 SKIPPED)
- Explanation: Scraping endpoint now accepts manual scraping requests, deduplicates posts using DB queries, and enforces strict rate limiting for expensive external API calls. All tests passing.
- Evidence: [backend/api/routes/posts.py](backend/api/routes/posts.py) (lines 165-287), [backend/config/rate_limits.py](backend/config/rate_limits.py) (line 246-251), [tests/integration/test_scraping_integration.py](tests/integration/test_scraping_integration.py) (320 lines)
- Test Results: 4 PASSED, 1 SKIPPED (optional real Reddit integration)
- Next actions: Task #5 - Docker Compose setup for automated hourly scraping
- Priority: ✅ Complete — ready for Task #5

5) Task orchestration (Celery + Scheduler)
- Status: Present but needs verification in dev/staging
- What exists: backend/celery_app.py, backend/tasks/scraping_tasks.py, scripts/scheduled_scraper.py
- Explanation: Celery app is configured; scraping tasks are defined and a standalone scheduled script exists for local execution.
- Blockers: Celery workers and beat not validated in CI; Redis connection and recommended concurrency not documented.
- Next actions: Add docker-compose dev setup for Redis + worker, add healthcheck endpoints and a simple CI check that starts a worker and runs a sample task.
- Priority: High — Task #5 will address this.

6) Database & Migrations
- Status: Implemented
- What exists: alembic/versions/*, backend/models/* (stock, reddit, trading_signal)
- Explanation: Database schema for reddit_posts, stock_prices and trading_signals defined and migrations present.
- Blockers: None major; ensure migration workflow documented (.env, DB URL)
- Next actions: Add sample seed data scripts for dev.
- Priority: Medium.

7) Feature engineering
- Status: Partially implemented
- What exists: backend/utils/indicators.py, components in backend/ml/* that assume prepared features
- Explanation: Indicator utilities exist but a formal, versioned feature builder pipeline (persisting features with metadata) is not yet in place.
- Blockers: No canonical features table or parquet snapshot that training scripts can rely on.
- Next actions: Implement backend/ml/features/ builder that writes to DB or parquet and records a snapshot id.
- Priority: High for ML reproducibility.

7) ML models & training
- Status: Implemented (models present) but training infra needs reproducibility improvements
- What exists: backend/ml/models/{xgboost_model.py, lightgbm_model.py, tft_model.py, ensemble.py}, backend/ml/training/train_ensemble.py
- Explanation: Core model code and training scripts exist (including a TFT sequence model); however experiment tracking (MLflow) and consistent dataset snapshots are missing.
- Blockers: No model registry, drift detection, or tuning automation configured.
- Next actions: Integrate MLflow (or equivalent), persist artifacts with metadata, add basic hyperparameter search job.
- Priority: High.

6) Inference & Risk manager
- Status: Partially implemented (inference pieces exist; risk manager missing)
- What exists: backend/ml/inference/predictor.py, backend/services/ml_service.py; risk manager file NOT present
- Explanation: Prediction logic exists but risk validation rules described in ARCHITECTURE.md are not implemented in a single service file for signal gating.
- Blockers: Missing backend/services/risk_manager.py prevents safe automated signal persistence/execution.
- Next actions: Implement risk_manager skeleton and unit tests for rules (confidence, position sizing, max concurrent positions).
- Priority: Critical before any automated execution path.

7) Frontend
- Status: Starter code present, UI milestone not complete
- What exists: frontend/ directory and backend/api/routes/{stocks.py,predictions.py,posts.py}
- Explanation: The backend exposes routes but frontend pages and integration need to be verified and built (dashboard, ticker detail, auth).
- Blockers: No confirmed build + test of the Next.js app in repo CI; TradingView chart integration to be completed.
- Next actions: Wire API endpoints, implement login, dashboard and ticker pages, and add E2E tests.
- Priority: Medium.

8) CI/CD, Monitoring & Deployment
- Status: Partial
- What exists: Dockerfile, docker-compose.yml, Makefile
- Explanation: Containerization and local compose exist; GitHub Actions and production monitoring (Sentry, Prometheus) are not configured.
- Blockers: No CI pipelines or staging deployment runs recorded.
- Next actions: Add GitHub Actions that run tests, lint and build images; add Sentry test instrumentation and /metrics endpoint for Prometheus.
- Priority: High for production readiness.

9) Tests & QA
- Status: Partial
- What exists: tests/test_scraper.py, tests/test_celery.py
- Explanation: Some unit tests present; integration and E2E tests missing.
- Blockers: Missing test coverage for feature builder, risk_manager, and inference pipeline.
- Next actions: Expand tests and add CI jobs to run them.
- Priority: High.

Weekly implementation plan (concise & actionable)
-------------------------------------------------
For each week below: Goal • Why • 3–6 tasks • Deliverables • Acceptance criteria • Owner (recommended)

Week 2 (now) — Real Data integration
- Goal: Make scrapers production-ready and schedule hourly ingestion.
- Why: Foundation for all downstream features and models.

**📊 Week 2 Progress: 3 of 5 tasks COMPLETE (60%)**

**✅ COMPLETED (No more work needed)**:
  1. ✅ **Task #1**: .env.example + credentials docs
     - Status: DONE — All developers can setup in < 5 minutes
     - Evidence: [.env.example](.env.example), [docs/credentials.md](docs/credentials.md), [scripts/setup.sh](scripts/setup.sh)
     - Time spent: ~15 minutes
  
  2. ✅ **Task #2**: Risk Manager with 6 validation rules
     - Status: DONE — 29/29 tests passing
     - Evidence: [backend/services/risk_manager.py](backend/services/risk_manager.py) (495 lines)
     - Time spent: ~90 minutes
     - Test file: [tests/unit/test_risk_manager.py](tests/unit/test_risk_manager.py) (29 passing tests in 0.03s)
  
  3. ✅ **Task #3**: Scraper hardening with retry/backoff
     - Status: DONE — 24/24 integration tests passing
     - Evidence: [backend/utils/retry.py](backend/utils/retry.py) (341 lines)
     - Applied to: reddit_scraper.py (lines 47, 114), stock_scraper.py (lines 33, 151)
     - Time spent: ~120 minutes
     - Test file: [tests/integration/test_scraper_retry.py](tests/integration/test_scraper_retry.py) (24 passing tests in 1.25s)

---

**⏳ TODO THIS WEEK (High Priority)**:
  
  4. **Task #4 - Data Validation & Integration Testing** (NEXT TO DO)
     - What: Create /api/posts/scrape endpoint, test real Reddit data, add deduplication
     - Files to create/update:
       - `backend/api/routes/posts.py` — Add POST /scrape/{subreddit} endpoint
       - `backend/services/reddit_service.py` — Add deduplication logic (check post_id exists)
       - `tests/integration/test_scraping_integration.py` — Test end-to-end pipeline
     - Time estimate: 1-2 hours
     - Acceptance criteria:
       - Endpoint POST /api/posts/scrape/wallstreetbets returns {subreddit, fetched, saved, skipped}
       - No duplicate posts inserted to database
       - SQL query confirms real Reddit posts in DB
     - Dependencies: ✅ All ready (scrapers, retry logic complete)
     - Blocks: Task #5, Week 3
  
  5. **Task #5 - Docker Compose Dev Setup** (AFTER Task #4)
     - What: Create docker/docker-compose.dev.yml with Redis, Postgres, Celery worker + beat
     - Files to create/update:
       - `docker/docker-compose.dev.yml` — New file with all services
       - `backend/tasks/scraping_tasks.py` — Update with real subreddit list
       - `docs/DEVELOPMENT.md` — How to start dev environment
     - Time estimate: 1-2 hours
     - Acceptance criteria:
       - `docker-compose -f docker/docker-compose.dev.yml up` starts all services
       - Celery worker visible and running
       - Beat scheduler triggers scraper task hourly
       - Logs show successful data ingestion
     - Dependencies: Task #4 (data validation working first)
     - Unblocks: Team can work with real local environment

---

**📈 Summary of Week 2**:
- Completed: 3 of 5 tasks (60%)
- Tests passing: 53/53 (29 Risk Manager + 24 Scraper Retry)
- Lines of code: 895+ (Risk Manager + Retry framework + tests)
- Ready for: Week 3 (Feature Builder) after Task #4

Week 3 — Feature builder + snapshots
- Goal: Produce a reproducible features dataset and a sequence builder for ML input.
- Why: Feature snapshots are required input for all ML training (Week 4+).
- Status: NOT STARTED (blocked until Task #4 complete with real data)
- Tasks:
  1. Implement backend/ml/features/build.py
     - Input: Real Reddit posts + stock prices from Task #4
     - Output: Features snapshot table with snapshot_id
     - Metrics: RSI, MACD, Bollinger Bands, sentiment score, ticker counts, volume ratio
  2. Implement 30-day sequence builder
     - Create sliding windows of 30 days of features
     - Output: Array of shape (n_sequences, 30, n_features)
     - For use by tree models (XGBoost, LightGBM) and TFT (Temporal Fusion Transformer)
  3. Add unit + integration tests
     - Test feature snapshot creation
     - Test sequence array shapes
     - Test historical data edge cases (missing data, gaps)
- Deliverables: Features snapshot, sequence arrays, tests
- Acceptance: 
  - ✅ Feature snapshot created with shape verified
  - ✅ Sequence arrays output correct dimensions
  - ✅ All tests passing (unit + integration)
- Dependencies: Task #4 (real data in database)
- Unblocks: Week 4 (baseline training)
- Owner: ML Lead
- Time estimate: 2-3 hours

Week 4 — Baseline training, logging, and backtest
- Goal: Train baseline models, log runs, and run backtests.
- Why: Establish baseline performance before tuning (Week 5).
- Status: NOT STARTED (blocked until Week 3 complete with feature snapshots)
- Tasks:
  1. Integrate MLflow for experiment tracking
     - Log all training runs with hyperparameters
     - Save model artifacts
     - Track metrics (accuracy, precision, recall, F1)
  2. Run baseline training
     - XGBoost model training
     - LightGBM model training  
     - TFT (Temporal Fusion Transformer) training
  3. Add backtest script
     - Use trained models to generate signals
     - Calculate P&L, win rate, drawdown
     - Compare against buy-and-hold baseline
- Deliverables: MLflow runs + artifacts, backtest report
- Acceptance:
  - ✅ All 3 models trained and logged in MLflow
  - ✅ Backtest shows model performance vs baseline
  - ✅ No lookahead bias in backtest
- Dependencies: Week 3 (feature snapshots ready)
- Unblocks: Week 5 (tuning)
- Owner: ML Lead
- Time estimate: 2-3 hours

Week 5 — Tuning & ensemble validation
- Goal: Improve model robustness with automated tuning and validate ensemble weights.
- Tasks:
  1. Add Optuna tuning jobs for tree models; run at small scale.
  2. Add walk-forward validation script to avoid lookahead bias.
  3. Validate and store ensemble weights and calibration parameters.
- Deliverables: best hyperparams; validated ensemble.
- Owner: ML Lead

Week 6 — Inference + Risk Manager + scheduled signals
- Goal: Safely create daily signals and persist them after risk checks.
- Tasks:
  1. Implement /api/predict endpoint and a Celery daily job to call it and persist signals.
  2. Implement backend/services/risk_manager.py with unit tests for rules (confidence, position sizing, max positions).
  3. Add a webhook/log notification for candidate signals.
- Deliverables: endpoint + scheduled job + risk_manager tests.
- Acceptance: Scheduled job writes trading_signals only for signals that pass risk checks.
- Owner: Backend + ML

Week 7–8 — Frontend baseline & watchlist
- Goal: Basic dashboard, ticker pages and watchlist.
- Tasks:
  1. Implement Dashboard, Ticker detail, Auth pages; wire to backend routes.
  2. Implement watchlist CRUD API and client UI.
  3. Add TradingView / Recharts for charting and sentiment timeline.
- Deliverables: working UI with auth and watchlist.
- Acceptance: User can login, add watchlist, view live/updating ticker details.
- Owner: Frontend Lead

Week 9–10 — Real-time, polishing, QA
- Goal: Add WebSockets, polish UI and finalize tests.
- Tasks:
  1. Implement WebSocket price feed and client subscriptions.
  2. Add sentiment feed and Reddit posts timeline on ticker page.
  3. Add E2E tests and accessibility checks.
- Deliverables: Real-time dashboard and test suite.
- Acceptance: Dashboard updates within <5s in simulated environment; E2E flows pass.
- Owner: Frontend + QA

Week 11 — CI/CD & Observability
- Goal: Build CI pipelines and add basic observability.
- Tasks:
  1. Add GitHub Actions for tests, lint, build and optional image push.
  2. Integrate Sentry SDK and a /metrics endpoint for Prometheus.
  3. Add deployment smoke-tests.
- Deliverables: CI runs on PRs; Sentry test event visible.
- Acceptance: CI passes on PR; Sentry receives test event.
- Owner: DevOps

Week 12 — Production deployment & smoke-tests
- Goal: Deploy to staging/production, run smoke tests and finalize runbooks.
- Tasks:
  1. Provision Neon Postgres, managed Redis, Vercel frontend; deploy containers to Render/Railway.
  2. Run smoke tests and small load tests; document rollback and retraining runbooks.
- Deliverables: Live staging/production, runbook, smoke-test report.
- Acceptance: Live app reachable; smoke tests pass; monitoring alerts configured.
- Owner: DevOps + Team Leads

Global prioritized TODOs (by priority)
-------------------------------------
Critical
- Add .env.example and secure secrets documentation.
- Implement backend/services/risk_manager.py and unit tests.
- Verify scrapers with real API credentials and add retry/backoff.
High
- Implement feature builder and snapshotting.
- Integrate MLflow and persist artifacts with metadata.
- Create a scheduled inference job that writes signals to DB.
Medium
- Implement frontend dashboard and watchlist.
- Add GitHub Actions for CI.
Low
- Broker integration (Alpaca/IB) — future work and gated by risk manager and regulatory considerations.

Immediate 2-week sprint (actionable checklist)
---------------------------------------------
Sprint goal: Reach a reproducible pipeline end-to-end: Scraper -> Feature snapshot -> Train -> Inference -> Risked signal persist (on staging data).

Tasks (owner: Backend + ML):
- [x] Add .env.example and docs/credentials.md (Backend) — COMPLETED ✅
- [x] Implement risk_manager skeleton and tests (Backend) — COMPLETED ✅ (29/29 tests passing)
- [ ] Add unit tests for reddit_scraper and stock_scraper (Backend) — cmd: pytest tests/test_scraper.py
- [ ] Implement feature builder that outputs a features snapshot (ML) — cmd: python -m backend.ml.training.build_features --sample AAPL
- [ ] Wire a daily scheduled inference Celery task writing to trading_signals (Backend+ML)

Sprint acceptance criteria
- All test cases for scrapers and risk_manager pass locally (pytest)
- Feature snapshot produced and used by training script to create an artifact
- Daily inference job runs locally and writes at least one risk-validated signal to DB (staging)

Recommended quick commands
--------------------------
- DB migrations: alembic upgrade head
- Start local infra: docker-compose up -d redis postgres
- Start Celery worker & beat:
  - celery -A backend.celery_app worker --loglevel=info
  - celery -A backend.celery_app beat --loglevel=info
- Run scraper manually: python scripts/scheduled_scraper.py
- Run training (dev): python backend/ml/training/train_ensemble.py --config configs/train.yaml
- Run tests: pytest -q

Notes & recommendations (technical choices)
-------------------------------------------
- Sequence model: repository includes tft_model.py (Temporal Fusion Transformer). If TFT is stable and documented, prefer it over hand-rolled LSTM — TFT often generalizes better for multivariate time-series. If LSTM is preferred for simplicity, implement a compact LSTM training script and keep TFT as advanced option.
- Experiment tracking: MLflow is recommended (lightweight and well-supported). Use local MLflow for dev, push to remote tracking server for production.
- Monitoring & drift: Track simple metrics (daily accuracy, prediction distribution shifts, feature nulls) and add alerting thresholds before automated retraining.

How to keep this document current
---------------------------------
- Update status lines (Completed / In Progress / Blocked) and add evidence (file paths, PR links) after every sprint.
- For major changes add a changelog header with date and short summary.

Appendix — Quick evidence pointers
----------------------------------
- Scrapers & utils: backend/scrapers/* and backend/utils/*
- Celery & tasks: backend/celery_app.py and backend/tasks/*
- ML models & training: backend/ml/models/* and backend/ml/training/*
- API routes: backend/api/routes/*
- DevOps: Dockerfile, docker-compose.yml, Makefile

End of document — use this as the sprint source of truth; update with brief evidence notes after completing each task.
