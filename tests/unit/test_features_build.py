"""
Test suite for Feature Engineering (backend/ml/features/build.py)

Tests:
  1. Feature snapshot creation
  2. Technical indicator computation
  3. Sentiment aggregation
  4. Volume trend calculation
  5. Data quality handling
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from backend.ml.features.build import FeatureBuilder


class TestFeatureBuilder:
    """Test suite for FeatureBuilder class."""

    @pytest.fixture
    def builder(self):
        """Create a FeatureBuilder instance."""
        return FeatureBuilder(
            lookback_days=30,
            sentiment_window_hours=24,
            min_volume_threshold=100000
        )

    @pytest.fixture
    def sample_stock_df(self):
        """Create sample stock price DataFrame."""
        dates = pd.date_range(start='2025-01-01', periods=30, freq='D')
        df = pd.DataFrame({
            'date': dates,
            'open': np.random.uniform(100, 150, 30),
            'high': np.random.uniform(105, 155, 30),
            'low': np.random.uniform(95, 145, 30),
            'close': np.random.uniform(100, 150, 30),
            'adjusted_close': np.random.uniform(100, 150, 30),
            'volume': np.random.randint(1000000, 5000000, 30),
            'rsi': np.random.uniform(30, 70, 30),
            'macd': np.random.uniform(-1, 1, 30),
            'macd_signal': np.random.uniform(-1, 1, 30),
            'bb_upper': np.random.uniform(110, 160, 30),
            'bb_lower': np.random.uniform(90, 140, 30),
            'sma_50': np.random.uniform(100, 150, 30),
            'sma_200': np.random.uniform(100, 150, 30),
            'volume_ratio': np.random.uniform(0.8, 1.5, 30),
        })
        return df

    def test_safe_float_conversion(self, builder):
        """Test _safe_float handles valid and invalid inputs."""
        assert builder._safe_float(42.5) == 42.5
        assert builder._safe_float("3.14") == 3.14
        assert builder._safe_float(None) is None
        assert builder._safe_float("invalid") is None

    def test_compute_technical_features(self, builder, sample_stock_df):
        """Test technical feature computation."""
        features = builder._compute_technical_features(sample_stock_df)

        # Check all keys are present
        assert "macd_histogram" in features
        assert "sma_50_200_ratio" in features
        assert "sma_crossover" in features
        assert "bb_width" in features
        assert "price_range" in features
        assert "rsi_extreme" in features

    def test_compute_sentiment_features_with_data(self, builder):
        """Test sentiment feature computation with actual sentiment scores."""
        sentiment_scores = [0.1, 0.2, 0.3, 0.4, 0.5]
        features = builder._compute_sentiment_features(sentiment_scores)

        assert features["sentiment_count"] == 5
        assert abs(features["sentiment_score"] - 0.3) < 0.01  # Mean should be 0.3
        assert features["sentiment_std"] > 0
        assert features["sentiment_trend"] in [1, -1, 0]

    def test_compute_sentiment_features_empty(self, builder):
        """Test sentiment feature computation with no data."""
        features = builder._compute_sentiment_features([])

        assert features["sentiment_score"] is None
        assert features["sentiment_count"] == 0
        assert features["sentiment_std"] is None

    def test_compute_sentiment_features_with_none_values(self, builder):
        """Test sentiment feature computation filters None values."""
        sentiment_scores = [0.1, None, 0.3, None, 0.5]
        features = builder._compute_sentiment_features(sentiment_scores)

        assert features["sentiment_count"] == 3  # Only non-None values counted
        assert abs(features["sentiment_score"] - 0.3) < 0.01

    def test_compute_volume_trend_increasing(self, builder):
        """Test volume trend detection (increasing)."""
        df = pd.DataFrame({
            'volume': [1000000] * 5 + [2000000] * 5  # Jump up in recent volume
        })
        trend = builder._compute_volume_trend(df)
        assert trend == 1  # Should detect increase

    def test_compute_volume_trend_decreasing(self, builder):
        """Test volume trend detection (decreasing)."""
        df = pd.DataFrame({
            'volume': [2000000] * 5 + [1000000] * 5  # Drop in recent volume
        })
        trend = builder._compute_volume_trend(df)
        assert trend == -1  # Should detect decrease

    def test_compute_volume_trend_flat(self, builder):
        """Test volume trend detection (flat)."""
        df = pd.DataFrame({
            'volume': [1000000] * 10  # Constant volume
        })
        trend = builder._compute_volume_trend(df)
        assert trend == 0  # Should detect no change

    def test_compute_volume_trend_insufficient_data(self, builder):
        """Test volume trend with insufficient data."""
        df = pd.DataFrame({'volume': [1000000, 2000000, 3000000]})
        trend = builder._compute_volume_trend(df)
        assert trend is None  # Not enough data

    def test_compute_features(self, builder, sample_stock_df):
        """Test complete feature computation."""
        sentiment_scores = [0.2, 0.3, 0.4, 0.5]
        
        features = builder._compute_features(
            ticker="AAPL",
            stock_history=sample_stock_df,
            sentiment_scores=sentiment_scores,
            reference_date=datetime.utcnow()
        )

        # Check all expected keys
        assert features["ticker"] == "AAPL"
        assert "close_price" in features
        assert "volume" in features
        assert "rsi" in features
        assert "macd" in features
        assert "bb_upper" in features
        assert "sentiment_score" in features
        assert "sentiment_count" in features
        assert "volume_trend" in features
        assert features["data_quality"] == "complete"

    def test_compute_features_empty_history(self, builder):
        """Test feature computation with empty stock history."""
        features = builder._compute_features(
            ticker="INVALID",
            stock_history=pd.DataFrame(),
            sentiment_scores=[],
            reference_date=datetime.utcnow()
        )

        assert features["ticker"] == "INVALID"
        assert features["data_quality"] == "insufficient_data"

    @pytest.mark.asyncio
    async def test_build_snapshot_structure(self, builder):
        """Test snapshot structure (mock database calls)."""
        with patch.object(builder, '_get_active_tickers', new_callable=AsyncMock) as mock_tickers, \
             patch.object(builder, '_fetch_stock_data', new_callable=AsyncMock) as mock_stock, \
             patch.object(builder, '_fetch_sentiment_data', new_callable=AsyncMock) as mock_sentiment:
            
            mock_tickers.return_value = ["AAPL", "MSFT"]
            mock_stock.return_value = {
                "AAPL": pd.DataFrame({'close': [150.0]}),
                "MSFT": pd.DataFrame({'close': [300.0]})
            }
            mock_sentiment.return_value = {
                "AAPL": [0.2, 0.3],
                "MSFT": [0.4, 0.5]
            }

            snapshot = await builder.build_snapshot(
                tickers=None,  # Will fetch all
                reference_date=datetime(2025, 2, 15)
            )

            # Verify snapshot structure
            assert "snapshot_id" in snapshot
            assert "timestamp" in snapshot
            assert "features" in snapshot
            assert "metadata" in snapshot
            assert len(snapshot["features"]) == 2
            assert "AAPL" in snapshot["features"]
            assert "MSFT" in snapshot["features"]

    @pytest.mark.asyncio
    async def test_build_snapshot_no_tickers(self, builder):
        """Test snapshot with no active tickers."""
        with patch.object(builder, '_get_active_tickers', new_callable=AsyncMock) as mock_tickers:
            mock_tickers.return_value = []

            snapshot = await builder.build_snapshot()

            assert "error" in snapshot["metadata"]
            assert len(snapshot["features"]) == 0


class TestFeatureIntegration:
    """Integration tests for feature engineering."""

    def test_feature_completeness(self):
        """Verify all required metrics are computed."""
        builder = FeatureBuilder()
        
        # Create sample data
        sample_df = pd.DataFrame({
            'date': pd.date_range('2025-01-01', periods=30),
            'close': np.linspace(100, 110, 30),
            'high': np.linspace(105, 115, 30),
            'low': np.linspace(95, 105, 30),
            'open': np.linspace(100, 110, 30),
            'adjusted_close': np.linspace(100, 110, 30),
            'volume': np.full(30, 1000000),
            'rsi': np.linspace(40, 60, 30),
            'macd': np.linspace(-0.5, 0.5, 30),
            'macd_signal': np.linspace(-0.4, 0.4, 30),
            'bb_upper': np.linspace(110, 120, 30),
            'bb_lower': np.linspace(90, 100, 30),
            'sma_50': np.linspace(100, 110, 30),
            'sma_200': np.linspace(95, 105, 30),
            'volume_ratio': np.full(30, 1.0),
        })

        features = builder._compute_features(
            ticker="TEST",
            stock_history=sample_df,
            sentiment_scores=[0.1, 0.2, 0.3, 0.4, 0.5],
            reference_date=datetime.utcnow()
        )

        # Required metrics from spec
        required_metrics = [
            'rsi', 'macd', 'macd_signal',
            'bb_upper', 'bb_lower',
            'sentiment_score',
            'sentiment_count',  # Ticker mentions
            'volume_ratio'
        ]

        for metric in required_metrics:
            assert metric in features, f"Missing metric: {metric}"

    def test_feature_values_in_valid_range(self):
        """Verify feature values are in expected ranges."""
        builder = FeatureBuilder()
        
        sample_df = pd.DataFrame({
            'date': pd.date_range('2025-01-01', periods=30),
            'close': np.full(30, 100.0),
            'high': np.full(30, 105.0),
            'low': np.full(30, 95.0),
            'open': np.full(30, 100.0),
            'adjusted_close': np.full(30, 100.0),
            'volume': np.full(30, 1000000),
            'rsi': np.full(30, 50.0),  # 0-100
            'macd': np.full(30, 0.1),  # Unbounded but typically -1 to 1
            'macd_signal': np.full(30, 0.1),
            'bb_upper': np.full(30, 110.0),
            'bb_lower': np.full(30, 90.0),
            'sma_50': np.full(30, 100.0),
            'sma_200': np.full(30, 100.0),
            'volume_ratio': np.full(30, 1.0),
        })

        features = builder._compute_features(
            ticker="TEST",
            stock_history=sample_df,
            sentiment_scores=[0.1, 0.2, 0.3],
            reference_date=datetime.utcnow()
        )

        # Validate ranges
        assert 0 <= features.get('rsi', 0) <= 100, "RSI should be 0-100"
        assert -1 <= features.get('sentiment_score', 0) <= 1, "Sentiment should be -1 to 1"
        assert features.get('sentiment_count', 0) >= 0, "Sentiment count should be non-negative"
        assert features.get('volume_ratio', 0) >= 0, "Volume ratio should be non-negative"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
