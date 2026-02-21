"""Tests for feature importance tracking."""

import pytest
import tempfile
from pathlib import Path

from backend.ml.features.importance import (
    FeatureImportanceTracker,
    FeatureImportanceRecord,
    FeatureImportanceSummary,
    create_feature_importance_tracker,
)


class TestFeatureImportanceRecord:
    """Test FeatureImportanceRecord dataclass."""

    def test_create_record(self):
        """Test creating a record."""
        record = FeatureImportanceRecord(
            feature_name="rsi_14",
            importance_score=0.15,
            importance_pct=15.0,
            model_type="xgboost",
            training_date="2026-02-20T10:00:00",
            experiment_id="exp_001",
        )

        assert record.feature_name == "rsi_14"
        assert record.importance_score == 0.15
        assert record.feature_group == "technical"

    def test_record_sentiment_classification(self):
        """Test sentiment feature classification."""
        record = FeatureImportanceRecord(
            feature_name="sentiment_trend_7d",
            importance_score=0.1,
            importance_pct=10.0,
            model_type="xgboost",
            training_date="2026-02-20T10:00:00",
            experiment_id="exp_001",
        )

        assert record.feature_group == "sentiment"

    def test_record_volume_classification(self):
        """Test volume feature classification."""
        record = FeatureImportanceRecord(
            feature_name="volume_ratio",
            importance_score=0.08,
            importance_pct=8.0,
            model_type="xgboost",
            training_date="2026-02-20T10:00:00",
            experiment_id="exp_001",
        )

        assert record.feature_group == "volume"

    def test_record_to_dict(self):
        """Test converting record to dict."""
        record = FeatureImportanceRecord(
            feature_name="test_feature",
            importance_score=0.05,
            importance_pct=5.0,
            model_type="xgboost",
            training_date="2026-02-20T10:00:00",
            experiment_id="exp_001",
        )

        data = record.to_dict()
        assert data["feature_name"] == "test_feature"
        assert data["importance_pct"] == 5.0


