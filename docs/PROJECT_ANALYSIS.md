# TFT Trader - Project Analysis Report

**Project:** Temporal Sentiment Trader  
**Type:** Algorithmic Swing Trading Platform with ML  
**Status:** Active Development (Week 2 of 12)  
**Last Analyzed:** 2026-02-15

---

## 1. Executive Summary

TFT Trader is a production-grade, full-stack algorithmic trading system that combines:
- **Reddit sentiment analysis** for early retail investor momentum detection
- **Technical indicators** (RSI, MACD, Bollinger Bands, SMA)
- **Temporal Fusion Transformer ensemble** (TFT + LSTM + XGBoost + LightGBM)
- **Strict risk management** (position sizing, stop-loss, confidence filtering)

**Target Performance:** 60-65% win rate on 3-7 day swing trades with 5-10% average gains.

---

## 2. Technology Stack

### Backend
| Component | Technology | Version |
|-----------|-----------|---------|
| Framework | FastAPI | 0.110.0 |
| Database | PostgreSQL | 16.0 |
| ORM | SQLAlchemy | 2.0.25 |
| Migrations | Alembic | 1.13.1 |
| Task Queue | Celery | 5.3.6 |
| Cache | Redis | 5.0.1 |
| ML Framework | PyTorch | 2.2.1 |
| Gradient Boosting | XGBoost | 2.0.3 |
| Gradient Boosting | LightGBM | 4.3.0 |
| Stock Data | yfinance | 0.2.36 |
| Technical Indicators | pandas-ta | 0.3.14b0 |
| Reddit API | PRAW | 7.7.1 |
| Sentiment | vaderSentiment | 3.3.2 |

### Frontend
| Component | Technology |
|-----------|-----------|
| Framework | Next.js 15 |
| Language | TypeScript |
| Styling | Tailwind CSS |
| Charts | TradingView, Recharts |

### DevOps
- Docker & Docker Compose
- UV package manager
- GitHub Actions (planned)

---

## 3. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DATA INGESTION LAYER                          │
├─────────────────────────────────────────────────────────────────────┤
│  ┌────────────────┐  ┌────────────────┐  ┌─────────────────────┐ │
│  │ Reddit Scraper │  │ Stock Scraper  │  │  Scheduled Tasks    │ │
│  │ (PRAW + VADER) │  │ (yfinance)     │  │  (Celery + Beat)    │ │
│  └───────┬────────┘  └───────┬────────┘  └──────────┬──────────┘ │
└─────────────────────────────────────────────────────────────────────┘
                                 ↓
┌─────────────────────────────────────────────────────────────────────┐
│                    DATABASE LAYER (PostgreSQL)                       │
├─────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────────┐  │
│  │  reddit_posts   │  │  stock_prices   │  │ trading_signals │  │
│  └─────────────────┘  └─────────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                                 ↓
┌─────────────────────────────────────────────────────────────────────┐
│                    FEATURE ENGINEERING LAYER                         │
├─────────────────────────────────────────────────────────────────────┤
│  Momentum Features (RSI, MACD, SMA, BB) + Sentiment Features        │
└─────────────────────────────────────────────────────────────────────┘
                                 ↓
┌─────────────────────────────────────────────────────────────────────┐
│                      ML PREDICTION LAYER                            │
├─────────────────────────────────────────────────────────────────────┤
│  Ensemble: LSTM (30%) + XGBoost (40%) + LightGBM (30%)              │
└─────────────────────────────────────────────────────────────────────┘
                                 ↓
┌─────────────────────────────────────────────────────────────────────┐
│                    RISK MANAGEMENT LAYER                            │
├─────────────────────────────────────────────────────────────────────┤
│  Confidence (70%) + Position Sizing (20%) + Stop-Loss (5%)          │
└─────────────────────────────────────────────────────────────────────┘
                                 ↓
┌─────────────────────────────────────────────────────────────────────┐
│                      API LAYER (FastAPI)                            │
├─────────────────────────────────────────────────────────────────────┤
│  REST Endpoints + Rate Limiting + Redis Caching                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 4. Database Schema

### reddit_posts
- `post_id` (VARCHAR, UNIQUE)
- `title`, `text`, `subreddit`
- `tickers` (ARRAY)
- `sentiment_score` (FLOAT, -1.0 to 1.0)
- `score`, `num_comments`, `upvote_ratio`
- `created_at`, `scraped_at`

