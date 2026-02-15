"""
Feature Engineering Pipeline for TFT Trader

Task #5: Build Features from Real Data
========================================

Input:
  - Real Reddit posts (sentiment scores, ticker mentions)
  - Stock prices (OHLCV, volume, dates)
  - Technical indicators (RSI, MACD, Bollinger Bands)

Output:
  - Engineered features snapshot with snapshot_id
  - Metrics: RSI, MACD, Bollinger Bands, sentiment, ticker counts, volume ratio
  - Aggregated per ticker + timestamp

Metrics Computed:
  1. RSI (14-day) - Momentum indicator
  2. MACD (12/26/9) - Trend following
  3. Bollinger Bands (20-day, 2σ) - Volatility
  4. Sentiment Score - Average sentiment from Reddit posts
  5. Ticker Count - Number of Reddit mentions
  6. Volume Ratio - Current volume / 20-day average
  7. SMA Crossover - 50/200 day MA signal
  8. MACD Histogram - Momentum divergence
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from uuid import uuid4

import pandas as pd
import numpy as np
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

# Import models
from backend.models.stock import StockPrice
from backend.models.reddit import RedditPost
from backend.database.config import AsyncSessionLocal

logger = logging.getLogger(__name__)


class FeatureBuilder:
    """
    Build engineered features from raw market and sentiment data.
    
    Workflow:
      1. Fetch latest stock prices for all tickers
      2. Fetch Reddit posts within time window
      3. Aggregate sentiment per ticker
      4. Calculate technical indicators (from stored values)
      5. Combine into feature snapshot
    """

    def __init__(
        self,
        lookback_days: int = 30,
        sentiment_window_hours: int = 24,
        min_volume_threshold: int = 100000
    ):
        """
        Initialize feature builder.
        
        Args:
            lookback_days: Days of historical data for indicators
            sentiment_window_hours: Hours to look back for Reddit sentiment
            min_volume_threshold: Minimum volume to consider stock liquid
        """
        self.lookback_days = lookback_days
        self.sentiment_window_hours = sentiment_window_hours
        self.min_volume_threshold = min_volume_threshold

    async def build_snapshot(
        self,
        tickers: Optional[List[str]] = None,
        reference_date: Optional[datetime] = None,
        session: Optional[AsyncSession] = None
    ) -> Dict:
        """
        Build a complete feature snapshot for given tickers.
        
        Args:
            tickers: List of tickers to build features for (if None, use all in DB)
            reference_date: Date to build features as of (default: today)
            session: Database session (creates new if None)
            
        Returns:
            Dict with:
              - snapshot_id: Unique identifier for this feature snapshot
              - timestamp: When snapshot was created
              - features: Dict of ticker -> features
              - metadata: Data quality metrics
        """
        if session is None:
            session = AsyncSessionLocal()

        try:
            reference_date = reference_date or datetime.utcnow()
            snapshot_id = str(uuid4())
            
            logger.info(f"Building feature snapshot {snapshot_id} for {reference_date.date()}")

            # Get tickers if not provided
            if tickers is None:
                tickers = await self._get_active_tickers(session)
            
            if not tickers:
                logger.warning("No active tickers found")
                return {
                    "snapshot_id": snapshot_id,
                    "timestamp": reference_date,
                    "features": {},
                    "metadata": {"error": "No active tickers"}
                }

            # Fetch data for all tickers
            stock_data = await self._fetch_stock_data(
                session, tickers, reference_date
            )
            
            sentiment_data = await self._fetch_sentiment_data(
                session, tickers, reference_date
            )

            # Build features per ticker
            features = {}
            for ticker in tickers:
                try:
                    ticker_features = self._compute_features(
                        ticker=ticker,
                        stock_history=stock_data.get(ticker, pd.DataFrame()),
                        sentiment_scores=sentiment_data.get(ticker, []),
                        reference_date=reference_date
                    )
                    features[ticker] = ticker_features
                except Exception as e:
                    logger.error(f"Failed to build features for {ticker}: {e}")
                    features[ticker] = {"error": str(e)}

            return {
                "snapshot_id": snapshot_id,
                "timestamp": reference_date,
                "features": features,
                "metadata": {
                    "tickers_processed": len(features),
                    "reference_date": reference_date.isoformat(),
                    "lookback_days": self.lookback_days,
                    "feature_version": "1.0"
                }
            }

        finally:
            await session.close()

    async def _get_active_tickers(self, session: AsyncSession) -> List[str]:
        """Get list of tickers with recent price data."""
        cutoff_date = datetime.utcnow() - timedelta(days=5)
        
        stmt = select(StockPrice.ticker).where(
            StockPrice.date >= cutoff_date
        ).distinct()
        
        result = await session.execute(stmt)
        tickers = [row[0] for row in result.fetchall()]
        return sorted(set(tickers))

    async def _fetch_stock_data(
        self,
        session: AsyncSession,
        tickers: List[str],
        reference_date: datetime
    ) -> Dict[str, pd.DataFrame]:
        """
        Fetch historical stock price data for lookback period.
        
        Returns:
            Dict mapping ticker -> DataFrame with columns:
              [date, open, high, low, close, adjusted_close, volume,
               rsi, macd, macd_signal, bb_upper, bb_lower, sma_50, sma_200, volume_ratio]
        """
        lookback_start = reference_date - timedelta(days=self.lookback_days)
        
        stmt = select(StockPrice).where(
            and_(
                StockPrice.ticker.in_(tickers),
                StockPrice.date >= lookback_start,
                StockPrice.date <= reference_date
            )
        ).order_by(StockPrice.ticker, StockPrice.date)
        
        result = await session.execute(stmt)
        rows = result.fetchall()

        # Group by ticker
        stock_data = {}
        for ticker in tickers:
            ticker_rows = [
                row for row in rows 
                if row[0].ticker == ticker  # row[0] is the StockPrice object
            ]
            
            if ticker_rows:
                df = pd.DataFrame([
                    {
                        'date': row[0].date,
                        'open': row[0].open_price,
                        'high': row[0].high,
                        'low': row[0].low,
                        'close': row[0].close,
                        'adjusted_close': row[0].adjusted_close,
                        'volume': row[0].volume,
                        'rsi': row[0].rsi,
                        'macd': row[0].macd,
                        'macd_signal': row[0].macd_signal,
                        'bb_upper': row[0].bb_upper,
                        'bb_lower': row[0].bb_lower,
                        'sma_50': row[0].sma_50,
                        'sma_200': row[0].sma_200,
                        'volume_ratio': row[0].volume_ratio,
                    }
                    for row in ticker_rows
                ])
                df['date'] = pd.to_datetime(df['date'])
                stock_data[ticker] = df.sort_values('date').reset_index(drop=True)
            else:
                stock_data[ticker] = pd.DataFrame()

        return stock_data

    async def _fetch_sentiment_data(
        self,
        session: AsyncSession,
        tickers: List[str],
        reference_date: datetime
    ) -> Dict[str, List[float]]:
        """
        Fetch sentiment scores from Reddit posts within time window.
        
        Returns:
            Dict mapping ticker -> list of sentiment scores
        """
        lookback_time = reference_date - timedelta(hours=self.sentiment_window_hours)
        
        stmt = select(RedditPost).where(
            and_(
                RedditPost.created_at >= lookback_time,
                RedditPost.created_at <= reference_date
            )
        )
        
        result = await session.execute(stmt)
        posts = result.fetchall()

        # Aggregate sentiment by ticker
        sentiment_data = {ticker: [] for ticker in tickers}
        
        for row in posts:
            post = row[0]  # Extract RedditPost object
            if post.sentiment_score is not None:
                # Post mentions multiple tickers
                post_tickers = post.tickers or []
                for ticker in post_tickers:
                    if ticker in tickers:
                        try:
                            sentiment_val = float(post.sentiment_score)
                            sentiment_data[ticker].append(sentiment_val)
                        except (ValueError, TypeError):
                            pass

        return sentiment_data

    def _compute_features(
        self,
        ticker: str,
        stock_history: pd.DataFrame,
        sentiment_scores: List[float],
        reference_date: datetime
    ) -> Dict:
        """
        Compute all engineered features for a ticker.
        
        Args:
            ticker: Stock ticker symbol
            stock_history: DataFrame with price history
            sentiment_scores: List of sentiment values from posts
            reference_date: Reference date for features
            
        Returns:
            Dict with all feature values
        """
        features = {
            "ticker": ticker,
            "reference_date": reference_date.isoformat(),
        }

        if stock_history.empty:
            features["data_quality"] = "insufficient_data"
            logger.warning(f"No stock data for {ticker}")
            return features

        # Latest price and OHLCV
        latest = stock_history.iloc[-1]
        features["close_price"] = float(latest['close'])
        features["volume"] = int(latest['volume'])
        features["high"] = float(latest['high'])
        features["low"] = float(latest['low'])
        features["date"] = latest['date'].isoformat()

        # Technical Indicators (from stored values)
        features["rsi"] = self._safe_float(latest['rsi'])
        features["macd"] = self._safe_float(latest['macd'])
        features["macd_signal"] = self._safe_float(latest['macd_signal'])
        features["bb_upper"] = self._safe_float(latest['bb_upper'])
        features["bb_lower"] = self._safe_float(latest['bb_lower'])
        features["sma_50"] = self._safe_float(latest['sma_50'])
        features["sma_200"] = self._safe_float(latest['sma_200'])
        features["volume_ratio"] = self._safe_float(latest['volume_ratio'])

        # Derived Technical Features
        features.update(self._compute_technical_features(stock_history))

        # Sentiment Features
        features.update(self._compute_sentiment_features(sentiment_scores))

        # Volume Features
        features["volume_trend"] = self._compute_volume_trend(stock_history)

        # Data Quality
        features["data_quality"] = "complete" if not features.get("data_quality") else "incomplete"

        return features

    def _compute_technical_features(self, df: pd.DataFrame) -> Dict:
        """Compute derived technical indicator features."""
        features = {}

        if df.empty:
            return features

        try:
            latest = df.iloc[-1]
            
            # MACD Histogram (momentum divergence)
            if pd.notna(latest['macd']) and pd.notna(latest['macd_signal']):
                features["macd_histogram"] = float(latest['macd'] - latest['macd_signal'])
            else:
                features["macd_histogram"] = None

            # SMA Crossover Signal (50/200 MA)
            if pd.notna(latest['sma_50']) and pd.notna(latest['sma_200']):
                features["sma_50_200_ratio"] = float(latest['sma_50'] / latest['sma_200']) if latest['sma_200'] > 0 else None
                features["sma_crossover"] = 1 if latest['sma_50'] > latest['sma_200'] else -1
            else:
                features["sma_50_200_ratio"] = None
                features["sma_crossover"] = None

            # Bollinger Bands Squeeze (upper - lower)
            if pd.notna(latest['bb_upper']) and pd.notna(latest['bb_lower']):
                features["bb_width"] = float(latest['bb_upper'] - latest['bb_lower'])
                features["close_to_bb_mid"] = float(
                    (latest['close'] - (latest['bb_upper'] + latest['bb_lower']) / 2) 
                    / (latest['bb_upper'] - latest['bb_lower'])
                ) if features["bb_width"] > 0 else None
            else:
                features["bb_width"] = None
                features["close_to_bb_mid"] = None

            # Price Range (high - low)
            features["price_range"] = float(latest['high'] - latest['low'])

            # RSI Extremes (overbought > 70, oversold < 30)
            if pd.notna(latest['rsi']):
                features["rsi_extreme"] = (
                    1 if latest['rsi'] > 70 else (-1 if latest['rsi'] < 30 else 0)
                )
            else:
                features["rsi_extreme"] = None

        except Exception as e:
            logger.warning(f"Error computing technical features: {e}")

        return features

    def _compute_sentiment_features(self, sentiment_scores: List[float]) -> Dict:
        """Compute aggregate sentiment features."""
        features = {}

        if not sentiment_scores:
            features["sentiment_score"] = None
            features["sentiment_count"] = 0
            features["sentiment_std"] = None
            features["sentiment_trend"] = None
            return features

        scores = [s for s in sentiment_scores if s is not None]
        
        if not scores:
            features["sentiment_score"] = None
            features["sentiment_count"] = 0
            features["sentiment_std"] = None
            features["sentiment_trend"] = None
            return features

        features["sentiment_score"] = float(np.mean(scores))
        features["sentiment_count"] = len(scores)
        features["sentiment_std"] = float(np.std(scores)) if len(scores) > 1 else 0.0
        
        # Sentiment trend (positive if most recent posts are more positive)
        if len(scores) >= 2:
            recent_half = scores[len(scores)//2:]
            older_half = scores[:len(scores)//2]
            recent_mean = np.mean(recent_half)
            older_mean = np.mean(older_half)
            features["sentiment_trend"] = 1 if recent_mean > older_mean else (-1 if recent_mean < older_mean else 0)
        else:
            features["sentiment_trend"] = None

        return features

    def _compute_volume_trend(self, df: pd.DataFrame) -> Optional[int]:
        """Compute volume trend (1 = increasing, -1 = decreasing, 0 = flat)."""
        if df.empty or len(df) < 5:
            return None

        try:
            # Compare recent 5-day avg to prior 5-day avg
            recent_vol = df['volume'].tail(5).mean()
            prior_vol = df['volume'].iloc[-10:-5].mean()
            
            if recent_vol > prior_vol * 1.1:
                return 1  # Volume increasing
            elif recent_vol < prior_vol * 0.9:
                return -1  # Volume decreasing
            else:
                return 0  # Flat
        except Exception as e:
            logger.warning(f"Error computing volume trend: {e}")
            return None

    @staticmethod
    def _safe_float(value) -> Optional[float]:
        """Safely convert value to float, returning None if invalid."""
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    async def save_snapshot(
        self,
        snapshot: Dict,
        session: AsyncSession
    ) -> str:
        """
        Persist feature snapshot to database.
        
        Args:
            snapshot: Dict returned from build_snapshot()
            session: Database session
            
        Returns:
            snapshot_id for tracking
        """
        try:
            # Import here to avoid circular imports
            from backend.models.feature_snapshot import FeatureSnapshot
            
            snapshot_id = snapshot["snapshot_id"]
            reference_date = snapshot["timestamp"]
            
            for ticker, features in snapshot["features"].items():
                if "error" in features:
                    # Store error state
                    fs = FeatureSnapshot(
                        snapshot_id=snapshot_id,
                        ticker=ticker,
                        reference_date=reference_date,
                        features_json={},
                        data_quality="error",
                        error_message=features.get("error")
                    )
                else:
                    # Store features
                    fs = FeatureSnapshot(
                        snapshot_id=snapshot_id,
                        ticker=ticker,
                        reference_date=reference_date,
                        features_json=features,
                        data_quality=features.get("data_quality", "complete")
                    )
                
                session.add(fs)
            
            await session.commit()
            logger.info(f"Saved feature snapshot {snapshot_id} with {len(snapshot['features'])} tickers")
            return snapshot_id
            
        except Exception as e:
            logger.error(f"Failed to save snapshot: {e}")
            await session.rollback()
            raise


async def build_features_snapshot(
    tickers: Optional[List[str]] = None,
    reference_date: Optional[datetime] = None,
) -> Dict:
    """
    Convenience function to build a feature snapshot.
    
    Usage:
        snapshot = await build_features_snapshot(
            tickers=["AAPL", "MSFT", "TSLA"],
            reference_date=datetime(2025, 2, 15)
        )
        
        # Access features
        aapl_features = snapshot["features"]["AAPL"]
        print(f"AAPL RSI: {aapl_features['rsi']}")
        print(f"AAPL Sentiment: {aapl_features['sentiment_score']}")
    """
    builder = FeatureBuilder()
    return await builder.build_snapshot(
        tickers=tickers,
        reference_date=reference_date
    )


if __name__ == "__main__":
    # Example: Run feature engineering
    import asyncio
    
    async def main():
        snapshot = await build_features_snapshot(
            tickers=["AAPL", "MSFT", "NVDA"],
        )
        
        print(f"\n✅ Feature Snapshot: {snapshot['snapshot_id']}")
        print(f"   Timestamp: {snapshot['timestamp']}")
        print(f"   Tickers: {len(snapshot['features'])}")
        print()
        
        for ticker, features in snapshot["features"].items():
            if "error" not in features:
                print(f"\n{ticker}:")
                print(f"  Close: ${features.get('close_price'):.2f}")
                print(f"  RSI: {features.get('rsi'):.2f}")
                print(f"  MACD: {features.get('macd'):.4f}")
                print(f"  Sentiment: {features.get('sentiment_score'):.4f}")
                print(f"  Sentiment Count: {features.get('sentiment_count')}")
                print(f"  Volume Ratio: {features.get('volume_ratio'):.2f}")

    asyncio.run(main())
