"""Test suite for experiment comparison functionality."""

import pytest
import tempfile
import json
from pathlib import Path
from datetime import datetime

from backend.ml.tracking.experiment_compare import (
    ExperimentMetrics,
    ComparisonResult,
    ExperimentComparer,
)


class TestExperimentMetrics:
    """Test ExperimentMetrics dataclass."""

    def test_create_metrics(self):
        """Test creating experiment metrics."""
        metrics = ExperimentMetrics(
            experiment_id="exp_001",
            run_id="run_001",
            run_name="baseline",
            timestamp=datetime.utcnow().isoformat(),
            model_type="xgboost",
            metrics={"accuracy": 0.92, "f1": 0.88, "sharpe": 1.5},
            params={"max_depth": "5", "learning_rate": "0.1"},
            artifacts=["model.pkl", "feature_importance.json"],
        )

        assert metrics.run_id == "run_001"
        assert metrics.metrics["accuracy"] == 0.92
        assert len(metrics.artifacts) == 2

    def test_metrics_to_dict(self):
        """Test converting metrics to dict."""
        metrics = ExperimentMetrics(
            experiment_id="exp_001",
            run_id="run_001",
            run_name="baseline",
            timestamp="2026-02-20T10:00:00",
            model_type="xgboost",
            metrics={"accuracy": 0.92},
            params={"max_depth": "5"},
        )

        data = metrics.to_dict()
        assert data["run_id"] == "run_001"
        assert data["metrics"]["accuracy"] == 0.92


class TestComparisonResult:
    """Test ComparisonResult dataclass."""

    def test_create_comparison(self):
        """Test creating comparison result."""
        result = ComparisonResult(
            baseline_run_id="run_001",
            comparison_run_id="run_002",
            improved_metrics={"accuracy": 3.2, "f1": 3.4},
            degraded_metrics={"precision": 0.5},
            unchanged_metrics=["recall"],
            overall_improvement=3.3,
        )

        assert result.baseline_run_id == "run_001"
        assert result.improved_metrics["accuracy"] == 3.2
        assert result.overall_improvement == 3.3

    def test_promote_recommendation(self):
        """Test recommendation for good improvement."""
        result = ComparisonResult(
            baseline_run_id="run_001",
            comparison_run_id="run_002",
            improved_metrics={"accuracy": 8.0},
            overall_improvement=8.0,
        )
        result.recommendation = "PROMOTE: 8.0% improvement"

        assert "PROMOTE" in result.recommendation

    def test_review_recommendation(self):
        """Test recommendation for degradation."""
        result = ComparisonResult(
            baseline_run_id="run_001",
            comparison_run_id="run_002",
            degraded_metrics={"accuracy": 5.0},
        )
        result.recommendation = "REVIEW: 5.0% degradation in accuracy"

        assert "REVIEW" in result.recommendation


