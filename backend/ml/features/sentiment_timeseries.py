"""
Sentiment time-series feature engineering.

Generates advanced sentiment-based features including:
- Sentiment trend analysis (3-day, 7-day)
- Sentiment volatility
- Sentiment momentum
- Sentiment-price divergence
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class SentimentTimeSeriesFeatures:
    """
    Generate time-series sentiment features from historical data.
    
    Features:
    - sentiment_trend_3d: Average sentiment change over 3 days
    - sentiment_trend_7d: Average sentiment change over 7 days
    - sentiment_volatility: Standard deviation of sentiment over period
    - sentiment_momentum: Rate of change of sentiment (derivative)
    - sentiment_divergence: Divergence between sentiment momentum and price momentum
    """

    def __init__(self, window_3d: int = 3, window_7d: int = 7, volatility_window: int = 14):
        """
        Initialize sentiment feature generator.

        Args:
            window_3d: Window size for 3-day trend calculation
            window_7d: Window size for 7-day trend calculation
            volatility_window: Window size for volatility calculation
        """
        self.window_3d = window_3d
        self.window_7d = window_7d
        self.volatility_window = volatility_window

    def sentiment_trend_3d(
        self, sentiment_series: pd.Series, current_idx: int
    ) -> Optional[float]:
        """
        Calculate 3-day sentiment trend.

        Args:
            sentiment_series: Time series of sentiment scores
            current_idx: Current index in series

        Returns:
            Trend value (positive = improving, negative = deteriorating)
        """
        if current_idx < self.window_3d:
            return None

        past_idx = current_idx - self.window_3d
        past_sentiment = sentiment_series.iloc[past_idx]
        current_sentiment = sentiment_series.iloc[current_idx]

        if past_sentiment == 0:
            return 0.0

        trend = (current_sentiment - past_sentiment) / abs(past_sentiment)
        return float(trend)

    def sentiment_trend_7d(
        self, sentiment_series: pd.Series, current_idx: int
    ) -> Optional[float]:
        """
        Calculate 7-day sentiment trend.

        Args:
            sentiment_series: Time series of sentiment scores
            current_idx: Current index in series

        Returns:
            Trend value (positive = improving, negative = deteriorating)
        """
        if current_idx < self.window_7d:
            return None

        past_idx = current_idx - self.window_7d
        past_sentiment = sentiment_series.iloc[past_idx]
        current_sentiment = sentiment_series.iloc[current_idx]

        if past_sentiment == 0:
            return 0.0

        trend = (current_sentiment - past_sentiment) / abs(past_sentiment)
        return float(trend)

    def sentiment_volatility(
        self, sentiment_series: pd.Series, current_idx: int
    ) -> Optional[float]:
        """
        Calculate sentiment volatility (standard deviation).

        Args:
            sentiment_series: Time series of sentiment scores
            current_idx: Current index in series

        Returns:
            Volatility value (higher = more volatile sentiment)
        """
        if current_idx < self.volatility_window:
            return None

        start_idx = current_idx - self.volatility_window + 1
        window_data = sentiment_series.iloc[start_idx : current_idx + 1]

        volatility = float(window_data.std())
        return volatility

    def sentiment_momentum(
        self, sentiment_series: pd.Series, current_idx: int
    ) -> Optional[float]:
        """
        Calculate sentiment momentum (rate of change).

        Args:
            sentiment_series: Time series of sentiment scores
            current_idx: Current index in series

        Returns:
            Momentum value (positive = accelerating improvement)
        """
        if current_idx < 2:
            return None

        current_sentiment = sentiment_series.iloc[current_idx]
        prev_sentiment = sentiment_series.iloc[current_idx - 1]
        prev_prev_sentiment = sentiment_series.iloc[current_idx - 2]

        # First derivative
        change_1 = current_sentiment - prev_sentiment
        change_2 = prev_sentiment - prev_prev_sentiment

        # Second derivative (momentum)
        momentum = change_1 - change_2
        return float(momentum)

    def sentiment_divergence(
        self,
        sentiment_series: pd.Series,
        price_series: pd.Series,
        current_idx: int,
    ) -> Optional[float]:
        """
        Calculate sentiment-price divergence.

        Positive value = sentiment and price diverging (potential reversal)
        Negative value = sentiment and price aligned

        Args:
            sentiment_series: Time series of sentiment scores
            price_series: Time series of price values
            current_idx: Current index in series

        Returns:
            Divergence value
        """
        if current_idx < 2:
            return None

        # Calculate sentiment momentum
        sent_change = sentiment_series.iloc[current_idx] - sentiment_series.iloc[current_idx - 1]
        sent_prev_change = (
            sentiment_series.iloc[current_idx - 1]
            - sentiment_series.iloc[current_idx - 2]
        )
        sentiment_momentum = sent_change - sent_prev_change

        # Calculate price momentum
        price_change = price_series.iloc[current_idx] - price_series.iloc[current_idx - 1]
        price_prev_change = (
            price_series.iloc[current_idx - 1] - price_series.iloc[current_idx - 2]
        )
        price_momentum = price_change - price_prev_change

        # Divergence: opposite sign momentum indicates potential reversal
        if sentiment_momentum == 0 and price_momentum == 0:
            return 0.0

        # Normalize by absolute values to avoid scale issues
        sent_norm = abs(sentiment_momentum) + 1e-8
        price_norm = abs(price_momentum) + 1e-8

        # Opposite signs = positive divergence, same signs = negative divergence
        divergence = (
            -1.0
            if (sentiment_momentum * price_momentum > 0)
            else (abs(sentiment_momentum - price_momentum) / (sent_norm + price_norm))
        )
        return float(divergence)

    def batch_compute_features(
        self,
        sentiment_series: pd.Series,
        price_series: Optional[pd.Series] = None,
    ) -> Dict[str, pd.Series]:
        """
        Compute all sentiment time-series features for a series.

        Args:
            sentiment_series: Time series of sentiment scores
            price_series: Time series of price values (for divergence)

        Returns:
            Dictionary of feature series
        """
        features = {}

        # Compute each feature
        features["sentiment_trend_3d"] = pd.Series(
            [
                self.sentiment_trend_3d(sentiment_series, i)
                for i in range(len(sentiment_series))
            ]
        )

        features["sentiment_trend_7d"] = pd.Series(
            [
                self.sentiment_trend_7d(sentiment_series, i)
                for i in range(len(sentiment_series))
            ]
        )

        features["sentiment_volatility"] = pd.Series(
            [
                self.sentiment_volatility(sentiment_series, i)
                for i in range(len(sentiment_series))
            ]
        )

        features["sentiment_momentum"] = pd.Series(
            [
                self.sentiment_momentum(sentiment_series, i)
                for i in range(len(sentiment_series))
            ]
        )

        if price_series is not None:
            features["sentiment_divergence"] = pd.Series(
                [
                    self.sentiment_divergence(sentiment_series, price_series, i)
                    for i in range(len(sentiment_series))
                ]
            )

        return features


def create_sentiment_feature_engineering() -> SentimentTimeSeriesFeatures:
    """Factory function to create sentiment feature engineer."""
    return SentimentTimeSeriesFeatures(window_3d=3, window_7d=7, volatility_window=14)