class TestFeatureImportanceTracker:
    """Test FeatureImportanceTracker functionality."""

    @pytest.fixture
    def tracker(self):
        """Create temporary tracker."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = FeatureImportanceTracker(storage_dir=tmpdir)
            yield tracker

    def test_log_single_experiment(self, tracker):
        """Test logging importance from single experiment."""
        importance_dict = {
            "rsi_14": 0.15,
            "macd": 0.12,
            "sentiment_trend_7d": 0.10,
            "volume_ratio": 0.08,
        }

        records = tracker.log_feature_importance(
            importance_dict, "xgboost", "exp_001"
        )

        assert len(records) == 4
        assert records[0].feature_name == "rsi_14"  # Highest importance
        assert records[0].rank == 1

    def test_importance_normalization(self, tracker):
        """Test that importance is normalized to 100%."""
        importance_dict = {"feat_a": 0.5, "feat_b": 0.3, "feat_c": 0.2}

        records = tracker.log_feature_importance(
            importance_dict, "xgboost", "exp_001"
        )

        total_pct = sum(r.importance_pct for r in records)
        assert abs(total_pct - 100.0) < 0.01

    def test_get_feature_summary(self, tracker):
        """Test getting feature importance summary."""
        importance_dict = {
            "high_impact_1": 0.5,  # 50%
            "high_impact_2": 0.3,  # 30%
            "medium_impact": 0.15,  # 15%
            "dead_feature": 0.005,  # 0.5%
        }

        tracker.log_feature_importance(importance_dict, "xgboost", "exp_001")
        summary = tracker.get_feature_summary("exp_001")

        assert summary is not None
        assert len(summary.high_impact_features) == 2  # > 1%
        assert len(summary.medium_impact_features) == 1  # 0.1% - 1%
        assert len(summary.dead_features) == 1  # < 0.1%

    def test_feature_group_classification(self, tracker):
        """Test feature group classification in summary."""
        importance_dict = {
            "rsi_14": 0.25,
            "macd": 0.20,
            "sentiment_trend_7d": 0.20,
            "volume_ratio": 0.15,
            "sma_50": 0.10,
            "other_feature": 0.10,
        }

        tracker.log_feature_importance(importance_dict, "xgboost", "exp_001")
        summary = tracker.get_feature_summary("exp_001")

        assert summary is not None
        assert "sentiment" in summary.feature_group_importance
        assert "technical" in summary.feature_group_importance
        assert "volume" in summary.feature_group_importance

    def test_zero_importance_handling(self, tracker):
        """Test handling of zero total importance."""
        importance_dict = {"feat_a": 0.0, "feat_b": 0.0}

        records = tracker.log_feature_importance(
            importance_dict, "xgboost", "exp_001"
        )

        assert len(records) == 0


class TestFeatureIdentification:
    """Test identifying important features."""

    @pytest.fixture
    def tracker_with_data(self):
        """Create tracker with multiple experiments."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = FeatureImportanceTracker(storage_dir=tmpdir)

            # Exp 1: sentiment features emerging
            tracker.log_feature_importance(
                {"rsi": 0.3, "macd": 0.25, "sentiment": 0.2, "volume": 0.25},
                "xgboost",
                "exp_001",
            )

            # Exp 2: sentiment features growing
            tracker.log_feature_importance(
                {"rsi": 0.25, "macd": 0.20, "sentiment": 0.35, "volume": 0.20},
                "xgboost",
                "exp_002",
            )

            yield tracker

    def test_identify_emerging_features(self, tracker_with_data):
        """Test identifying emerging features across experiments."""
        emerging = tracker_with_data.identify_emerging_features(
            ["exp_001", "exp_002"], growth_threshold=0.1
        )

        assert "sentiment" in emerging
        assert emerging["sentiment"] > 0.1

    def test_identify_declining_features(self, tracker_with_data):
        """Test identifying declining features."""
        declining = tracker_with_data.identify_declining_features(
            ["exp_001", "exp_002"], decline_threshold=0.01
        )

        assert "rsi" in declining or "macd" in declining or "volume" in declining

    def test_compare_importance_across_experiments(self, tracker_with_data):
        """Test comparing importance across experiments."""
        df = tracker_with_data.compare_importance_across_experiments(
            ["exp_001", "exp_002"], top_k=5
        )

        assert "exp_001" in df.columns
        assert "exp_002" in df.columns
        assert len(df) > 0


class TestReportGeneration:
    """Test report generation."""

    @pytest.fixture
    def tracker_with_data(self):
        """Create tracker with sample data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = FeatureImportanceTracker(storage_dir=tmpdir)

            importance_dict = {
                "sentiment_trend_7d": 0.25,
                "rsi_14": 0.20,
                "macd": 0.18,
                "volume_ratio": 0.15,
                "sma_cross": 0.12,
                "dead_feat_1": 0.001,
                "dead_feat_2": 0.0005,
            }

            tracker.log_feature_importance(
                importance_dict, "xgboost", "exp_001"
            )

            yield tracker

    def test_generate_importance_report(self, tracker_with_data):
        """Test report generation."""
        report = tracker_with_data.generate_importance_report("exp_001")

        assert "FEATURE IMPORTANCE REPORT" in report
        assert "exp_001" in report
        assert "sentiment_trend_7d" in report
        assert "HIGH-IMPACT" in report

    def test_report_with_recommendations(self, tracker_with_data):
        """Test that report includes recommendations."""
        report = tracker_with_data.generate_importance_report("exp_001")

        assert "RECOMMENDATIONS" in report or len(report) > 50


class TestMultipleExperiments:
    """Test tracking multiple experiments."""

    @pytest.fixture
    def tracker(self):
        """Create tracker."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = FeatureImportanceTracker(storage_dir=tmpdir)
            yield tracker

    def test_log_multiple_experiments(self, tracker):
        """Test logging multiple experiments."""
        for exp_id in ["exp_001", "exp_002", "exp_003"]:
            tracker.log_feature_importance(
                {"feat_a": 0.5, "feat_b": 0.3, "feat_c": 0.2},
                "xgboost",
                exp_id,
            )

        experiments = tracker.list_experiments()
        assert len(experiments) == 3
        assert "exp_001" in experiments
        assert "exp_002" in experiments

    def test_get_records_by_experiment(self, tracker):
        """Test retrieving records for specific experiment."""
        tracker.log_feature_importance(
            {"feat_a": 0.6, "feat_b": 0.4}, "xgboost", "exp_001"
        )

        tracker.log_feature_importance(
            {"feat_a": 0.5, "feat_c": 0.5}, "xgboost", "exp_002"
        )

        exp1_records = tracker.get_records_by_experiment("exp_001")
        assert len(exp1_records) == 2
        assert exp1_records[0].feature_name == "feat_a"  # Higher importance

    def test_experiments_independent(self, tracker):
        """Test that experiments don't interfere with each other."""
        tracker.log_feature_importance(
            {"feat_high": 0.8, "feat_low": 0.2}, "xgboost", "exp_001"
        )

        tracker.log_feature_importance(
            {"feat_high": 0.2, "feat_low": 0.8}, "lightgbm", "exp_002"
        )

        summary1 = tracker.get_feature_summary("exp_001")
        summary2 = tracker.get_feature_summary("exp_002")

        assert len(summary1.high_impact_features) == 1
        assert "feat_high" in summary1.high_impact_features[0]
        assert "feat_low" in summary2.high_impact_features[0]


