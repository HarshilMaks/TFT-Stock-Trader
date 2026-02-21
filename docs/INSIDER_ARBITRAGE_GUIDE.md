# INSIDER / INFORMATION-ARBITRAGE GUIDE

Last updated: 2026-02-20
Author: TFT Trader — Generated summary

---

## Executive summary

Goal: steer TFT Trader from a Reddit+momentum swing trading platform toward a high-alpha "legal insider trading" (information arbitrage) system by adding high-signal data layers, real-time flow analytics, disciplined evaluation, and robust MLOps.

Short verdict: the current codebase and docs show a very strong foundation (scrapers, 23-d feature engine, Celery orchestration, risk manager, TFT/LSTM training), so the project is on the right track for swing trading. However, to materially raise prediction accuracy and approach "insider-level" information arbitrage you must add at least two high-alpha data layers (Insider filings + Institutional/Options flow), real-time tick ingestion & analysis, and strict evaluation (walk-forward CV/backtests, lookahead prevention). TFT/LSTM models help capture temporal patterns and will likely improve performance over naive baselines, but deep models alone cannot replace missing high-alpha signals.

---

## Where the repo already excels

- Production-grade scrapers with retry/backoff and deduplication
- Feature engineering: 23-dimensional temporal features and a 30-day sequence builder
- Orchestration: Celery tasks + scheduled scrapers and ML tasks
- Risk manager: validated rules (position sizing, stop loss, drawdown limits)
- ML infra: TFT/LSTM/XGBoost/LightGBM code and MLflow logging hooks (partial)
- Tests: comprehensive unit/integration tests for feature builder and scrapers

---

## What’s missing (the critical gaps / faults)

1. Missing high-alpha data:
   - No SEC Form-4 / insider trades ingestion
   - No options / unusual-flow ingestion
   - No dark-pool or institutional flow signals (order-book / tick-level analysis)
2. No real-time tick ingestion pipeline (Redis Pub/Sub + TimescaleDB) for unusual volume detection and options flow correlation
3. ML lifecycle gaps:
   - Model registry, automated retraining, and drift detection are not wired
   - Experiment comparators and ablation harnesses are present but not fully automated
4. Labeling & evaluation risks:
   - Potential lookahead/leakage if feature snapshots are not strictly time-gated
   - Lack of walk-forward cross-validation and realistic backtesting (slippage/fees)
5. No broker/execution connector (Alpaca/IB) and no enforced execution-layer safety for stop-loss/position sizing
6. Frontend real-time socket integration and execution UI incomplete
7. Potential operational gaps: monitoring/metrics (Prometheus), Sentry alerts, CI/CD pipelines

---

## Strategy to become an "Information Arbitrage" platform

Principle: Only trade when multiple independent sources (insider, institutional flow, social hype) align — the "Triangulation Method". This loses many opportunities but improves hit-rate and average trade quality.

Layers (must-have):

- Layer 1 — Insider (Legal): SEC Form‑4, congressional disclosures
- Layer 2 — Institutional Flow: unusual/option flows, dark‑pool volume, order book anomalies
- Layer 3 — Hype / Retail: Reddit/social sentiment (existing)

Regime gate: disable buys in bearish regimes (e.g., SPY < SMA200) — reduces false positives.

Scoring (example):
- Insider_Score: CEO/CFO/Director buy => +30
- Flow_Score: Volume > 200% avg OR heavy call OI => +20
- Sentiment_Score: Reddit spike + positive sentiment => +20
- Technical_Score: RSI oversold / MACD confirmation => +30
- Execution trigger: BUY when total > 80

---

## Architecture changes (high-level)

Add event-driven streaming and new strategy modules:

backend/
  ├─ strategy/
  │   ├─ insider_tracker.py      # SEC Form‑4 ingestion and normalization
  │   ├─ dark_pool.py            # Volume / OI anomaly detectors
  │   └─ regime_filter.py        # SPY 200-day MA gate
  ├─ streams/
  │   ├─ socket_listener.py     # Connect to real-time data (Alpaca/Polygon)
  │   └─ redis_publisher.py     # Publish raw ticks to Redis
  ├─ analysis/
  │   ├─ feature_store.py       # Align time-series + irregular social events
  │   └─ signal_engine.py       # Regime-weighted voting & signal generation
  ├─ tasks/
  │   └─ insider_tasks.py       # Celery tasks to fetch & persist insider events

