# TFT Trader - System Architecture

**Last Updated:** January 27, 2026  
**Version:** 1.0  
**Project Type:** Swing + Momentum Trading with ML

---

## Table of Contents

1. [Overview](#overview)
2. [Core Principles](#core-principles)
3. [System Architecture](#system-architecture)
4. [Technology Stack](#technology-stack)
5. [Database Schema](#database-schema)
6. [Data Flow](#data-flow)
7. [Component Details](#component-details)
8. [Security & Performance](#security--performance)
9. [Deployment Architecture](#deployment-architecture)

---

## Overview

TFT Trader is an algorithmic swing trading system that combines:
- **Reddit sentiment analysis** (WSB, r/stocks, r/investing)
- **Technical momentum indicators** (RSI, MACD, Bollinger Bands, SMA)
- **Machine Learning predictions** (LSTM, XGBoost, LightGBM ensemble)
- **Risk management** (position sizing, stop-loss, confidence filtering)

**Target:** 60-65% win rate with 5-10% average gains per trade over 3-7 day hold periods.

---

## Core Principles

### 1. Swing Trading Focused
- **Hold Period:** 3-7 days (not day trading, not long-term investing)
- **Target Gains:** 5-10% per trade
- **Data Frequency:** Daily OHLCV after market close (4:30 PM ET)
- **No Intraday Noise:** Ignore minute-level fluctuations

### 2. Momentum-Filtered
- **Entry:** Only when technical momentum + sentiment momentum align
- **Technical Filters:** RSI oversold + MACD crossover + volume spike
- **Sentiment Filter:** Bullish Reddit sentiment + rising mention count
- **Exit:** Momentum reversal (technical or sentiment)

### 3. Algorithmic
- **ML-Driven:** Predictions from ensemble model (no human discretion)
- **Backtested:** Every strategy validated on 2+ years historical data
- **Automated:** Scheduled scraping, signal generation (future: execution)
- **Adaptive:** Model retrains weekly with new data

### 4. Risk-Aware
- **Position Sizing:** Max 20% of portfolio per position
- **Risk per Trade:** Max 2% of portfolio at risk
- **Stop-Loss:** Automatic exit at -5% loss
- **Confidence Filter:** Only trade when ML confidence >70%
- **Diversification:** Max 5 concurrent positions
- **Drawdown Limit:** Stop trading if portfolio down >15%

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                       DATA INGESTION LAYER                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────┐  ┌────────────────┐  ┌─────────────────┐  │
│  │ Reddit Scraper │  │ Stock Scraper  │  │  News Scraper   │  │
│  │ (Sentiment)    │  │ (OHLCV + Tech) │  │  (Events)       │  │
│  └───────┬────────┘  └───────┬────────┘  └────────┬────────┘  │
│          │                    │                     │            │
│     PRAW API          Yahoo Finance           BeautifulSoup     │
│     + VADER           + pandas-ta             (Future)          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    DATABASE LAYER (PostgreSQL)                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌────────────────┐ │
│  │  reddit_posts   │  │  stock_prices   │  │ trading_signals│ │
│  ├─────────────────┤  ├─────────────────┤  ├────────────────┤ │
│  │ sentiment_score │  │ OHLCV data      │  │ BUY/SELL/HOLD  │ │
│  │ tickers[]       │  │ RSI, MACD       │  │ confidence     │ │
│  │ mention_count   │  │ SMA 50/200      │  │ risk params    │ │
│  │                 │  │ BB, Volume      │  │ status         │ │
│  └─────────────────┘  └─────────────────┘  └────────────────┘ │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    FEATURE ENGINEERING LAYER                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Momentum Features              Sentiment Features              │
│  ├─ RSI signals                 ├─ Sentiment score              │
│  ├─ MACD crossovers             ├─ Sentiment trend              │
│  ├─ SMA crossovers              ├─ Mention count                │
│  ├─ BB breakouts                ├─ Conviction level             │
│  └─ Volume spikes               └─ Sentiment volatility         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                        ML PREDICTION LAYER                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Ensemble Model (Weighted Voting)                               │
│  ├─ LSTM (30% weight) - Sequential patterns                     │
│  ├─ XGBoost (40% weight) - Feature importance                   │
│  └─ LightGBM (30% weight) - Fast inference                      │
│                                                                  │
│  Output: BUY/SELL/HOLD + Confidence (0-1)                       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                      RISK MANAGEMENT LAYER                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Risk Manager Validates:                                        │
│  ├─ Confidence threshold (>70%)                                 │
│  ├─ Position size (max 20% portfolio)                           │
│  ├─ Risk per trade (max 2% portfolio)                           │
│  ├─ Stop loss calculation (-5%)                                 │
│  ├─ Target price (+5-10%)                                       │
│  ├─ Risk/reward ratio (min 1:2)                                 │
│  ├─ Max concurrent positions (5)                                │
│  └─ Portfolio drawdown (<15%)                                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                      TRADING SIGNAL LAYER                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Signal Generator:                                              │
│  ├─ Creates TradingSignal record                                │
│  ├─ Sets entry/target/stop prices                               │
│  ├─ Tracks status (active/closed)                               │
│  └─ Logs exit reasons                                           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                       EXECUTION LAYER (Future)                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Broker API Integration (Alpaca/Interactive Brokers)            │
│  ├─ Order placement (market/limit)                              │
│  ├─ Position monitoring (real-time)                             │
│  ├─ Auto-exit on stop-loss/target hit                           │
│  └─ Portfolio rebalancing                                       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                     FRONTEND LAYER (Next.js)                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐   │
│  │  Dashboard   │  │   Signals    │  │    Portfolio       │   │
│  ├──────────────┤  ├──────────────┤  ├────────────────────┤   │
│  │ Trending     │  │ Active       │  │ P&L tracking       │   │
│  │ Sentiment    │  │ Confidence   │  │ Win rate           │   │
│  │ Charts       │  │ Entry/Exit   │  │ Risk metrics       │   │
│  └──────────────┘  └──────────────┘  └────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Technology Stack

### Backend
| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| **Framework** | FastAPI | 0.128.0 | Async REST API |
| **Database** | PostgreSQL | 16.0 | Primary data store |
| **ORM** | SQLAlchemy | 2.0.23 | Async database access |
| **Migrations** | Alembic | 1.12.1 | Schema versioning |
| **Task Queue** | Celery | 5.3.4 | Background jobs |
| **Cache** | Redis | 5.0.1 | Task queue + caching |
| **ML Framework** | PyTorch | 2.1.1 | LSTM training |
| **ML Framework** | XGBoost | 2.0.2 | Gradient boosting |
| **ML Framework** | LightGBM | 4.1.0 | Fast inference |
| **Stock Data** | yfinance | 1.0 | Yahoo Finance API |
| **Technical Indicators** | pandas-ta | 0.4.71b0 | RSI, MACD, BB, SMA |
| **Reddit API** | PRAW | 7.7.1 | Reddit scraping |
| **Sentiment** | vaderSentiment | 3.3.2 | Sentiment analysis |
| **Data Processing** | pandas | 2.1.3 | Data manipulation |
| **Data Processing** | numpy | 2.2.6 | Numerical computing |

### Frontend
| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| **Framework** | Next.js | 15 | React SSR/SSG |
| **Language** | TypeScript | 5.0 | Type safety |
| **Styling** | Tailwind CSS | 3.0 | Utility-first CSS |
| **Charts** | TradingView | - | Professional charts |
| **Charts** | Recharts | 2.0 | React charts |
| **State** | React Context | - | Global state |
| **HTTP Client** | Axios | 1.6 | API requests |
| **Real-time** | WebSockets | - | Live updates |

### DevOps
| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Package Manager** | UV | Fast Python package management |
| **Containers** | Docker | Application containerization |
| **Orchestration** | Docker Compose | Multi-container apps |
| **CI/CD** | GitHub Actions | Automated testing & deployment |
| **Hosting (Backend)** | Railway/Render | Managed cloud hosting |
| **Hosting (Frontend)** | Vercel | Edge network deployment |
| **Hosting (DB)** | Neon PostgreSQL | Serverless Postgres |
| **Monitoring** | Sentry | Error tracking |
| **Logging** | Python logging | Application logs |

---

## Database Schema

### reddit_posts
```sql
CREATE TABLE reddit_posts (
    id SERIAL PRIMARY KEY,
    post_id VARCHAR(20) UNIQUE NOT NULL,
    title TEXT NOT NULL,
    text TEXT,
    subreddit VARCHAR(50) NOT NULL,
    
    -- Extracted tickers
    tickers VARCHAR(10)[] NOT NULL,  -- Array of stock symbols
    
    -- Sentiment analysis
    sentiment_score FLOAT NOT NULL,  -- -1.0 to 1.0 (VADER compound)
    
    -- Engagement metrics
    score INTEGER DEFAULT 0,
    num_comments INTEGER DEFAULT 0,
    upvote_ratio FLOAT,
    
    -- Metadata
    url TEXT,
    author VARCHAR(50),
    post_type VARCHAR(20),  -- 'post', 'comment', 'discussion'
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    scraped_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Indexes
    INDEX idx_tickers USING GIN(tickers),
    INDEX idx_created_at ON reddit_posts(created_at),
    INDEX idx_sentiment ON reddit_posts(sentiment_score)
);
```

### stock_prices
```sql
CREATE TABLE stock_prices (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    
    -- OHLCV data
    open_price FLOAT NOT NULL,
    high FLOAT NOT NULL,
    low FLOAT NOT NULL,
    close FLOAT NOT NULL,
    adjusted_close FLOAT NOT NULL,  -- Adjusted for splits/dividends
    volume BIGINT NOT NULL,
    
    -- Technical Indicators - Momentum
    rsi FLOAT,                      -- Relative Strength Index (14-period)
    macd FLOAT,                     -- MACD (12,26,9)
    macd_signal FLOAT,              -- MACD signal line
    bb_upper FLOAT,                 -- Bollinger Band upper (20,2)
    bb_lower FLOAT,                 -- Bollinger Band lower (20,2)
    
    -- Moving Averages - Swing Trading
    sma_50 FLOAT,                   -- 50-day simple moving average
    sma_200 FLOAT,                  -- 200-day simple moving average
    
    -- Volume Indicators
    volume_ratio FLOAT,             -- Current volume / 20-day avg
    
    -- Timestamps
    date TIMESTAMP WITH TIME ZONE NOT NULL,
    fetched_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT unique_ticker_date UNIQUE (ticker, date),
    INDEX idx_ticker_date ON stock_prices(ticker, date)
);
```

### trading_signals
```sql
CREATE TABLE trading_signals (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    
    -- Signal
    signal VARCHAR(10) NOT NULL,    -- 'BUY', 'SELL', 'HOLD'
    confidence FLOAT NOT NULL,      -- 0.0 to 1.0 (ML model confidence)
    
    -- Price levels
    entry_price FLOAT NOT NULL,
    target_price FLOAT,             -- +5-10% profit target
    stop_loss FLOAT,                -- -5% loss limit
    
    -- Risk metrics
    risk_reward_ratio FLOAT,        -- Target gain / Stop loss distance
    position_size_pct FLOAT,        -- % of portfolio (max 20%)
    
    -- Features that generated signal
    rsi_value FLOAT,
    macd_value FLOAT,
    sentiment_score FLOAT,
    sentiment_trend FLOAT,          -- Sentiment momentum
    
    -- Status tracking
    is_active INTEGER DEFAULT 1,    -- 1=active, 0=closed
    exit_price FLOAT,
    exit_reason VARCHAR(50),        -- 'target', 'stop_loss', 'signal_flip', 'time_decay'
    
    -- Timestamps
    generated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,
    closed_at TIMESTAMP WITH TIME ZONE,
    
    -- Indexes
    INDEX idx_ticker_signal ON trading_signals(ticker, is_active),
    INDEX idx_generated_at ON trading_signals(generated_at)
);
```

---

## Data Flow

### 1. Data Collection (Every Hour)
```
Celery Task Scheduler
    ├─> Reddit Scraper (5 min)
    │   ├─ Scrape r/wallstreetbets, r/stocks, r/investing
    │   ├─ Extract tickers from post text
    │   ├─ Calculate VADER sentiment
    │   └─ Save to reddit_posts table
    │
    └─> Stock Scraper (15 min)
        ├─ Fetch OHLCV for trending tickers
        ├─ Calculate technical indicators (RSI, MACD, SMA, BB)
        ├─ Calculate volume metrics
        └─ Save to stock_prices table
```

### 2. Feature Engineering (Daily @ 5 PM ET)
```
Feature Engineering Pipeline
    ├─> Load last 90 days of data
    ├─> Merge stock_prices + reddit_posts
    ├─> Calculate derived features:
    │   ├─ Momentum signals (RSI crossover, MACD divergence)
    │   ├─ Sentiment trends (5-day delta)
    │   ├─ Volume anomalies (z-score)
    │   └─ Price momentum (5/10/20 day returns)
    └─> Save to features table
```

### 3. ML Prediction (Daily @ 5:30 PM ET)
```
ML Inference Pipeline
    ├─> Load features for all tickers
    ├─> Run ensemble models:
    │   ├─ LSTM (sequence patterns)
    │   ├─ XGBoost (feature importance)
    │   └─ LightGBM (fast inference)
    ├─> Weighted voting (30%/40%/30%)
    └─> Output: BUY/SELL/HOLD + confidence
```

### 4. Signal Generation (Daily @ 5:45 PM ET)
```
Signal Generation Pipeline
    ├─> Filter predictions by confidence >70%
    ├─> For each BUY signal:
    │   ├─ Validate with Risk Manager
    │   ├─ Calculate position size
    │   ├─ Calculate stop-loss & target
    │   ├─ Check portfolio constraints
    │   └─ Create TradingSignal record
    └─> Send notifications (email/webhook)
```

### 5. Position Monitoring (Every 15 min during market hours)
```
Position Monitor
    ├─> Get active signals (is_active=1)
    ├─> Fetch current prices
    ├─> For each position:
    │   ├─ Check if target hit → Close & mark 'target'
    │   ├─ Check if stop-loss hit → Close & mark 'stop_loss'
    │   ├─ Check if sentiment flipped → Close & mark 'signal_flip'
    │   └─ Check if held >7 days → Close & mark 'time_decay'
    └─> Update trading_signals table
```

---

## Component Details

### 1. Reddit Scraper (`backend/scrapers/reddit_scraper.py`)
**Purpose:** Extract posts from Reddit and calculate sentiment

**Implementation:**
- Uses PRAW (Python Reddit API Wrapper)
- Custom VADER lexicon (40+ stock market terms)
- Extracts tickers using regex patterns ($TSLA, TSLA, etc.)
- Stores with deduplication check

**Key Features:**
- Multi-subreddit support
- Post type filtering (hot/new/top)
- Rate limit handling
- Async operation

### 2. Stock Scraper (`backend/scrapers/stock_scraper.py`)
**Purpose:** Fetch OHLCV data and calculate technical indicators

**Implementation:**
- Uses yfinance for Yahoo Finance data
- pandas-ta for indicator calculations
- Async thread pool execution
- 3-month lookback for SMA_200

**Indicators Calculated:**
- **RSI (14):** Overbought/oversold
- **MACD (12,26,9):** Trend strength
- **Bollinger Bands (20,2):** Volatility
- **SMA 50/200:** Trend direction
- **Volume Ratio:** Momentum confirmation

### 3. Feature Engineering (`backend/ml/features/`)
**Purpose:** Transform raw data into ML-ready features

**Features Generated:**
```python
momentum_features = [
    'rsi_oversold',      # RSI < 30
    'rsi_overbought',    # RSI > 70
    'macd_crossover',    # MACD > Signal
    'sma_crossover',     # SMA50 > SMA200 (golden cross)
    'bb_breakout',       # Price > BB_upper
    'volume_spike',      # Volume > 2x avg
]

sentiment_features = [
    'sentiment_score',   # Current VADER score
    'sentiment_ma_5',    # 5-day sentiment avg
    'sentiment_trend',   # sentiment_score - sentiment_ma_5
    'mention_count',     # Number of posts mentioning ticker
    'conviction',        # High (>50 mentions) / Low
]

price_features = [
    'return_5d',         # 5-day price change
    'return_10d',        # 10-day price change
    'volatility_20d',    # 20-day rolling std
]
```

### 4. ML Models (`backend/ml/models/`)

#### LSTM Model
- **Architecture:** 2 LSTM layers (128, 64 units) + Dense
- **Input:** 30-day sequences of features
- **Output:** Probability distribution [BUY, HOLD, SELL]
- **Training:** Binary cross-entropy, Adam optimizer
- **Weight:** 30% in ensemble

#### XGBoost Model
- **Parameters:** max_depth=6, learning_rate=0.1, n_estimators=100
- **Input:** Feature vector (no sequence)
- **Output:** Class probabilities
- **Training:** Multi-class logistic objective
- **Weight:** 40% in ensemble (highest interpretability)

#### LightGBM Model
- **Parameters:** num_leaves=31, learning_rate=0.05
- **Input:** Feature vector
- **Output:** Class probabilities
- **Training:** Fast gradient boosting
- **Weight:** 30% in ensemble

#### Ensemble Logic
```python
final_prediction = (
    0.30 * lstm_proba +
    0.40 * xgb_proba +
    0.30 * lgb_proba
)
signal = argmax(final_prediction)  # BUY/HOLD/SELL
confidence = max(final_prediction)  # 0-1
```

### 5. Risk Manager (`backend/services/risk_manager.py`)
**Purpose:** Validate signals and calculate position parameters

**Rules:**
```python
MAX_POSITION_SIZE = 0.20        # 20% of portfolio
MAX_RISK_PER_TRADE = 0.02       # 2% of portfolio
STOP_LOSS_PCT = 0.05            # 5% loss limit
TARGET_PROFIT_MIN = 0.05        # 5% minimum target
TARGET_PROFIT_MAX = 0.10        # 10% maximum target
MIN_CONFIDENCE = 0.70           # 70% ML confidence
MAX_POSITIONS = 5               # Concurrent positions
MAX_DRAWDOWN = 0.15             # 15% portfolio drawdown
```

**Position Sizing Formula:**
```python
risk_amount = portfolio_value * MAX_RISK_PER_TRADE
position_size = risk_amount / (entry_price * STOP_LOSS_PCT)
position_size = min(position_size, portfolio_value * MAX_POSITION_SIZE)
```

---

## Security & Performance

### Security Measures
1. **Environment Variables:** All secrets in `.env` (never committed)
2. **Database:** SSL-required connections to Neon PostgreSQL
3. **API Keys:** Rate-limited, rotated regularly
4. **Authentication:** JWT tokens (future: OAuth2)
5. **CORS:** Restricted to frontend domain only

### Performance Optimizations
1. **Async I/O:** FastAPI + asyncpg for non-blocking DB
2. **Connection Pooling:** 10 concurrent DB connections
3. **Caching:** Redis for frequently accessed data
4. **Batch Processing:** Bulk inserts for historical data
5. **Indexes:** Optimized queries on ticker, date, sentiment
6. **Background Tasks:** Celery for long-running jobs

### Scalability Considerations
- **Horizontal:** Multiple Celery workers
- **Vertical:** Database read replicas
- **Caching:** Redis for hot data
- **CDN:** Static assets via Vercel Edge

---

## Deployment Architecture

### Development Environment
```
localhost:8000 (FastAPI)
localhost:3000 (Next.js)
localhost:5432 (PostgreSQL - local)
localhost:6379 (Redis - local)
```

### Production Environment
```
Backend:       railway.app or render.com
Frontend:      vercel.app (Edge Network)
Database:      neon.tech (Serverless Postgres)
Cache/Queue:   redis.com (Managed Redis)
```

### CI/CD Pipeline
```
GitHub Push
    ↓
GitHub Actions
    ├─> Run tests (pytest)
    ├─> Lint code (ruff, black)
    ├─> Build Docker image
    ├─> Push to registry
    └─> Deploy to Railway/Render
    
Frontend:
    ├─> Build Next.js
    ├─> Run type checks
    └─> Deploy to Vercel (auto)
```

---

## Implementation Timeline

| Week | Phase | Status |
|------|-------|--------|
| 1 | Backend foundation + Reddit sentiment | ✅ Complete |
| 2 | Stock scraper + Real data integration | 🔄 In Progress |
| 3-4 | ML pipeline + Feature engineering | ⏳ Planned |
| 5-6 | Ensemble model + Risk management | ⏳ Planned |
| 7-8 | Frontend core (Dashboard, Charts) | ⏳ Planned |
| 9-10 | Frontend advanced (Real-time, Alerts) | ⏳ Planned |
| 11 | Production prep (Docker, CI/CD) | ⏳ Planned |
| 12 | Deployment + Testing | ⏳ Planned |

---

**Document Version:** 1.0  
**Last Updated:** January 27, 2026  
**Maintained By:** TFT Trader Development Team
