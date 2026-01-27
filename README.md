# TFT Trader

**Algorithmic Swing Trading Platform with ML-Driven Sentiment Analysis**

TFT Trader is a production-grade, full-stack trading system that combines Reddit sentiment analysis with technical momentum indicators to generate algorithmic swing trading signals. The platform uses an ensemble ML approach (LSTM, XGBoost, LightGBM) with strict risk management to target 60-65% win rates on 3-7 day trades.

**Project Status:** Active Development | Week 2 of 12  
**Strategy:** Swing + Momentum Trading  
**Tech Stack:** FastAPI, PostgreSQL, PyTorch, Next.js

---

## Overview

### Core Concept

Capture short-term momentum opportunities by combining:
- **Reddit sentiment analysis** (early detection of retail investor momentum)
- **Technical indicators** (RSI, MACD, Bollinger Bands, moving averages)
- **Ensemble ML predictions** (multiple models voting for robustness)
- **Automated risk management** (position sizing, stop-loss, confidence filtering)

### Key Differentiators

1. **Early Sentiment Detection** - Reddit signals momentum before mainstream news
2. **Multi-Model Ensemble** - LSTM + XGBoost + LightGBM reduce overfitting
3. **Risk-First Design** - Every signal validated by risk manager before execution
4. **Production Architecture** - Async APIs, background tasks, proper observability

---

## Architecture

### System Design

```
Data Ingestion → Feature Engineering → ML Prediction → Risk Validation → Signal Generation
      ↓                  ↓                   ↓                ↓                 ↓
  PostgreSQL         Database           Ensemble         Risk Manager      Frontend
   + Redis                              Models                            Dashboard
```

**Data Layer**
- Reddit scraper (PRAW) with custom VADER sentiment lexicon
- Stock scraper (yfinance) with technical indicators
- PostgreSQL for persistence, Redis for caching

**ML Layer**
- LSTM (30%) - Sequence patterns over 30-day windows
- XGBoost (40%) - Feature importance, most reliable
- LightGBM (30%) - Fast inference
- Ensemble voting with 70%+ confidence threshold

**Risk Layer**
- Position sizing: Max 20% per position, 2% risk per trade
- Stop-loss: Automatic -5% exit
- Confidence filtering: Only trade signals >70% probability
- Portfolio constraints: Max 5 concurrent positions, 15% drawdown limit

**API Layer**
- FastAPI with async operations
- REST endpoints for historical data
- WebSocket for real-time updates (future)

### Technology Stack

**Backend:** FastAPI, PostgreSQL, SQLAlchemy 2.0, Alembic, Celery, Redis  
**ML:** PyTorch (LSTM), XGBoost, LightGBM, pandas-ta  
**Data:** yfinance, PRAW, vaderSentiment  
**Frontend:** Next.js 15, TypeScript, Tailwind, TradingView  
**DevOps:** Docker, GitHub Actions, Railway/Render, Vercel

---

## Features

### Implemented (Week 1-2)

**Reddit Sentiment Engine**
- Multi-subreddit scraping (r/wallstreetbets, r/stocks, r/investing)
- Custom VADER lexicon with 40+ stock market terms
- Ticker extraction from post text
- Sentiment scoring with engagement metrics

**Stock Data Pipeline**
- OHLCV data from Yahoo Finance
- Technical indicators: RSI, MACD, Bollinger Bands, SMA 50/200, Volume Ratio
- 3-month historical lookback for moving averages
- Async scraping with error handling

**REST API**
- `GET /posts/` - Paginated Reddit posts with sentiment
- `GET /posts/ticker/{ticker}` - Filter posts by stock symbol
- `GET /posts/trending` - Most mentioned tickers
- `GET /posts/sentiment/{ticker}` - Aggregate sentiment metrics
- `GET /health` - Database connectivity check

**Database Schema**
- `reddit_posts` - Sentiment, tickers, engagement
- `stock_prices` - OHLCV + momentum indicators
- `trading_signals` - BUY/SELL/HOLD with risk parameters

### Planned (Week 3-12)

**Week 3-4: ML Pipeline**
- Feature engineering (45 features combining price + sentiment)
- LSTM training on sequence data
- XGBoost/LightGBM training on feature vectors
- Ensemble voting system
- Backtesting framework on 3-year historical data

**Week 5-6: Trading Logic**
- Risk manager implementation
- Signal generation with entry/exit logic
- Position sizing calculator
- Stop-loss/target automation
- Performance tracking