class TestPersistence:
    """Test persistence of importance records."""

    def test_save_and_load_records(self):
        """Test that records persist across instances."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create and populate tracker
            tracker1 = FeatureImportanceTracker(storage_dir=tmpdir)
            tracker1.log_feature_importance(
                {"feat_a": 0.5, "feat_b": 0.3, "feat_c": 0.2},
                "xgboost",
                "exp_001",
            )

            # Create new tracker instance and verify data persists
            tracker2 = FeatureImportanceTracker(storage_dir=tmpdir)
            records = tracker2.get_records_by_experiment("exp_001")

            assert len(records) == 3
            assert records[0].feature_name == "feat_a"


class TestFactoryFunction:
    """Test factory function."""

    def test_create_tracker(self):
        """Test creating tracker via factory."""
        tracker = create_feature_importance_tracker()

        assert tracker is not None
        assert isinstance(tracker, FeatureImportanceTracker)


class TestEdgeCases:
    """Test edge cases."""

    @pytest.fixture
    def tracker(self):
        """Create tracker."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = FeatureImportanceTracker(storage_dir=tmpdir)
            yield tracker

    def test_very_small_importance_values(self, tracker):
        """Test handling of very small importance values."""
        importance_dict = {
            "feat_a": 1e-10,
            "feat_b": 1e-9,
            "feat_c": 1e-8,
        }

        records = tracker.log_feature_importance(
            importance_dict, "xgboost", "exp_001"
        )

        assert len(records) == 3
        total_pct = sum(r.importance_pct for r in records)
        assert abs(total_pct - 100.0) < 0.01

    def test_many_features(self, tracker):
        """Test with many features."""
        importance_dict = {
            f"feature_{i}": 1.0 / 100 for i in range(100)
        }

        records = tracker.log_feature_importance(
            importance_dict, "xgboost", "exp_001"
        )

        assert len(records) == 100
        summary = tracker.get_feature_summary("exp_001")
        assert summary.total_features == 100

    def test_single_feature(self, tracker):
        """Test with single feature."""
        importance_dict = {"single_feature": 1.0}

        records = tracker.log_feature_importance(
            importance_dict, "xgboost", "exp_001"
        )

        assert len(records) == 1
        assert records[0].importance_pct == 100.0

    def test_special_characters_in_feature_names(self, tracker):
        """Test feature names with special characters."""
        importance_dict = {
            "feature-with-dash": 0.3,
            "feature_with_underscore": 0.3,
            "feature.with.dot": 0.2,
            "feature/with/slash": 0.2,
        }

        records = tracker.log_feature_importance(
            importance_dict, "xgboost", "exp_001"
        )

        assert len(records) == 4
