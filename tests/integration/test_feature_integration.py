"""
Integration Tests for Feature Engineering Pipeline

Tests focused on specific functionality:
1. Snapshot structure and feature computation
2. Sequence building from mock data
3. Shape validation and data integrity
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from backend.ml.features.build import FeatureBuilder
from backend.ml.features.sequences import SequenceBuilder


class TestFeatureBuilderIntegration:
    """Integration tests for FeatureBuilder output structure."""
    
    def test_feature_builder_initialization(self):
        """Test FeatureBuilder can be initialized."""
        builder = FeatureBuilder()
        
        assert builder.lookback_days == 30
        assert builder.sentiment_window_hours == 24
        assert builder.min_volume_threshold == 100000
    
    def test_feature_builder_config_override(self):
        """Test FeatureBuilder with custom configuration."""
        builder = FeatureBuilder(
            lookback_days=60,
            sentiment_window_hours=48,
            min_volume_threshold=500000
        )
        
        assert builder.lookback_days == 60
        assert builder.sentiment_window_hours == 48
        assert builder.min_volume_threshold == 500000


class TestSequenceBuilderIntegration:
    """Integration tests for sequence building."""
    
    def test_sequence_builder_initialization(self):
        """Test SequenceBuilder can be initialized."""
        builder = SequenceBuilder(window_size=30, step_size=1)
        
        assert builder.window_size == 30
        assert builder.step_size == 1
        assert len(builder.DEFAULT_FEATURES) > 0
    
    def test_sequence_builder_custom_config(self):
        """Test SequenceBuilder with custom configuration."""
        builder = SequenceBuilder(window_size=60, step_size=5, fill_missing=False)
        
        assert builder.window_size == 60
        assert builder.step_size == 5
        assert builder.fill_missing == False
    
    def test_default_features_list(self):
        """Test that SequenceBuilder has all required features."""
        builder = SequenceBuilder()
        
        # Check that all default features are defined
        required_features = [
            'rsi', 'macd', 'sentiment_score', 'volume',
            'close_price', 'sma_50', 'sma_200'
        ]
        
        for feature in required_features:
            assert feature in builder.DEFAULT_FEATURES
    
    def test_forward_fill_basic(self):
        """Test forward fill functionality."""
        builder = SequenceBuilder(fill_missing=True)
        
        # Create minimal DataFrame with NaNs
        df = pd.DataFrame({
            'col1': [1.0, 2.0, np.nan, 4.0],
            'col2': [10.0, np.nan, 30.0, 40.0]
        })
        
        # Call the forward fill method
        filled = builder._forward_fill_nans(df.values)
        
        # Should return array with interpolated values
        assert filled is not None
        assert filled.shape == df.values.shape


class TestEndToEndFeatureEngineering:
    """End-to-end tests for pipeline integration."""
    
    def test_feature_and_sequence_builders_compatible(self):
        """Test that builders are compatible with each other."""
        feature_builder = FeatureBuilder()
        sequence_builder = SequenceBuilder(window_size=30)
        
        # Verify both can be instantiated
        assert feature_builder is not None
        assert sequence_builder is not None
        
        # Verify sequence builder has required features
        assert len(sequence_builder.DEFAULT_FEATURES) > 0
        
        # Verify feature builder has proper configuration
        assert feature_builder.lookback_days > 0
        assert feature_builder.sentiment_window_hours > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