**Week 7-10: Frontend**
- Dashboard with trending stocks
- TradingView price charts
- Sentiment timeline visualization
- Active signals display
- Portfolio tracking (P&L, win rate)
- WebSocket real-time updates

**Week 11-12: Production**
- Docker containerization
- CI/CD pipeline
- Error monitoring (Sentry)
- Deployment to Railway + Vercel

---

## Trading Strategy

### Entry Criteria (BUY Signal)

All conditions must align:

**Technical Momentum**
- RSI < 35 (oversold with reversal potential)
- MACD > Signal (bullish crossover)
- Close > SMA 50 (price above support)
- Volume > 1.5x average (momentum confirmation)

**Sentiment Momentum**
- Sentiment score > 0.3 (positive Reddit sentiment)
- Sentiment rising over 5-day period
- Mention count > 20 posts (high conviction)

**ML Validation**
- Ensemble prediction = BUY
- Confidence > 70%
- All 3 models agree or strong majority

**Risk Checks**
- Current positions < 5
- Portfolio drawdown < 15%
- Risk/reward ratio > 1:2

### Exit Criteria

1. **Take Profit** - Price hits +7% target
2. **Stop Loss** - Price hits -5% stop
3. **Signal Flip** - Technical or sentiment reversal
4. **Time Decay** - Position held > 7 days

### Risk Management

**Position Sizing Formula:**
```python
risk_amount = portfolio * 0.02  # Max 2% risk per trade
position_size = risk_amount / stop_loss_distance
position_size = min(position_size, portfolio * 0.20)  # Cap at 20%
```

**Risk Limits:**
- Max position: 20% of portfolio
- Max risk per trade: 2%
- Stop loss: 5% below entry
- Max concurrent positions: 5
- Portfolio drawdown limit: 15%

**Expected Performance:**
- Win rate: 60-65%
- Average gain: 5-10% per trade
- Average loss: <5%
- Risk/reward: 1:2 minimum
- Trade frequency: 2-5 per week

---

## Repository Structure

```
tft-trader/
├── backend/
│   ├── api/                  # FastAPI application
│   │   ├── main.py           # Entry point
│   │   ├── routes/           # Endpoint definitions
│   │   └── schemas/          # Pydantic models
│   ├── models/               # SQLAlchemy ORM models
│   │   ├── reddit.py
│   │   ├── stock.py
│   │   └── trading_signal.py
│   ├── scrapers/             # Data collection
│   │   ├── reddit_scraper.py
│   │   └── stock_scraper.py
│   ├── services/             # Business logic
│   │   ├── reddit_service.py
│   │   └── stock_service.py
│   ├── ml/                   # Machine learning
│   │   ├── models/           # Model architectures
│   │   ├── training/         # Training scripts
│   │   └── inference/        # Prediction service
│   ├── utils/                # Utilities
│   │   ├── sentiment.py      # VADER analyzer
│   │   └── logger.py
│   ├── config/               # Configuration
│   └── database/             # DB setup
├── frontend/                 # Next.js application
│   ├── app/
│   ├── components/
│   └── lib/
├── tests/                    # Tests
├── scripts/                  # Utility scripts
├── docs/                     # Documentation
│   ├── ARCHITECTURE.md
│   └── TRADING_STRATEGY.md
├── alembic/                  # Migrations
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

---

## Getting Started

### Prerequisites

- Python 3.12+
- PostgreSQL 14+
- Node.js 20+
- UV package manager (`pip install uv`)
- Redis (for Celery task queue)

### Backend Setup

```bash
# Clone repository
git clone <your-repo-url>
cd tft-trader

# Install dependencies
uv sync

# Configure environment
cp .env.example .env
# Edit .env with your database URL, API keys

# Run migrations
uv run alembic upgrade head

# Start Redis (separate terminal)
redis-server

# Start Celery worker (separate terminal)
uv run celery -A backend.tasks worker --loglevel=info

# Start API server
uv run uvicorn backend.api.main:app --reload
```

**API available at:** http://localhost:8000  
**Docs:** http://localhost:8000/docs

### Environment Variables

```env
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host:port/dbname

# Reddit API (optional, for live data)
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_secret
REDDIT_USER_AGENT=TFTTrader/1.0

# Redis
REDIS_URL=redis://localhost:6379/0

# API Configuration
API_V1_STR=/api/v1
PROJECT_NAME=TFT Trader
```

### Frontend Setup (Coming in Week 7)

```bash
cd frontend
npm install
npm run dev
```

**Dashboard at:** http://localhost:3000

### Testing

```bash
# Test stock scraper
uv run python test_stock_scraper.py