Infrastructure:
- Redis (Pub/Sub) for real-time messaging
- TimescaleDB (Postgres extension) for tick & aggregated time-series
- MLflow server + model registry and automated experiment tracking
- Broker connector module for safe execution (Alpaca/IB) with enforced stop-loss

---

## Database additions (suggested schema)

```sql
CREATE TABLE insider_trades (
  id SERIAL PRIMARY KEY,
  ticker VARCHAR(10) NOT NULL,
  insider_name VARCHAR(200),
  insider_title VARCHAR(100),
  transaction_date DATE NOT NULL,
  transaction_type VARCHAR(10), -- 'BUY' or 'SELL'
  transaction_shares BIGINT,
  transaction_amount NUMERIC, -- dollar value if available
  filing_url TEXT,
  reported_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_insider_ticker_date ON insider_trades(ticker, transaction_date);
```

Also add a small table for unusual_options_events and dark_pool_events (similar schema).

---

## Implementation plan (prioritized)

High priority (start here):
1. Insider data layer
   - Create `backend/strategy/insider_tracker.py` (use sec-api or SEC EDGAR feeds)
   - Add Alembic migration for `insider_trades`
   - Add Celery task `backend/tasks/insider_tasks.py` scheduled hourly
   - Join insider signals into feature pipeline (FeatureSnapshot)
2. Local ablation + backtest harness
   - Create experiment comparing baseline vs baseline+insider
   - Use walk-forward CV and MLflow to track results
3. Regime filter
   - Implement `backend/strategy/regime_filter.py` and wire into signal_engine

Medium priority:
4. Options / unusual flow ingestion (use Tradier/Polygon options endpoints or an options flow API)
5. Real-time tick ingestion: Redis Pub/Sub + TimescaleDB (socket_listener → redis_publisher → analyzer)
6. Update signal_engine to Regime‑Weighted Voting with new scoring weights

Lower priority:
7. Broker connector + safe execution with hard stop-loss enforcement
8. Model registry + retraining automation + drift detection
9. Frontend websockets and execution UI
10. Monitoring, CI/CD, and production-grade observability

---

## ML evaluation & experiments

- Use walk‑forward cross‑validation (time-series split that respects time) — never shuffle time.
- Backtest with realistic slippage and commissions; include order fill assumptions.
- Ablation tests: baseline (no insider), +insider, +options, +real-time ticks, +all combined.
- Metrics to track: Win rate, average return per trade, max drawdown, Sharpe ratio, precision/recall on BUY vs not-BUY, calibration (reliability diagrams), statistical significance (bootstrap CI).
- For model comparison: run TFTTrainer vs LSTM vs XGBoost/LightGBM; collect MLflow metrics and compare.

Suggested MLflow experiment flow:
1. Baseline run (existing features)
2. Add insider features run
3. Add options flow run
4. Full-stack run

Compare uplift and only promote models that produce robust out-of-sample improvement.

---

## Coding notes & quick scaffolds

Insider tracker (pseudo):

```python
# backend/strategy/insider_tracker.py
from sec_api import QueryApi
from backend.db import get_session

class InsiderTracker:
    def __init__(self, api_key):
        self.query_api = QueryApi(api_key)

    def fetch_recent_form4(self):
        # query Form 4 filings for buys in the last 7 days
        # normalize ticker, insider name, shares, amount, date
        return filings

    def persist(self, filings, db_session):
        # upsert into insider_trades table
        pass
```

Celery task (pseudo):

```python
# backend/tasks/insider_tasks.py
from backend.celery_app import celery
from backend.strategy.insider_tracker import InsiderTracker

@celery.task
def ingest_insiders():
    tracker = InsiderTracker(api_key=...)
    filings = tracker.fetch_recent_form4()
    tracker.persist(filings, db_session)
```

---

## Common pitfalls & how to avoid them

- Lookahead bias: always build features from data strictly prior to the prediction timestamp and store feature snapshots.
- Data leakage: do not use future aggregated volume or sentiment that would not be known at inference time.
- Overfitting: use walk-forward CV and restrict hyperparameter tuning to a separate validation window.
- False confidence: calibrate model probabilities and force risk manager rules to avoid large, concentrated bets.
- Legal risk: only use *publicly available* filings (Form 4 etc.). Maintain audit trails and access logs.

---

## Next immediate actionable items (what I recommend we do next)