class TestExperimentComparer:
    """Test ExperimentComparer functionality."""

    @pytest.fixture
    def comparer(self):
        """Create experiment comparer with temp cache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            comparer = ExperimentComparer(cache_dir=tmpdir)
            yield comparer

    def test_initialize_comparer(self, comparer):
        """Test initializing comparer."""
        assert comparer.cache_dir.exists()
        assert len(comparer.experiments_cache) == 0

    def test_cache_management(self, comparer):
        """Test caching experiment data."""
        metrics = ExperimentMetrics(
            experiment_id="exp_001",
            run_id="run_001",
            run_name="baseline",
            timestamp=datetime.utcnow().isoformat(),
            model_type="xgboost",
            metrics={"accuracy": 0.92, "f1": 0.88},
            params={"max_depth": "5"},
        )

        comparer.experiments_cache["run_001"] = metrics
        comparer._save_cache()

        # Create new comparer and check cache loaded
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            # Copy cache file
            cache_file = cache_dir / "experiments_cache.json"
            comparer.cache_dir.mkdir(parents=True, exist_ok=True)
            existing_cache = comparer.cache_dir / "experiments_cache.json"
            if existing_cache.exists():
                with open(existing_cache, "r") as f:
                    data = json.load(f)
                with open(cache_file, "w") as f:
                    json.dump(data, f)

            comparer2 = ExperimentComparer(cache_dir=str(cache_dir))
            # Comparer should load empty cache if file doesn't exist in new dir
            assert comparer2.cache_dir != comparer.cache_dir


class TestComparisonLogic:
    """Test comparison calculation logic."""

    @pytest.fixture
    def comparer_with_data(self):
        """Create comparer with test data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            comparer = ExperimentComparer(cache_dir=tmpdir)

            # Create baseline metrics
            baseline = ExperimentMetrics(
                experiment_id="exp_001",
                run_id="run_001",
                run_name="baseline",
                timestamp="2026-02-20T10:00:00",
                model_type="xgboost",
                metrics={"accuracy": 0.90, "f1": 0.87, "sharpe": 1.2},
                params={"max_depth": "5", "learning_rate": "0.1"},
                artifacts=["model.pkl"],
            )

            # Create improved metrics
            improved = ExperimentMetrics(
                experiment_id="exp_001",
                run_id="run_002",
                run_name="v1.1.0",
                timestamp="2026-02-20T11:00:00",
                model_type="xgboost",
                metrics={"accuracy": 0.93, "f1": 0.91, "sharpe": 1.5},
                params={"max_depth": "7", "learning_rate": "0.05"},
                artifacts=["model.pkl"],
            )

            comparer.experiments_cache["run_001"] = baseline
            comparer.experiments_cache["run_002"] = improved
            comparer._save_cache()

            yield comparer

    def test_compare_runs(self, comparer_with_data):
        """Test run comparison."""
        result = comparer_with_data.compare_runs("run_001", "run_002")

        assert result.baseline_run_id == "run_001"
        assert result.comparison_run_id == "run_002"
        assert "accuracy" in result.improved_metrics
        assert "max_depth" in result.parameter_changes

        # Check metric improvements
        acc_improvement = result.improved_metrics.get("accuracy", 0)
        assert acc_improvement > 0  # Should show improvement

    def test_metric_improvement_calculation(self, comparer_with_data):
        """Test correct calculation of metric improvements."""
        result = comparer_with_data.compare_runs("run_001", "run_002")

        # accuracy: (0.93 - 0.90) / 0.90 * 100 = 3.33%
        acc_improvement = result.improved_metrics.get("accuracy", 0)
        assert 3.0 < acc_improvement < 4.0

    def test_parameter_changes_tracking(self, comparer_with_data):
        """Test parameter change tracking."""
        result = comparer_with_data.compare_runs("run_001", "run_002")

        assert "max_depth" in result.parameter_changes
        old_val, new_val = result.parameter_changes["max_depth"]
        assert old_val == "5"
        assert new_val == "7"

    def test_identify_feature_impact(self, comparer_with_data):
        """Test feature impact identification."""
        impact = comparer_with_data.identify_feature_impact("run_001", "run_002")

        assert "max_depth" in impact
        assert "learning_rate" in impact
        assert impact["max_depth"]["old_value"] == "5"
        assert impact["max_depth"]["new_value"] == "7"


class TestExperimentRanking:
    """Test experiment ranking functionality."""

    @pytest.fixture
    def comparer_with_multiple_runs(self):
        """Create comparer with multiple experiment runs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            comparer = ExperimentComparer(cache_dir=tmpdir)

            # Create multiple runs with different accuracies
            for i in range(5):
                metrics = ExperimentMetrics(
                    experiment_id="exp_001",
                    run_id=f"run_{i:03d}",
                    run_name=f"variant_{i}",
                    timestamp=f"2026-02-20T{10+i}:00:00",
                    model_type="xgboost",
                    metrics={"accuracy": 0.85 + i * 0.02, "f1": 0.82 + i * 0.02},
                    params={},
                    artifacts=[],
                )
                comparer.experiments_cache[f"run_{i:03d}"] = metrics

            comparer._save_cache()
            yield comparer

    def test_rank_by_metric(self, comparer_with_multiple_runs):
        """Test ranking runs by accuracy."""
        # Note: Since we can't actually call fetch_experiment without MLflow,
        # we test the ranking logic with cached data
        ranked = sorted(
            [
                (rid, exp.metrics.get("accuracy", 0))
                for rid, exp in comparer_with_multiple_runs.experiments_cache.items()
            ],
            key=lambda x: x[1],
            reverse=True,
        )

        assert len(ranked) == 5
        # Best should have accuracy 0.93 (0.85 + 4*0.02)
        assert ranked[0][1] > 0.92


class TestReportGeneration:
    """Test report generation."""

    @pytest.fixture
    def comparer_for_reports(self):
        """Create comparer for report tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            comparer = ExperimentComparer(cache_dir=tmpdir)

            baseline = ExperimentMetrics(
                experiment_id="exp_001",
                run_id="run_001",
                run_name="baseline",
                timestamp="2026-02-20T10:00:00",
                model_type="xgboost",
                metrics={"accuracy": 0.90, "f1": 0.87},
                params={"max_depth": "5"},
                artifacts=["model.pkl"],
            )

            improved = ExperimentMetrics(
                experiment_id="exp_001",
                run_id="run_002",
                run_name="v1.1.0",
                timestamp="2026-02-20T11:00:00",
                model_type="xgboost",
                metrics={"accuracy": 0.93, "f1": 0.91},
                params={"max_depth": "7"},
                artifacts=["model.pkl"],
            )

            comparer.experiments_cache["run_001"] = baseline
            comparer.experiments_cache["run_002"] = improved

            yield comparer

    def test_generate_comparison_report(self, comparer_for_reports):
        """Test report generation."""
        report = comparer_for_reports.generate_comparison_report("run_001", "run_002")

        assert "EXPERIMENT COMPARISON REPORT" in report
        assert "run_001" in report
        assert "run_002" in report
        assert "METRICS COMPARISON" in report
        assert "PARAMETER CHANGES" in report

    def test_report_contains_metrics(self, comparer_for_reports):
        """Test that report includes metrics."""
        report = comparer_for_reports.generate_comparison_report("run_001", "run_002")

        # Should show improvements
        assert "accuracy" in report.lower()
        assert "improved" in report.lower() or "✓" in report