# Run unit tests
uv run pytest tests/unit/

# Run integration tests
uv run pytest tests/integration/
```

---

## Development Roadmap

**Week 1-2: Foundation** ✅
- PostgreSQL setup, Reddit scraper, stock data pipeline, REST API

**Week 3-4: ML Training**
- Feature engineering, LSTM training, XGBoost/LightGBM, backtesting

**Week 5-6: Trading Logic**
- Risk manager, signal generation, position sizing, performance tracking

**Week 7-10: Frontend**
- Dashboard, charts, sentiment timeline, real-time updates

**Week 11-12: Production**
- Docker, CI/CD, monitoring, deployment

---

## Success Metrics

**Technical Performance**
- API response time: <200ms
- Database query time: <50ms
- Scraper throughput: 100 posts/min
- System uptime: 99.9%

**ML Performance** (Target on validation set)
- Prediction accuracy: 65%+
- Sharpe ratio: >1.5
- Max drawdown: <15%
- Win rate: 60-65%

**Trading Performance** (Simulated)
- Average trade duration: 3-7 days
- Risk/reward: >1:2
- ROI: 20-30% annually (target)
- Consistency: Positive 8/12 months

---

## Tech Stack Details

**Backend Stack:**
- **FastAPI 0.128.0** - Async REST API with auto docs
- **SQLAlchemy 2.0.23** - Async ORM with type safety
- **Alembic 1.12.1** - Database migrations
- **PostgreSQL** - Primary data store (hosted on Neon)
- **Celery 5.3.4 + Redis** - Task queue for async scraping

**ML Stack:**
- **PyTorch 2.1.1** - LSTM for sequence modeling
- **XGBoost 2.0.2** - Gradient boosting for tabular features
- **LightGBM 4.1.0** - Fast gradient boosting
- **pandas-ta 0.4.71b0** - Technical indicator calculations
- **scikit-learn** - Preprocessing, metrics, model selection

**Data Sources:**
- **yfinance 1.0** - Stock OHLCV data from Yahoo Finance
- **PRAW 7.7.1** - Reddit API wrapper
- **vaderSentiment 3.3.2** - Sentiment analysis with custom lexicon

---

## Project Structure Philosophy

This codebase follows clean architecture principles:

**Separation of Concerns:**
- `api/` - HTTP layer (routes, schemas, middleware)
- `services/` - Business logic
- `models/` - Database models
- `ml/` - Machine learning pipeline
- `scrapers/` - Data ingestion

**Async-First:**
- All I/O operations use `async/await`
- Database sessions via `AsyncSession`
- Scraping parallelized with `asyncio.gather()`

**Type Safety:**
- Pydantic schemas for API validation
- SQLAlchemy 2.0 typed mappings
- Full type hints in Python code

**Testing:**
- Unit tests for utilities and services
- Integration tests for API endpoints
- Mocked external dependencies

---

## Learning Outcomes

**Backend Engineering:**
- Async Python with FastAPI
- PostgreSQL optimization (indexes, query planning)
- Database migrations with Alembic
- Task queues with Celery

**Machine Learning:**
- Time series forecasting with LSTM
- Ensemble methods (stacking, voting)
- Feature engineering for financial data
- Backtesting and walk-forward validation

**Trading Systems:**
- Risk management and position sizing
- Entry/exit signal generation
- Performance metrics (Sharpe, Sortino, max drawdown)
- Market regime detection

**Full Stack:**
- REST API design
- WebSocket real-time updates
- React Server Components (Next.js 15)
- Docker containerization
- CI/CD with GitHub Actions

---

## Contributing

This is a personal learning project. If you find issues or have suggestions:

1. Open an issue describing the problem
2. Fork the repo and create a feature branch
3. Submit a PR with clear description

---

## License

MIT License - see LICENSE file

---

## Acknowledgments

**Data Sources:**
- Yahoo Finance (via yfinance)
- Reddit API
- Financial modeling inspiration from QuantConnect, Zipline

**ML References:**
- PyTorch documentation
- XGBoost and LightGBM papers
- Andrew Ng's ML courses

---

## Intended Audience

* Backend engineering roles (Python, FastAPI, distributed systems)
* ML engineering roles (training, inference, pipelines)
* Full-stack roles with real-time data requirements
* Interview take-home or portfolio review

---

## Disclaimer

This project is for **educational and research purposes only**.
It is not financial advice and should not be used for live trading without extensive validation, risk controls, and regulatory compliance.

---

**Built with ❤️ as a learning project to master ML engineering and quantitative trading**