1. Confirm: create insider_tracker scaffold + Alembic migration + Celery task to ingest Form‑4 filings.
2. Run an ablation experiment (MLflow): baseline vs baseline+insider using existing TFTTrainer and FeatureSnapshot data.
3. If insider features provide uplift, implement options flow ingestion next.

If confirmed, a follow-up commit will scaffold the insider tracker, add the DB model/migration, and add a Celery ingestion task and a short test to validate ingestion.

---

## Legal & ethical note

This guide proposes using only publicly available filings and APIs; *illegal insider trading must not be attempted*. Keep logs, API provenance, and adhere to all applicable laws.

---

If this layout looks right, reply "Yes — scaffold insider layer" and the next commit will add the initial code and migration.

---

## Detailed Phase-by-Phase TODO Checklist

Below is a concrete, actionable checklist broken down by phase. Use these as development tasks, track them in your project board, and mark off as they are completed.

### Phase 0 — Foundation & Dev Environment (P0)
- [ ] Verify docker/docker-compose.dev.yml starts all services (FastAPI, Celery workers, Beat, Flower, Redis, Neon DB) and document startup steps in docs/DEVELOPMENT.md.
- [ ] Add / confirm `.env.example` values and provide a developer `.env.local` template (no secrets) and `scripts/setup.sh` for onboarding.
- [ ] Add Makefile targets: `make dev`, `make test`, `make lint`, `make build`.
- [ ] Ensure container healthchecks, resource limits, and restart policies are configured and validated in CI smoke tests.
- [ ] Create seed data scripts for reddit_posts and stock_prices to enable local development and tests.

### Phase 1 — Data Quality & Ingestion (P1)
- [ ] Implement `insider_trades` DB schema and create an Alembic migration script.
- [ ] Implement `backend/strategy/insider_tracker.py` with secure configuration and robust parsing (primary: sec-api, fallback: EDGAR scraping/parsing).
- [ ] Create Celery task `backend/tasks/insider_tasks.py` (scheduled hourly) to fetch/persist Form‑4 filings and write idempotent upserts.
- [ ] Add unit tests: parsing Form‑4 edge cases, ticker normalization, duplicate handling; add integration test for DB persistence.
- [ ] Implement `unusual_options_events` and `dark_pool_events` schemas plus basic ingestion tasks (batch/stream) as placeholders.
- [ ] Build normalization utilities: ticker mapping, company name resolution, insider role canonicalization, and timezone normalization.

### Phase 2 — Real-time Streams & Aggregation (P1/P2)
- [ ] Implement `backend/streams/socket_listener.py` to connect to streaming providers (Alpaca/Polygon) with pluggable adapters.
- [ ] Implement `backend/streams/redis_publisher.py` that publishes raw trade events to Redis channel(s) (`live_trades`, `options_flow`).
- [ ] Provision TimescaleDB usage plan and create `ticks` hypertable with retention/compression policies; write Alembic SQL migration for Timescale hypertable if using managed Postgres.
- [ ] Implement `backend/streams/analyzer.py` subscriber to Redis that: aggregates 1-minute candles, writes to TimescaleDB, computes rolling volume ratios, and emits `unusual_volume` events to Redis.
- [ ] Add integration tests: simulate socket → Redis → analyzer → Timescale write and confirm aggregated results.

### Phase 3 — Feature Store, Snapshots & Alignment (P2)
- [ ] Implement `backend/analysis/feature_store.py` to join and align: stock_prices (regular) + reddit_posts + insider_trades + options/dark_pool events into fixed-time windows and create FeatureSnapshots.
- [ ] Ensure FeatureSnapshot persistence with unique snapshot_id and timestamp; add retrieval API for reproducible training/inference.
- [ ] Implement strict time-gating and lookahead prevention logic in feature_store (unit tests to assert no future leakage).
- [ ] Add tests validating sequence shapes and missing-value handling for the 30-day SequenceBuilder.