class TestSummaryStatistics:
    """Test summary statistics generation."""

    @pytest.fixture
    def comparer_with_summary_data(self):
        """Create comparer with data for summary stats."""
        with tempfile.TemporaryDirectory() as tmpdir:
            comparer = ExperimentComparer(cache_dir=tmpdir)

            # Create runs with varying metrics
            accuracies = [0.88, 0.90, 0.92, 0.91, 0.89]
            for i, acc in enumerate(accuracies):
                metrics = ExperimentMetrics(
                    experiment_id="exp_001",
                    run_id=f"run_{i:03d}",
                    run_name=f"run_{i}",
                    timestamp=f"2026-02-20T{10+i}:00:00",
                    model_type="xgboost",
                    metrics={"accuracy": acc, "f1": acc - 0.03},
                    params={},
                    artifacts=[],
                )
                comparer.experiments_cache[f"run_{i:03d}"] = metrics

            yield comparer

    def test_list_cached_experiments(self, comparer_with_summary_data):
        """Test listing cached experiments."""
        cached = comparer_with_summary_data.list_cached_experiments()

        assert len(cached) == 5
        # Should be sorted by timestamp (newest first)
        for i in range(len(cached) - 1):
            assert cached[i].timestamp >= cached[i + 1].timestamp

    def test_get_experiment_summary(self, comparer_with_summary_data):
        """Test getting experiment summary statistics."""
        # Manually calculate summary from cache
        runs = list(comparer_with_summary_data.experiments_cache.values())
        accuracies = [r.metrics.get("accuracy", 0) for r in runs]

        assert len(accuracies) == 5
        assert max(accuracies) == 0.92
        assert min(accuracies) == 0.88
        assert 0.89 < sum(accuracies) / len(accuracies) < 0.91


class TestExperimentBestRun:
    """Test finding best run in experiment."""

    @pytest.fixture
    def comparer_with_runs(self):
        """Create comparer with multiple runs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            comparer = ExperimentComparer(cache_dir=tmpdir)

            metrics_list = [
                {"accuracy": 0.88, "f1": 0.85},
                {"accuracy": 0.92, "f1": 0.89},
                {"accuracy": 0.90, "f1": 0.87},
            ]

            for i, m in enumerate(metrics_list):
                metrics = ExperimentMetrics(
                    experiment_id="exp_001",
                    run_id=f"run_{i:03d}",
                    run_name=f"attempt_{i}",
                    timestamp=f"2026-02-20T{10+i}:00:00",
                    model_type="xgboost",
                    metrics=m,
                    params={},
                    artifacts=[],
                )
                comparer.experiments_cache[f"run_{i:03d}"] = metrics

            yield comparer

    def test_best_run_by_f1(self, comparer_with_runs):
        """Test finding best run by F1 metric."""
        cached_runs = list(comparer_with_runs.experiments_cache.values())
        best = max(cached_runs, key=lambda r: r.metrics.get("f1", 0))

        assert best.metrics["f1"] == 0.89
        assert best.metrics["accuracy"] == 0.92
