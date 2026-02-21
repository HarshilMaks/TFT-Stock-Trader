"""Tests for sentiment time-series feature engineering."""

import pytest
import pandas as pd
import numpy as np

from backend.ml.features.sentiment_timeseries import (
    SentimentTimeSeriesFeatures,
    create_sentiment_feature_engineering,
)


class TestSentimentTrendFeatures:
    """Test sentiment trend calculations."""

    @pytest.fixture
    def features(self):
        """Create feature engineer."""
        return SentimentTimeSeriesFeatures()

    @pytest.fixture
    def sentiment_series(self):
        """Create sample sentiment series."""
        return pd.Series([0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0])

    def test_sentiment_trend_3d(self, features, sentiment_series):
        """Test 3-day sentiment trend calculation."""
        # At index 3: (0.6 - 0.3) / 0.3 = 1.0 (100% improvement)
        trend = features.sentiment_trend_3d(sentiment_series, 3)
        assert trend is not None
        assert abs(trend - 1.0) < 0.01

    def test_sentiment_trend_3d_insufficient_history(self, features, sentiment_series):
        """Test that trend returns None with insufficient history."""
        trend = features.sentiment_trend_3d(sentiment_series, 1)
        assert trend is None

    def test_sentiment_trend_7d(self, features, sentiment_series):
        """Test 7-day sentiment trend calculation."""
        # At index 7: (1.0 - 0.3) / 0.3 = 2.33 (233% improvement)
        trend = features.sentiment_trend_7d(sentiment_series, 7)
        assert trend is not None
        assert abs(trend - 2.33) < 0.1

    def test_sentiment_trend_negative(self, features):
        """Test negative sentiment trend."""
        declining_series = pd.Series([1.0, 0.9, 0.8, 0.7, 0.6])
        trend = features.sentiment_trend_3d(declining_series, 3)
        assert trend is not None
        assert trend < 0  # Negative trend

    def test_sentiment_trend_zero_handling(self, features):
        """Test handling of zero sentiment values."""
        series_with_zero = pd.Series([0.0, 0.1, 0.2, 0.3, 0.4])
        trend = features.sentiment_trend_3d(series_with_zero, 3)
        assert trend == 0.0  # Should return 0 when dividing by zero


class TestSentimentVolatility:
    """Test sentiment volatility calculations."""

    @pytest.fixture
    def features(self):
        return SentimentTimeSeriesFeatures()

    def test_sentiment_volatility_stable(self, features):
        """Test volatility for stable sentiment."""
        stable_series = pd.Series([0.5] * 20)
        volatility = features.sentiment_volatility(stable_series, 19)
        assert volatility is not None
        assert abs(volatility) < 0.01  # Zero or near-zero volatility

    def test_sentiment_volatility_volatile(self, features):
        """Test volatility for volatile sentiment."""
        volatile_series = pd.Series([0.1, 0.9, 0.1, 0.9, 0.1, 0.9] * 3)
        volatility = features.sentiment_volatility(volatile_series, len(volatile_series) - 1)
        assert volatility is not None
        assert volatility > 0.3  # High volatility

    def test_sentiment_volatility_insufficient_history(self, features):
        """Test that volatility returns None with insufficient history."""
        series = pd.Series([0.5, 0.6, 0.7])
        volatility = features.sentiment_volatility(series, 1)
        assert volatility is None

    def test_sentiment_volatility_trending(self, features):
        """Test volatility for trending sentiment."""
        trending_series = pd.Series(np.linspace(0.1, 1.0, 20))
        volatility = features.sentiment_volatility(trending_series, 19)
        assert volatility is not None
        assert volatility > 0  # Non-zero volatility from trend


class TestSentimentMomentum:
    """Test sentiment momentum calculation."""

    @pytest.fixture
    def features(self):
        return SentimentTimeSeriesFeatures()

    def test_sentiment_momentum_accelerating(self, features):
        """Test momentum for accelerating sentiment."""
        series = pd.Series([0.1, 0.2, 0.4, 0.7, 1.0])
        # At index 4: changes are [0.1, 0.2, 0.3]
        # Momentum = 0.3 - 0.2 = 0.1 (positive acceleration)
        momentum = features.sentiment_momentum(series, 4)
        assert momentum is not None
        assert momentum > 0

    def test_sentiment_momentum_decelerating(self, features):
        """Test momentum for decelerating sentiment."""
        series = pd.Series([0.1, 0.5, 0.8, 0.95, 1.0])
        # Changes decrease: [0.4, 0.3, 0.15]
        # Momentum should be negative
        momentum = features.sentiment_momentum(series, 4)
        assert momentum is not None
        assert momentum < 0

    def test_sentiment_momentum_insufficient_history(self, features):
        """Test that momentum returns None with insufficient history."""
        series = pd.Series([0.1, 0.2])
        momentum = features.sentiment_momentum(series, 0)
        assert momentum is None


