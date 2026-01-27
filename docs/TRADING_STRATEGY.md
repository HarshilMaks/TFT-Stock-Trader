# TFT Trader - Trading Strategy & ML Approach

**Last Updated:** January 27, 2026  
**Strategy Type:** Swing + Momentum Trading  
**ML Approach:** Ensemble (LSTM + XGBoost + LightGBM)

---

## Table of Contents

1. [Trading Strategy Overview](#trading-strategy-overview)
2. [Entry Criteria](#entry-criteria)
3. [Exit Criteria](#exit-criteria)
4. [Risk Management](#risk-management)
5. [ML Model Architecture](#ml-model-architecture)
6. [Feature Engineering](#feature-engineering)
7. [Backtesting Methodology](#backtesting-methodology)
8. [Performance Metrics](#performance-metrics)
9. [Edge Analysis](#edge-analysis)

---

## Trading Strategy Overview

### Core Concept
**Capture short-term momentum fueled by Reddit sentiment combined with technical breakouts.**

### Strategy Type
- **Swing Trading:** Hold 3-7 days
- **Momentum-Based:** Only trade when multiple indicators align
- **Sentiment-Driven:** Use Reddit as early momentum signal
- **Risk-Controlled:** Strict position sizing and stop-loss

### Target Market
- **Asset Class:** US Equities
- **Focus:** High-liquidity stocks ($1B+ market cap)
- **Universe:** Stocks mentioned on r/wallstreetbets, r/stocks, r/investing
- **Typical Tickers:** AAPL, TSLA, NVDA, SPY, MSFT, AMD, etc.

### Expected Performance
| Metric | Target | Notes |
|--------|--------|-------|
| **Win Rate** | 60-65% | Realistic for swing trading |
| **Average Gain** | 5-10% | Per winning trade |
| **Average Loss** | <5% | Stop-loss protected |
| **Risk/Reward** | 1:2 minimum | $1 risk for $2+ reward |
| **Max Drawdown** | 15% | Circuit breaker triggers |
| **Trade Frequency** | 2-5/week | Selective, high-confidence only |

---

## Entry Criteria

### Signal Generation Logic

A **BUY** signal is generated when **ALL** of the following conditions are met:

#### 1. Technical Momentum Alignment
```python
# Oversold with reversal potential
rsi < 35                        # RSI in oversold zone

# Bullish momentum building
macd > macd_signal              # MACD crossed above signal line
macd_histogram increasing       # Momentum accelerating

# Price above key support
close > sma_50                  # Above 50-day moving average
sma_50 > sma_200               # Golden cross (bullish trend)

# Volume confirmation
volume_ratio > 1.5              # 50% above 20-day average
```

#### 2. Sentiment Momentum Alignment
```python
# Bullish community sentiment
sentiment_score > 0.3           # Positive sentiment (VADER compound)

# Sentiment gaining strength
sentiment_trend > 0             # Rising over last 5 days
sentiment_ma_5 > sentiment_ma_20  # Short-term > long-term

# High conviction
mention_count > 20              # Significant discussion volume
post_engagement > 100           # Combined upvotes + comments
```

#### 3. ML Confidence
```python
# Ensemble model prediction
model_prediction == 'BUY'       # All models agree or majority vote

# High confidence threshold
model_confidence > 0.70         # 70%+ probability

# Model agreement
lstm_confidence > 0.60 and      # Sequence pattern detected
xgb_confidence > 0.65 and       # Feature importance aligned
lgb_confidence > 0.60           # Fast model confirms
```

#### 4. Risk Validation
```python
# Portfolio constraints
current_positions < 5           # Max 5 concurrent positions
portfolio_drawdown < 15%        # Not in drawdown mode

# Position sizing
proposed_position < 20% portfolio  # Max position size

# Risk/reward
(target_price - entry_price) / (entry_price - stop_loss) > 2.0
```

### Entry Execution
```python
entry_price = current_market_price
target_price = entry_price * 1.07    # +7% profit target
stop_loss = entry_price * 0.95       # -5% stop loss
position_size = calculate_position_size(portfolio, stop_loss_distance)
```

---

## Exit Criteria

### Exit Signal Types

#### 1. Take Profit (Target Hit)
```python
if current_price >= target_price:
    exit_reason = 'target'
    exit_price = target_price
    CLOSE POSITION
```

#### 2. Stop Loss (Risk Control)
```python
if current_price <= stop_loss:
    exit_reason = 'stop_loss'
    exit_price = stop_loss
    CLOSE POSITION
```

#### 3. Signal Flip (Momentum Reversal)
```python
# Technical reversal
if (rsi > 65 and                    # Overbought
    macd < macd_signal and          # Bearish crossover
    close < sma_50):                # Broke support
    
    exit_reason = 'signal_flip'
    exit_price = current_market_price
    CLOSE POSITION

# Sentiment reversal
if (sentiment_score < -0.2 and      # Turned bearish
    sentiment_trend < -0.1):        # Rapidly declining
    
    exit_reason = 'signal_flip'
    exit_price = current_market_price
    CLOSE POSITION
```

#### 4. Time Decay (Max Hold Period)
```python
if days_held > 7:                   # Exceeded swing trade window
    exit_reason = 'time_decay'
    exit_price = current_market_price
    CLOSE POSITION
```

#### 5. Risk Event (External Trigger)
```python
# Portfolio-level risk
if portfolio_drawdown > 15%:
    CLOSE ALL POSITIONS
    PAUSE TRADING

# Stock-specific risk
if stock_news_sentiment < -0.5:     # Negative news event
    CLOSE POSITION IMMEDIATELY
```

---

## Risk Management

### Position Sizing Formula

```python
def calculate_position_size(portfolio_value, entry_price, stop_loss):
    """
    Risk-adjusted position sizing using Kelly Criterion variant
    """
    # Maximum risk per trade
    max_risk_dollars = portfolio_value * 0.02  # 2% max risk
    
    # Distance to stop loss
    stop_loss_distance = entry_price - stop_loss
    stop_loss_pct = stop_loss_distance / entry_price
    
    # Position size based on risk
    shares = max_risk_dollars / stop_loss_distance
    position_value = shares * entry_price
    
    # Cap at max position size
    max_position_value = portfolio_value * 0.20  # 20% max
    position_value = min(position_value, max_position_value)
    
    return position_value
```

### Example Calculation
```
Portfolio Value: $10,000
Entry Price: $100
Stop Loss: $95
Max Risk: 2% = $200

Stop Loss Distance: $5
Shares: $200 / $5 = 40 shares
Position Value: 40 * $100 = $4,000 (40% of portfolio)

Capped at 20%: 20 shares = $2,000
```

### Risk Limits

| Parameter | Limit | Rationale |
|-----------|-------|-----------|
| **Max Position Size** | 20% | Diversification |
| **Max Risk per Trade** | 2% | Preserve capital |
| **Stop Loss** | 5% | Limit downside |
| **Max Positions** | 5 | Manageable monitoring |
| **Max Drawdown** | 15% | Circuit breaker |
| **Min Confidence** | 70% | Quality over quantity |
| **Min Risk/Reward** | 1:2 | Favorable odds |

### Diversification Rules
- Max 2 positions in same sector
- No correlated pairs (e.g., both TSLA and NIO)
- Minimum $1B market cap (liquidity)
- Avoid earnings week volatility

---

## ML Model Architecture

### Ensemble Overview

**Philosophy:** Combine multiple models to reduce overfitting and increase robustness.

```
Input Features → [LSTM, XGBoost, LightGBM] → Weighted Voting → Final Prediction
```

### 1. LSTM Model (Sequence Patterns)

**Architecture:**
```python
model = Sequential([
    LSTM(128, return_sequences=True, input_shape=(30, n_features)),
    Dropout(0.2),
    LSTM(64),
    Dropout(0.2),
    Dense(32, activation='relu'),
    Dense(3, activation='softmax')  # [BUY, HOLD, SELL]
])
```

**Training:**
- **Input:** 30-day sequences of features
- **Loss:** Categorical cross-entropy
- **Optimizer:** Adam (lr=0.001)
- **Epochs:** 50 (early stopping)
- **Batch Size:** 32

**Strengths:**
- Captures temporal patterns
- Learns momentum sequences
- Good for trend following

**Weaknesses:**
- Prone to overfitting
- Requires more data
- Slower inference

**Weight in Ensemble:** 30%

---

### 2. XGBoost Model (Feature Importance)

**Parameters:**
```python
xgb_params = {
    'objective': 'multi:softprob',
    'num_class': 3,
    'max_depth': 6,
    'learning_rate': 0.1,
    'n_estimators': 100,
    'subsample': 0.8,
    'colsample_bytree': 0.8,
    'eval_metric': 'mlogloss'
}
```

**Training:**
- **Input:** Feature vector (no sequence)
- **Validation:** 5-fold cross-validation
- **Early Stopping:** 10 rounds

**Strengths:**
- High interpretability (feature importance)
- Handles non-linear relationships
- Robust to outliers

**Weaknesses:**
- Doesn't capture sequences
- Requires feature engineering

**Weight in Ensemble:** 40% (highest - most reliable)

---

### 3. LightGBM Model (Fast Inference)

**Parameters:**
```python
lgb_params = {
    'objective': 'multiclass',
    'num_class': 3,
    'num_leaves': 31,
    'learning_rate': 0.05,
    'n_estimators': 150,
    'feature_fraction': 0.8,
    'bagging_fraction': 0.8,
    'bagging_freq': 5
}
```

**Training:**
- **Input:** Feature vector
- **Validation:** Stratified K-fold

**Strengths:**
- Very fast inference
- Memory efficient
- Good generalization

**Weaknesses:**
- Similar to XGBoost (less diversity)

**Weight in Ensemble:** 30%

---

### Ensemble Voting Logic

```python
def ensemble_predict(features):
    """
    Weighted voting with confidence calibration
    """
    # Get predictions from all models
    lstm_proba = lstm_model.predict(sequence_features)
    xgb_proba = xgb_model.predict_proba(vector_features)
    lgb_proba = lgb_model.predict_proba(vector_features)
    
    # Weighted average
    final_proba = (
        0.30 * lstm_proba +
        0.40 * xgb_proba +
        0.30 * lgb_proba
    )
    
    # Final prediction
    signal_idx = np.argmax(final_proba)
    signal = ['BUY', 'HOLD', 'SELL'][signal_idx]
    confidence = final_proba[signal_idx]
    
    # Require all models to somewhat agree
    if confidence < 0.70:
        signal = 'HOLD'  # Not confident enough
    
    return signal, confidence
```

---

## Feature Engineering

### Feature Categories

#### 1. Price-Based Features (12 features)
```python
price_features = [
    'return_1d',        # 1-day return
    'return_5d',        # 5-day return
    'return_10d',       # 10-day return
    'return_20d',       # 20-day return
    'volatility_5d',    # 5-day rolling std
    'volatility_20d',   # 20-day rolling std
    'high_low_range',   # (high - low) / close
    'close_open_change', # (close - open) / open
    'price_to_sma50',   # close / sma_50
    'price_to_sma200',  # close / sma_200
    'sma50_to_sma200',  # sma_50 / sma_200 (trend)
    'distance_to_52w_high' # (close - 52w_high) / 52w_high
]
```

#### 2. Technical Indicator Features (8 features)
```python
technical_features = [
    'rsi',              # Relative Strength Index
    'rsi_oversold',     # rsi < 30
    'rsi_overbought',   # rsi > 70
    'macd',             # MACD value
    'macd_signal',      # MACD signal line
    'macd_histogram',   # macd - macd_signal
    'macd_crossover',   # 1 if macd > signal, else 0
    'bb_position'       # (close - bb_lower) / (bb_upper - bb_lower)
]
```

#### 3. Volume Features (5 features)
```python
volume_features = [
    'volume_ratio',     # volume / volume_ma_20
    'volume_spike',     # volume > 2 * volume_ma_20
    'volume_trend',     # volume_ma_5 / volume_ma_20
    'obv',              # On-Balance Volume
    'obv_trend'         # obv_ma_5 / obv_ma_20
]
```

#### 4. Sentiment Features (10 features)
```python
sentiment_features = [
    'sentiment_score',      # Current VADER score
    'sentiment_ma_5',       # 5-day sentiment avg
    'sentiment_ma_20',      # 20-day sentiment avg
    'sentiment_trend',      # sentiment_score - sentiment_ma_5
    'sentiment_volatility', # std of sentiment over 5 days
    'mention_count',        # Number of posts
    'mention_trend',        # mention_count / mention_ma_5
    'post_engagement',      # Total score + comments
    'conviction_score',     # mention_count * abs(sentiment_score)
    'sentiment_flip'        # 1 if sentiment changed sign
]
```

#### 5. Derived Features (10 features)
```python
derived_features = [
    'momentum_score',       # Composite: RSI + MACD + Volume
    'trend_strength',       # abs(sma_50 - sma_200) / close
    'breakout_signal',      # close > bb_upper and volume_spike
    'reversal_signal',      # rsi_oversold and macd_crossover
    'sentiment_momentum',   # sentiment_trend * mention_trend
    'combined_signal',      # momentum_score * sentiment_score
    'risk_score',           # volatility_20d / abs(return_20d)
    'days_since_peak',      # Days since 52-week high
    'days_since_trough',    # Days since 52-week low
    'regime'                # Bull (1) / Bear (0) market
]
```

### Total Features: 45

---

## Backtesting Methodology

### Dataset
- **Period:** 2022-01-01 to 2024-12-31 (3 years)
- **Universe:** Top 100 stocks by Reddit mentions
- **Frequency:** Daily data
- **Validation:** Walk-forward (train on past, test on future)

### Train/Test Split
```
2022-01-01 to 2023-06-30: Training (18 months)
2023-07-01 to 2023-12-31: Validation (6 months)
2024-01-01 to 2024-12-31: Test (12 months)
```

### Simulation Parameters
```python
initial_capital = $10,000
max_positions = 5
commission = $0 (commission-free broker)
slippage = 0.1% (market impact)
```

### Walk-Forward Validation
```python
for window_start in date_range(start='2022-01', end='2024-12', freq='1M'):
    train_data = data[window_start - 18months : window_start]
    test_data = data[window_start : window_start + 1month]
    
    model.train(train_data)
    signals = model.predict(test_data)
    
    backtest_results = simulate_trades(signals, test_data)
    metrics.append(backtest_results)
```

---

## Performance Metrics

### Key Metrics to Track

#### 1. Return Metrics
```python
total_return = (final_portfolio - initial_capital) / initial_capital
annualized_return = (1 + total_return) ** (252 / trading_days) - 1
sharpe_ratio = annualized_return / annualized_volatility
sortino_ratio = annualized_return / downside_deviation
```

#### 2. Risk Metrics
```python
max_drawdown = max((peak - trough) / peak for all drawdowns)
volatility = std(daily_returns) * sqrt(252)
value_at_risk_95 = percentile(daily_returns, 5)
```

#### 3. Win/Loss Metrics
```python
win_rate = winning_trades / total_trades
avg_win = mean(winning_trade_returns)
avg_loss = mean(losing_trade_returns)
profit_factor = sum(wins) / abs(sum(losses))
```

#### 4. Trade Metrics
```python
total_trades = count(all_trades)
avg_holding_period = mean(exit_date - entry_date)
turnover = sum(trade_values) / avg_portfolio_value
```

### Target Benchmarks

| Metric | Target | Industry Benchmark |
|--------|--------|-------------------|
| **Annualized Return** | 25-40% | S&P 500: ~10% |
| **Sharpe Ratio** | 1.5+ | Good: >1.0 |
| **Max Drawdown** | <20% | Acceptable: <25% |
| **Win Rate** | 60-65% | Swing Trading: 50-60% |
| **Profit Factor** | 2.0+ | Profitable: >1.5 |
| **Avg Hold** | 3-7 days | Swing Trading Range |

---

## Edge Analysis

### What Gives Us an Edge?

#### 1. Early Sentiment Detection
**Traditional:** Institutions react to news/earnings  
**TFT Trader:** Capture Reddit momentum BEFORE mainstream attention

**Example:** GME Jan 2021 - Reddit signals days before price explosion

#### 2. Sentiment + Technical Confirmation
**Traditional:** Either sentiment OR technical  
**TFT Trader:** BOTH must align (reduces false positives)

**Result:** Higher win rate, fewer whipsaws

#### 3. Ensemble ML
**Traditional:** Single model overfits  
**TFT Trader:** 3 models with different strengths vote together

**Result:** More robust predictions, less overfitting

#### 4. Strict Risk Management
**Traditional:** Hope-based trading  
**TFT Trader:** Pre-defined stop-loss, position sizing, confidence filters

**Result:** Limited losses, capital preservation

#### 5. Swing Trading Timeframe
**Traditional Day Trading:** High frequency, high noise  
**Traditional Long-Term:** Slow gains, long holding  
**TFT Trader Swing:** Capture momentum moves (3-7 days)

**Result:** Balance between noise and opportunity

---

## Risk Factors & Limitations

### Market Risks
- **Black Swan Events:** COVID-like crashes
- **Regulatory Changes:** Trading restrictions (2021 GME halt)
- **Sentiment Manipulation:** Pump-and-dump schemes

### Model Risks
- **Overfitting:** Model trained on past may not predict future
- **Regime Change:** Bull → Bear market shifts
- **Data Quality:** Reddit data may be noisy/fake

### Execution Risks
- **Slippage:** Market orders may fill worse than expected
- **Liquidity:** Low-volume stocks hard to exit
- **Downtime:** API/system failures miss signals

### Mitigation Strategies
- Regular model retraining (weekly)
- Confidence thresholds (only trade high-probability)
- Risk limits (stop-loss, max drawdown)
- Diversification (max 5 positions)
- Manual override capability (circuit breaker)

---

**Document Version:** 1.0  
**Last Updated:** January 27, 2026  
**Maintained By:** TFT Trader Development Team
