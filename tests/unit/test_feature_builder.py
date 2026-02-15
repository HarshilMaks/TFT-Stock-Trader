"""
Unit Tests for Feature Engineering Pipeline

Tests for:
- Feature computation (metrics calculations)
- Edge cases (missing data, empty data)
- Sentiment aggregation
- Technical feature derivations
- Database persistence
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from backend.ml.features.build import FeatureBuilder
from backend.ml.features.sequences import SequenceBuilder


class TestFeatureBuilder:
    """Test FeatureBuilder metric computations."""
    
    @pytest.fixture
    def feature_builder(self):
        return FeatureBuilder(lookback_days=30, sentiment_window_hours=24)
    
    def test_safe_float_valid_values(self, feature_builder):
        """Test _safe_float with valid inputs."""
        assert feature_builder._safe_float(1.5) == 1.5
        assert feature_builder._safe_float(0) == 0.0
        assert feature_builder._safe_float(-10.5) == -10.5
        assert feature_builder._safe_float("3.14") == 3.14
    
    def test_safe_float_invalid_values(self, feature_builder):
        """Test _safe_float with invalid inputs."""
        assert feature_builder._safe_float(None) is None
        assert feature_builder._safe_float("invalid") is None
        # np.nan converts to float, so it becomes (nan) which is float
        result = feature_builder._safe_float(np.nan)
        assert result is None or np.isnan(result)
    
    def test_compute_sentiment_features_complete(self, feature_builder):
        """Test sentiment feature computation with complete data."""
        sentiment_scores = [0.5, 0.6, 0.7, 0.8]
        
        features = feature_builder._compute_sentiment_features(sentiment_scores)
        
        assert features["sentiment_score"] == pytest.approx(0.65, abs=0.01)
        assert features["sentiment_count"] == 4
        assert features["sentiment_std"] > 0
        assert features["sentiment_trend"] in [1, -1, 0]
    
    def test_compute_sentiment_features_empty(self, feature_builder):
        """Test sentiment features with no data."""
        features = feature_builder._compute_sentiment_features([])
        
        assert features["sentiment_score"] is None
        assert features["sentiment_count"] == 0
        assert features["sentiment_std"] is None
        assert features["sentiment_trend"] is None
    
    def test_compute_sentiment_features_single(self, feature_builder):
        """Test sentiment features with single value."""
        features = feature_builder._compute_sentiment_features([0.5])
        
        assert features["sentiment_score"] == 0.5
        assert features["sentiment_count"] == 1
        assert features["sentiment_std"] == 0.0
    
    def test_compute_technical_features_rsi_extreme(self, feature_builder):
        """Test RSI extreme detection."""
        df_high = pd.DataFrame({
            'rsi': [75],
            'macd': [1.0],
            'macd_signal': [0.9],
            'sma_50': [150],
            'sma_200': [140],
            'bb_upper': [160],
            'bb_lower': [140],
            'close': [155],
            'high': [160],
            'low': [150],
            'volume': [1000000]
        })
        
        features = feature_builder._compute_technical_features(df_high)
        assert features["rsi_extreme"] == 1  # Overbought
        
        df_low = pd.DataFrame({
            'rsi': [25],
            'macd': [1.0],
            'macd_signal': [0.9],
            'sma_50': [150],
            'sma_200': [160],
            'bb_upper': [160],
            'bb_lower': [140],
            'close': [145],
            'high': [150],
            'low': [140],
            'volume': [500000]
        })
        
        features = feature_builder._compute_technical_features(df_low)
        assert features["rsi_extreme"] == -1  # Oversold
    
    def test_compute_technical_features_ma_crossover(self, feature_builder):
        """Test SMA crossover detection."""
        df_golden = pd.DataFrame({
            'sma_50': [155],
            'sma_200': [150],
            'macd': [1.0],
            'macd_signal': [0.9],
            'bb_upper': [160],
            'bb_lower': [140],
            'close': [155],
            'rsi': [55],
            'high': [160],
            'low': [150],
            'volume': [1000000]
        })
        
        features = feature_builder._compute_technical_features(df_golden)
        assert features["sma_crossover"] == 1  # Golden cross (SMA50 > SMA200)
        assert features["sma_50_200_ratio"] == pytest.approx(1.0333, abs=0.001)
        
        df_death = pd.DataFrame({
            'sma_50': [145],
            'sma_200': [150],
            'macd': [1.0],
            'macd_signal': [0.9],
            'bb_upper': [160],
            'bb_lower': [140],
            'close': [145],
            'rsi': [45],
            'high': [150],
            'low': [140],
            'volume': [500000]
        })
        
        features = feature_builder._compute_technical_features(df_death)
        assert features["sma_crossover"] == -1  # Death cross
    
    def test_compute_technical_features_macd_histogram(self, feature_builder):
        """Test MACD histogram calculation."""
        df = pd.DataFrame({
            'macd': [1.5],
            'macd_signal': [1.2],
            'sma_50': [150],
            'sma_200': [150],
            'bb_upper': [160],
            'bb_lower': [140],
            'close': [150],
            'rsi': [50],
            'high': [160],
            'low': [140],
            'volume': [1000000]
        })
        
        features = feature_builder._compute_technical_features(df)
        assert features["macd_histogram"] == pytest.approx(0.3, abs=0.001)
    
    def test_compute_volume_trend_increasing(self, feature_builder):
        """Test volume trend detection - increasing."""
        df = pd.DataFrame({
            'volume': [100000, 100000, 100000, 100000, 100000,
                       120000, 120000, 120000, 120000, 120000]
        })
        
        trend = feature_builder._compute_volume_trend(df)
        assert trend == 1  # Increasing
    
    def test_compute_volume_trend_decreasing(self, feature_builder):
        """Test volume trend detection - decreasing."""
        df = pd.DataFrame({
            'volume': [120000, 120000, 120000, 120000, 120000,
                       100000, 100000, 100000, 100000, 100000]
        })
        
        trend = feature_builder._compute_volume_trend(df)
        assert trend == -1  # Decreasing
    
    def test_compute_volume_trend_flat(self, feature_builder):
        """Test volume trend detection - flat."""
        df = pd.DataFrame({
            'volume': [100000] * 10
        })
        
        trend = feature_builder._compute_volume_trend(df)
        assert trend == 0  # Flat
    
    def test_compute_volume_trend_insufficient_data(self, feature_builder):
        """Test volume trend with insufficient data."""
        df = pd.DataFrame({'volume': [100000]})
        trend = feature_builder._compute_volume_trend(df)
        assert trend is None
    
    def test_compute_features_empty_dataframe(self, feature_builder):
        """Test feature computation with empty stock data."""
        features = feature_builder._compute_features(
            ticker="TEST",
            stock_history=pd.DataFrame(),
            sentiment_scores=[0.5],
            reference_date=datetime.now()
        )
        
        assert features["ticker"] == "TEST"
        assert features["data_quality"] == "insufficient_data"
    
    @pytest.mark.asyncio
    async def test_save_snapshot_valid(self, feature_builder):
        """Test saving snapshot to database."""
        snapshot = {
            "snapshot_id": str(uuid4()),
            "timestamp": datetime.now(),
            "features": {
                "AAPL": {
                    "rsi": 55.5,
                    "sentiment_score": 0.65,
                    "data_quality": "complete"
                },
                "MSFT": {
                    "rsi": 60.0,
                    "sentiment_score": 0.70,
                    "data_quality": "complete"
                }
            },
            "metadata": {}
        }
        
        mock_session = AsyncMock()
        
        result = await feature_builder.save_snapshot(snapshot, mock_session)
        
        assert result == snapshot["snapshot_id"]
        assert mock_session.add.call_count == 2  # Two tickers
        assert mock_session.commit.called


class TestSequenceBuilder:
    """Test SequenceBuilder for temporal sequences."""
    
    @pytest.fixture
    def sequence_builder(self):
        return SequenceBuilder(window_size=30, step_size=1)
    
    def test_default_features_defined(self, sequence_builder):
        """Test that default features are defined."""
        assert len(sequence_builder.DEFAULT_FEATURES) > 0
        assert "rsi" in sequence_builder.DEFAULT_FEATURES
        assert "sentiment_score" in sequence_builder.DEFAULT_FEATURES
        assert "macd" in sequence_builder.DEFAULT_FEATURES
    
    def test_forward_fill_nans(self, sequence_builder):
        """Test NaN forward filling."""
        arr = np.array([
            [1.0, 2.0],
            [np.nan, 3.0],
            [4.0, np.nan]
        ])
        
        filled = SequenceBuilder._forward_fill_nans(arr)
        
        assert filled[1, 0] == 1.0  # Forward filled from previous row
        assert filled[2, 1] == 3.0  # Forward filled from previous row
    
    def test_create_sequence_complete(self, sequence_builder):
        """Test sequence creation with complete data."""
        window_data = pd.DataFrame({
            'rsi': np.linspace(30, 70, 30),
            'macd': np.linspace(-1, 1, 30),
            'sentiment_score': np.ones(30) * 0.5,
            'volume': np.ones(30) * 1000000
        })
        
        features = ['rsi', 'macd', 'sentiment_score', 'volume']
        sequence = sequence_builder._create_sequence(window_data, features)
        
        assert sequence is not None
        assert sequence.shape == (30, 4)
        assert sequence.dtype == np.float32
    
    def test_create_sequence_missing_features(self, sequence_builder):
        """Test sequence creation when features don't exist."""
        window_data = pd.DataFrame({
            'rsi': np.linspace(30, 70, 30),
            'macd': np.linspace(-1, 1, 30)
        })
        
        features = ['rsi', 'macd', 'nonexistent_feature']
        sequence = sequence_builder._create_sequence(window_data, features)
        
        # Should still work, just with fewer features
        assert sequence is not None
        assert sequence.shape[1] == 2  # Only 2 features available
    
    def test_create_sequence_with_nans_no_fill(self):
        """Test sequence creation with NaNs when filling is disabled."""
        builder = SequenceBuilder(fill_missing=False)
        window_data = pd.DataFrame({
            'rsi': [50.0, np.nan, 55.0] + [60.0] * 27,
            'macd': np.ones(30)
        })
        
        features = ['rsi', 'macd']
        sequence = builder._create_sequence(window_data, features)
        
        assert sequence is None  # Should skip due to NaNs


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