### Phase 4 — ML Training, Experiments & MLOps (P2/P3)
- [ ] Deploy MLflow Tracking Server and Model Registry (local + production configuration); add docs/MLFLOW_SETUP.md with run instructions.
- [ ] Update training scripts (TFTTrainer, EnsembleTrainer) to register models to MLflow Model Registry and to save artifacts (feature snapshot id, preprocessing scaler, model weights).
- [ ] Implement ablation harness that can toggle feature groups (baseline / +insider / +options / +ticks) and run automated comparisons logged to MLflow.
- [ ] Implement walk‑forward cross‑validation pipeline and backtesting harness that respects time ordering and models slippage & backend execution assumptions.
- [ ] Add hyperparameter search (Optuna or randomized grid) that logs trials to MLflow and selects candidate models for registry promotion.
- [ ] Implement model evaluation and calibration steps (reliability diagrams, Platt scaling or isotonic) and add automated validation gates before promoting to production.
- [ ] Add unit & integration tests for training reproducibility: fixed seeds, deterministic data snapshots, and deterministic model saving.

### Phase 5 — Signal Engine & Risk Manager Integration (P3)
- [ ] Implement `backend/analysis/signal_engine.py` with Regime‑Weighted Voting logic, score composition (insider/flow/sentiment/technical), and scoring configuration file.
- [ ] Implement `backend/strategy/regime_filter.py` to compute market regime (SPY SMA200) and publish gate decisions.
- [ ] Integrate risk_manager validation into signal generation flow; require risk approval before any signal becomes actionable (includes: position size calculation, stop-loss/target, portfolio constraints).
- [ ] Add tests covering signal generation permutations and risk edge cases (max positions, drawdown threshold, confidence lower-than-min).

### Phase 6 — Execution & Broker Integration (P4)
- [ ] Create execution abstraction `backend/execution/broker.py` with `place_order`, `cancel_order`, `get_order_status` methods.
- [ ] Implement concrete adapter `backend/execution/adapters/alpaca_adapter.py` and a mock adapter for local testing.
- [ ] Implement `backend/execution/order_manager.py` to handle retries, idempotency, order confirmation, and enforce hard stop-losses and position limits.
- [ ] Create E2E tests with mock broker that exercise order placement, partial fills, cancellations, and stop-loss enforcement.
- [ ] Add safety features: circuit breaker, maximum daily traded value, and manual overrides.

### Phase 7 — Frontend & Real-time UI (P4)
- [ ] Implement FastAPI WebSocket `/ws/stocks/{ticker}` that subscribes to Redis channels and streams events to authenticated clients.
- [ ] Update Next.js frontend to consume WebSocket updates, display live tick/1m-candle data, highlight unusual_volume and insider events, and display active signals with risk overlays.
- [ ] Implement execution UI flow that shows order preview, risk metrics, and requires explicit confirmation; connect to backend execution endpoints.
- [ ] Add frontend integration tests and WebSocket tests (mock server) to validate message flows.

### Phase 8 — Monitoring, CI/CD & Production Hardening (P5)
- [ ] Implement GitHub Actions CI: run unit tests, integration tests (where feasible), lint (ruff/black), type checks (mypy/tsc), and build artifacts.
- [ ] Add Sentry for error monitoring and Prometheus exporters + Grafana dashboards for latency, task queue depth, error rates, and model throughput.
- [ ] Add automated canary deployment and health-check-based rollback for backend services.
- [ ] Add DB backup schedule and disaster recovery playbook in docs/.

### Phase 9 — Compliance, Security & Documentation (Ongoing)
- [ ] Implement full audit trail: store feature_snapshot_id, model_id, signal_id, and execution_id for each trade decision (immutable logs).
- [ ] Add data provenance docs for each external source: rate limits, storage retention, licensing, and contact info.
- [ ] Add secrets management plan (1Password/Vault) and rotate API keys regularly; ensure `.env.example` contains no secrets.
- [ ] Legal checklist to review data usage policies for the exchange/broker and third-party APIs.

### Ongoing Maintenance & Ops
- [ ] Daily: data ingestion and integrity checks, confirm scheduled Celery tasks run successfully.
- [ ] Weekly: run automated backtest with recent data; check for signs of model drift.
- [ ] On drift detection: trigger retraining workflow and run validation ablation tests before promoting new model.
- [ ] Monthly: review performance vs baseline and archive model/regression reports.

---

## How to use this checklist
1. Create tracking items in your project board or use the repository `todos` SQL table for task tracking.
2. Prioritize Phase 0→Phase 1→Phase 2 sequentially; parallelize medium/low priority tasks where teams exist.
3. For any data-source addition (insider/options/ticks) run ablation experiments to validate uplift before committing to long-term maintenance.

---

If anything in this checklist needs to be split into smaller tasks or added to the `todos` table, reply with the phase(s) to insert and the assistant will create the tracked todos and initial placeholders.