### stock_prices
- `ticker`, `date` (UNIQUE CONSTRAINT)
- OHLCV: `open_price`, `high`, `low`, `close`, `adjusted_close`, `volume`
- Technical: `rsi`, `macd`, `macd_signal`, `bb_upper`, `bb_lower`
- Moving Averages: `sma_50`, `sma_200`
- Volume: `volume_ratio`

### trading_signals
- `ticker`, `signal` (BUY/SELL/HOLD)
- `confidence`, `entry_price`, `target_price`, `stop_loss`
- `risk_reward_ratio`, `position_size_pct`
- `is_active`, `exit_price`, `exit_reason`
- `generated_at`, `expires_at`, `closed_at`

---

## 5. Key Components

### 5.1 Scrapers

**Reddit Scraper** ([`backend/scrapers/reddit_scraper.py`](backend/scrapers/reddit_scraper.py))
- Multi-subreddit support (r/wallstreetbets, r/stocks, r/investing)
- Custom VADER lexicon with 40+ stock market terms
- Ticker extraction via regex ($TSLA, TSLA)
- Retry logic with exponential backoff
- Comment scraping with nested replies

**Stock Scraper** ([`backend/scrapers/stock_scraper.py`](backend/scrapers/stock_scraper.py))
- OHLCV data from Yahoo Finance
- Technical indicators: RSI (14), MACD (12,26,9), Bollinger Bands (20,2), SMA 50/200
- Async thread pool execution
- 3-month historical lookback

### 5.2 Risk Manager

**Implementation:** [`backend/services/risk_manager.py`](backend/services/risk_manager.py) (488 lines)

**Validation Rules:**
1. **Confidence Filter:** Min 70% probability
2. **Price Validation:** Entry < Stop Loss < Target
3. **Risk/Reward Ratio:** Min 1:2 (1 risk for 2 reward)
4. **Position Sizing:** Max 2% risk, 20% position size
5. **Portfolio Constraints:** Max 5 concurrent positions, 15% drawdown limit

**Test Coverage:** 29 passing unit tests

### 5.3 Feature Engineering

**Implementation:** [`backend/ml/features/build.py`](backend/ml/features/build.py) (500+ lines)

**Features Generated:**
- Technical: RSI, MACD, Bollinger Bands, SMA crossover, volume ratio
- Sentiment: Score, trend, mention count, conviction
- Derived: Momentum score, breakout signal, reversal signal, combined signal
- **Total:** 45 features

### 5.4 ML Models

**Ensemble Architecture:**
- **LSTM (30% weight):** 2 LSTM layers (128, 64) + Dense, 30-day sequence input
- **XGBoost (40% weight):** max_depth=6, feature importance
- **LightGBM (30% weight):** Fast inference, num_leaves=31

**Model Files:**
- [`backend/ml/models/tft_model.py`](backend/ml/models/tft_model.py)
- [`backend/ml/models/xgboost_model.py`](backend/ml/models/xgboost_model.py)
- [`backend/ml/models/lightgbm_model.py`](backend/ml/models/lightgbm_model.py)
- [`backend/ml/models/ensemble.py`](backend/ml/models/ensemble.py)

### 5.5 API Endpoints

**Base URL:** `/api/v1`

**Posts Routes** ([`backend/api/routes/posts.py`](backend/api/routes/posts.py)):
- `GET /posts/` - Paginated Reddit posts
- `GET /posts/ticker/{ticker}` - Filter by stock
- `GET /posts/trending` - Most mentioned tickers
- `GET /posts/sentiment/{ticker}` - Aggregate metrics
- `POST /posts/scrape/{subreddit}` - Manual scrape trigger

**Stock Routes** ([`backend/api/routes/stocks.py`](backend/api/routes/stocks.py)):
- `GET /stocks/` - List stocks
- `GET /stocks/{ticker}` - Stock details
- `GET /stocks/{ticker}/history` - Historical data
- `GET /stocks/{ticker}/indicators` - Technical indicators
- `POST /stocks/fetch/{ticker}` - Fetch latest data

**Middleware:**
- Rate limiting with Redis ([`backend/api/middleware/rate_limit.py`](backend/api/middleware/rate_limit.py))
- CORS configuration

### 5.6 Background Tasks

**Celery Configuration:** [`backend/celery_app.py`](backend/celery_app.py)

**Scheduled Tasks:**
- `scrape_reddit_scheduled` - Every 30 minutes
- `fetch_stocks_scheduled` - Hourly
- `fetch_single_stock` - On-demand