class TestSentimentDivergence:
    """Test sentiment-price divergence calculation."""

    @pytest.fixture
    def features(self):
        return SentimentTimeSeriesFeatures()

    def test_divergence_aligned_trending(self, features):
        """Test divergence when sentiment and price trend together."""
        sentiment = pd.Series([0.2, 0.4, 0.6, 0.8, 1.0])
        price = pd.Series([100, 110, 120, 130, 140])

        divergence = features.sentiment_divergence(sentiment, price, 4)
        assert divergence is not None
        # Both trending up = aligned = negative divergence (allowing for floating point error)
        assert divergence <= 0.01

    def test_divergence_opposing_trends(self, features):
        """Test divergence when sentiment and price diverge."""
        sentiment = pd.Series([1.0, 0.9, 0.8, 0.7, 0.6])  # Down
        price = pd.Series([100, 110, 120, 130, 140])  # Up

        divergence = features.sentiment_divergence(sentiment, price, 4)
        assert divergence is not None
        # Opposite trends = divergence
        assert divergence > 0

    def test_divergence_insufficient_history(self, features):
        """Test divergence with insufficient history."""
        sentiment = pd.Series([0.5, 0.6])
        price = pd.Series([100, 105])

        divergence = features.sentiment_divergence(sentiment, price, 0)
        assert divergence is None

    def test_divergence_zero_momentum(self, features):
        """Test divergence with zero momentum."""
        sentiment = pd.Series([0.5, 0.5, 0.5, 0.5, 0.5])
        price = pd.Series([100, 100, 100, 100, 100])

        divergence = features.sentiment_divergence(sentiment, price, 4)
        assert divergence is not None
        assert divergence == 0.0


class TestBatchComputation:
    """Test batch feature computation."""

    @pytest.fixture
    def features(self):
        return SentimentTimeSeriesFeatures()

    def test_batch_compute_all_features(self, features):
        """Test computing all features in batch."""
        sentiment = pd.Series(np.linspace(0.2, 1.0, 30))
        price = pd.Series(np.linspace(100, 150, 30))

        feature_dict = features.batch_compute_features(sentiment, price)

        assert "sentiment_trend_3d" in feature_dict
        assert "sentiment_trend_7d" in feature_dict
        assert "sentiment_volatility" in feature_dict
        assert "sentiment_momentum" in feature_dict
        assert "sentiment_divergence" in feature_dict

        # All should have same length as input
        for f_series in feature_dict.values():
            assert len(f_series) == len(sentiment)

    def test_batch_compute_without_price(self, features):
        """Test batch computation without price data."""
        sentiment = pd.Series(np.linspace(0.2, 1.0, 30))

        feature_dict = features.batch_compute_features(sentiment)

        assert "sentiment_trend_3d" in feature_dict
        assert "sentiment_trend_7d" in feature_dict
        assert "sentiment_volatility" in feature_dict
        assert "sentiment_momentum" in feature_dict
        assert "sentiment_divergence" not in feature_dict


class TestFactoryFunction:
    """Test factory function."""

    def test_create_feature_engineering(self):
        """Test creating feature engineer via factory."""
        engineer = create_sentiment_feature_engineering()

        assert engineer is not None
        assert isinstance(engineer, SentimentTimeSeriesFeatures)
        assert engineer.window_3d == 3
        assert engineer.window_7d == 7
        assert engineer.volatility_window == 14


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.fixture
    def features(self):
        return SentimentTimeSeriesFeatures()

    def test_empty_series(self, features):
        """Test with empty series."""
        empty = pd.Series([], dtype=float)
        volatility = features.sentiment_volatility(empty, 0)
        assert volatility is None

    def test_single_value_series(self, features):
        """Test with single value series."""
        single = pd.Series([0.5])
        trend = features.sentiment_trend_3d(single, 0)
        assert trend is None

    def test_large_series(self, features):
        """Test with large series."""
        large = pd.Series(np.random.uniform(0, 1, 1000))
        volatility = features.sentiment_volatility(large, 999)
        assert volatility is not None
        assert 0 <= volatility <= 1

    def test_negative_sentiment_values(self, features):
        """Test handling negative sentiment values (unexpected but possible)."""
        series = pd.Series([-0.5, -0.3, -0.1, 0.1, 0.3])
        trend = features.sentiment_trend_3d(series, 3)
        assert trend is not None