---

## 6. Docker Configuration

**Development Setup:** [`docker/docker-compose.dev.yml`](docker/docker-compose.dev.yml)

**Services:**
- PostgreSQL (port 5432)
- Redis (port 6379)
- Celery Worker
- Celery Beat Scheduler
- Flower UI (port 5555)

---

## 7. Testing Coverage

| Test Suite | File | Status |
|------------|------|--------|
| Risk Manager Unit Tests | [`tests/unit/test_risk_manager.py`](tests/unit/test_risk_manager.py) | 29 PASSED |
| Scraper Retry Integration | [`tests/integration/test_scraper_retry.py`](tests/integration/test_scraper_retry.py) | 24 PASSED |
| Scraping Integration | [`tests/integration/test_scraping_integration.py`](tests/integration/test_scraping_integration.py) | 4 PASSED |
| Feature Builder Unit | [`tests/unit/test_features_build.py`](tests/unit/test_features_build.py) | Present |

---

## 8. Trading Strategy

### Entry Criteria (BUY Signal)
All conditions must align:
- **Technical:** RSI < 35, MACD > Signal, Close > SMA 50, Volume > 1.5x avg
- **Sentiment:** Score > 0.3, rising over 5 days, mentions > 20
- **ML:** Ensemble = BUY, Confidence > 70%
- **Risk:** Positions < 5, Drawdown < 15%, R/R > 1:2

### Exit Criteria
1. **Take Profit:** +7% target hit
2. **Stop Loss:** -5% hit
3. **Signal Flip:** Technical or sentiment reversal
4. **Time Decay:** Position held > 7 days

### Position Sizing
```python
risk_amount = portfolio * 0.02  # Max 2% risk
position_size = risk_amount / stop_loss_distance
position_size = min(position_size, portfolio * 0.20)  # Cap at 20%
```

---

## 9. Project Status

### Completed (Week 1-2)
- ✅ Database schema and migrations
- ✅ Reddit scraper with retry logic
- ✅ Stock scraper with technical indicators
- ✅ REST API endpoints
- ✅ Risk manager with validation
- ✅ Feature engineering pipeline
- ✅ Rate limiting middleware
- ✅ Docker Compose dev setup

### In Progress
- Week 2: Docker Compose verification
- Week 3: Feature builder integration

### Planned
- Week 3-4: ML training pipeline
- Week 5-6: Signal generation + inference
- Week 7-10: Frontend dashboard
- Week 11-12: Production deployment

---

## 10. File Structure

```
tft-trader/
├── backend/
│   ├── api/                    # FastAPI app
│   │   ├── main.py            # Entry point
│   │   ├── routes/            # Endpoints
│   │   ├── schemas/           # Pydantic models
│   │   └── middleware/        # Rate limiting
│   ├── models/                # SQLAlchemy ORM
│   ├── scrapers/              # Data collection
│   ├── services/              # Business logic
│   ├── ml/                    # Machine learning
│   ├── tasks/                 # Celery tasks
│   ├── utils/                 # Utilities
│   ├── config/                # Settings
│   └── database/              # DB config
├── frontend/                   # Next.js app
├── tests/                     # Test suite
├── scripts/                   # Utility scripts
├── docs/                      # Documentation
├── alembic/                   # Migrations
├── docker/                    # Container configs
└── Makefile                   # Build commands
```

---

## 11. Key Dependencies

**Runtime:**
- fastapi, uvicorn
- sqlalchemy, asyncpg, alembic
- redis, celery
- praw, yfinance
- torch, xgboost, lightgbm
- pandas, numpy
- vadersentiment, pandas-ta

**Development:**
- pytest, pytest-asyncio
- ruff, black

---

## 12. Recommendations

1. **Complete Docker Setup:** Verify Celery workers and Beat scheduler are working
2. **ML Integration:** Implement training pipeline with MLflow tracking
3. **Frontend:** Complete Next.js dashboard with TradingView charts
4. **CI/CD:** Set up GitHub Actions for automated testing
5. **Monitoring:** Add Sentry error tracking and Prometheus metrics

---

## 13. Quick Start Commands

```bash
# Install dependencies
make install

# Start Docker services
docker-compose -f docker-compose.dev.yml up -d

# Run migrations
make migrate

# Start API
make app

# Start Celery worker
make worker

# Start Celery beat
make beat

# Run tests
make test

# Lint code
make lint
```

---

*Report generated from project analysis on 2026-02-15*
