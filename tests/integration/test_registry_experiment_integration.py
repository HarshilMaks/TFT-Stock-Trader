"""Integration tests for Model Registry and Experiment Comparison working together."""

import pytest
import tempfile
from datetime import datetime

from backend.ml.registry import ModelRegistry, VersionStatus, ABTestResult
from backend.ml.tracking.experiment_compare import ExperimentComparer, ExperimentMetrics


class TestRegistryExperimentIntegration:
    """Test Model Registry and Experiment Comparison working together."""

    @pytest.fixture
    def integrated_system(self):
        """Create both registry and comparer for integration testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = ModelRegistry(registry_dir=f"{tmpdir}/registry")
            comparer = ExperimentComparer(cache_dir=f"{tmpdir}/cache")
            yield registry, comparer

    def test_register_model_from_experiment(self, integrated_system):
        """Test registering a model based on experiment results."""
        registry, comparer = integrated_system

        # Create experiment metrics
        exp_metrics = ExperimentMetrics(
            experiment_id="exp_001",
            run_id="run_001",
            run_name="baseline",
            timestamp=datetime.utcnow().isoformat(),
            model_type="xgboost",
            metrics={"accuracy": 0.92, "f1": 0.88, "sharpe": 1.2},
            params={"max_depth": "5", "learning_rate": "0.1"},
            artifacts=["model.pkl"],
        )

        comparer.experiments_cache["run_001"] = exp_metrics

        # Register model version based on experiment
        version = registry.register_version(
            version_id="v1.0.0",
            model_type=exp_metrics.model_type,
            feature_snapshot_id="snap_001",
            mlflow_run_id=exp_metrics.run_id,
            model_path="/models/v1.pkl",
            metrics=exp_metrics.metrics,
            hyperparameters={k: v for k, v in exp_metrics.params.items()},
            feature_importance={"rsi": 0.2},
            training_config={},
        )

        assert version.version_id == "v1.0.0"
        assert version.mlflow_run_id == "run_001"
        assert version.metrics["accuracy"] == 0.92

    def test_compare_and_promote_workflow(self, integrated_system):
        """Test comparing experiments then promoting winner in registry."""
        registry, comparer = integrated_system

        # Register two versions
        registry.register_version(
            version_id="v1.0.0",
            model_type="xgboost",
            feature_snapshot_id="snap_001",
            mlflow_run_id="run_001",
            model_path="/models/v1.pkl",
            metrics={"accuracy": 0.90, "f1": 0.87},
            hyperparameters={},
            feature_importance={},
            training_config={},
        )

        registry.register_version(
            version_id="v1.1.0",
            model_type="xgboost",
            feature_snapshot_id="snap_002",
            mlflow_run_id="run_002",
            model_path="/models/v1.1.pkl",
            metrics={"accuracy": 0.93, "f1": 0.91},
            hyperparameters={},
            feature_importance={},
            training_config={},
        )

        # Create experiment metrics for comparison
        baseline = ExperimentMetrics(
            experiment_id="exp_001",
            run_id="run_001",
            run_name="v1.0.0",
            timestamp="2026-02-20T10:00:00",
            model_type="xgboost",
            metrics={"accuracy": 0.90, "f1": 0.87},
            params={"max_depth": "5"},
            artifacts=[],
        )

        improved = ExperimentMetrics(
            experiment_id="exp_001",
            run_id="run_002",
            run_name="v1.1.0",
            timestamp="2026-02-20T11:00:00",
            model_type="xgboost",
            metrics={"accuracy": 0.93, "f1": 0.91},
            params={"max_depth": "7"},
            artifacts=[],
        )

        comparer.experiments_cache["run_001"] = baseline
        comparer.experiments_cache["run_002"] = improved

        # Compare runs
        comparison = comparer.compare_runs("run_001", "run_002")
        assert comparison.overall_improvement > 0

        # Promote winner
        registry.promote_version("v1.1.0", VersionStatus.STAGING, reason="Better metrics")
        registry.promote_version(
            "v1.1.0", VersionStatus.PRODUCTION, reason="Experiment comparison shows improvement"
        )

        prod = registry.get_current_production()
        assert prod.version_id == "v1.1.0"

    def test_ab_test_with_experiment_comparison(self, integrated_system):
        """Test A/B testing using experiment metrics."""
        registry, comparer = integrated_system

        # Register models
        registry.register_version(
            version_id="v1.0.0",
            model_type="xgboost",
            feature_snapshot_id="snap_001",
            mlflow_run_id="run_001",
            model_path="/models/v1.pkl",
            metrics={"accuracy": 0.92},
            hyperparameters={},
            feature_importance={},
            training_config={},
        )

        registry.register_version(
            version_id="v1.1.0",
            model_type="xgboost",
            feature_snapshot_id="snap_002",
            mlflow_run_id="run_002",
            model_path="/models/v1.1.pkl",
            metrics={"accuracy": 0.94},
            hyperparameters={},
            feature_importance={},
            training_config={},
        )

        # Create experiment metrics for A/B test
        comparer.experiments_cache["run_001"] = ExperimentMetrics(
            experiment_id="exp_001",
            run_id="run_001",
            run_name="control",
            timestamp="2026-02-20T10:00:00",
            model_type="xgboost",
            metrics={"accuracy": 0.92},
            params={},
            artifacts=[],
        )

        comparer.experiments_cache["run_002"] = ExperimentMetrics(
            experiment_id="exp_001",
            run_id="run_002",
            run_name="treatment",
            timestamp="2026-02-20T11:00:00",
            model_type="xgboost",
            metrics={"accuracy": 0.94},
            params={},
            artifacts=[],
        )

        # Compare and record A/B test
        comparison = comparer.compare_runs("run_001", "run_002")
        assert "accuracy" in comparison.improved_metrics

        # Record A/B test result
        ab_test = registry.record_ab_test(
            test_id="ab_001",
            variant_a_version="v1.0.0",
            variant_b_version="v1.1.0",
            variant_a_wins=40,
            variant_b_wins=60,
            draws=0,
            statistical_significance=0.01,
            confidence_level=0.99,
        )

        assert ab_test.winner() == "v1.1.0"
        assert "ab_001" in registry.versions["v1.0.0"].ab_tests
        assert "ab_001" in registry.versions["v1.1.0"].ab_tests

    def test_production_deployment_cycle(self, integrated_system):
        """Test complete production deployment cycle with both systems."""
        registry, comparer = integrated_system

        # Phase 1: Initial registration and staging
        baseline = registry.register_version(
            version_id="baseline",
            model_type="xgboost",
            feature_snapshot_id="snap_001",
            mlflow_run_id="run_baseline",
            model_path="/models/baseline.pkl",
            metrics={"accuracy": 0.90, "f1": 0.87, "sharpe": 1.2},
            hyperparameters={},
            feature_importance={},
            training_config={},
        )

        candidate = registry.register_version(
            version_id="v2.0.0",
            model_type="xgboost",
            feature_snapshot_id="snap_002",
            mlflow_run_id="run_v2",
            model_path="/models/v2.pkl",
            metrics={"accuracy": 0.93, "f1": 0.91, "sharpe": 1.5},
            hyperparameters={},
            feature_importance={},
            training_config={},
        )

        # Phase 2: Compare experiments
        comparer.experiments_cache["run_baseline"] = ExperimentMetrics(
            experiment_id="exp_prod",
            run_id="run_baseline",
            run_name="baseline",
            timestamp="2026-02-20T10:00:00",
            model_type="xgboost",
            metrics={"accuracy": 0.90, "f1": 0.87},
            params={"max_depth": "5"},
            artifacts=[],
        )

        comparer.experiments_cache["run_v2"] = ExperimentMetrics(
            experiment_id="exp_prod",
            run_id="run_v2",
            run_name="v2.0.0",
            timestamp="2026-02-20T11:00:00",
            model_type="xgboost",
            metrics={"accuracy": 0.93, "f1": 0.91},
            params={"max_depth": "7"},
            artifacts=[],
        )

        # Phase 3: Stage candidate
        registry.promote_version("v2.0.0", VersionStatus.STAGING, reason="Ready for testing")
        staging = registry.get_versions_by_status(VersionStatus.STAGING)
        assert len(staging) == 1

        # Phase 4: Deploy to staging
        registry.deploy_version("v2.0.0", environment="staging", deployed_by="mlops")
        staging_history = registry.get_deployment_history(environment="staging")
        assert len(staging_history) >= 1

        # Phase 5: A/B test
        ab_test = registry.record_ab_test(
            test_id="prod_test",
            variant_a_version="baseline",
            variant_b_version="v2.0.0",
            variant_a_wins=45,
            variant_b_wins=55,
            draws=0,
            statistical_significance=0.02,
            confidence_level=0.95,
        )
        assert ab_test.winner() == "v2.0.0"

        # Phase 6: Promote winner
        registry.promote_version(
            "v2.0.0",
            VersionStatus.PRODUCTION,
            reason="Won A/B test with statistical significance",
        )
        registry.deploy_version("v2.0.0", environment="production", deployed_by="mlops")

        # Phase 7: Verify production state
        prod = registry.get_current_production()
        assert prod.version_id == "v2.0.0"
        assert len(prod.deployment_history) == 2  # staging + production

    def test_metrics_tracking_across_systems(self, integrated_system):
        """Test that metrics are consistently tracked across both systems."""
        registry, comparer = integrated_system

        # Create consistent metrics
        metrics = {
            "accuracy": 0.92,
            "f1": 0.88,
            "precision": 0.90,
            "sharpe": 1.2,
        }

        # Register in registry
        registry.register_version(
            version_id="v1.0.0",
            model_type="xgboost",
            feature_snapshot_id="snap_001",
            mlflow_run_id="run_001",
            model_path="/models/v1.pkl",
            metrics=metrics,
            hyperparameters={},
            feature_importance={},
            training_config={},
        )

        # Create in experiment cache
        comparer.experiments_cache["run_001"] = ExperimentMetrics(
            experiment_id="exp_001",
            run_id="run_001",
            run_name="v1.0.0",
            timestamp=datetime.utcnow().isoformat(),
            model_type="xgboost",
            metrics=metrics,
            params={},
            artifacts=[],
        )

        # Verify metrics match
        reg_version = registry.get_version("v1.0.0")
        exp_metrics = comparer.experiments_cache["run_001"]

        for metric_name in metrics.keys():
            assert reg_version.metrics[metric_name] == exp_metrics.metrics[metric_name]

    def test_rollback_with_experiment_history(self, integrated_system):
        """Test rollback with access to experiment history."""
        registry, comparer = integrated_system

        # Setup: two versions with experiment history
        v1 = registry.register_version(
            version_id="v1.0.0",
            model_type="xgboost",
            feature_snapshot_id="snap_001",
            mlflow_run_id="run_001",
            model_path="/models/v1.pkl",
            metrics={"accuracy": 0.92},
            hyperparameters={},
            feature_importance={},
            training_config={},
        )

        v2 = registry.register_version(
            version_id="v2.0.0",
            model_type="xgboost",
            feature_snapshot_id="snap_002",
            mlflow_run_id="run_002",
            model_path="/models/v2.pkl",
            metrics={"accuracy": 0.94},
            hyperparameters={},
            feature_importance={},
            training_config={},
        )

        # Promote and deploy v2
        registry.promote_version("v2.0.0", VersionStatus.STAGING)
        registry.promote_version("v2.0.0", VersionStatus.PRODUCTION)
        registry.deploy_version("v2.0.0", environment="production", deployed_by="mlops")

        # Create experiment record showing v2 has issues
        comparer.experiments_cache["run_002_eval"] = ExperimentMetrics(
            experiment_id="exp_eval",
            run_id="run_002_eval",
            run_name="v2.0.0_evaluation",
            timestamp=datetime.utcnow().isoformat(),
            model_type="xgboost",
            metrics={"accuracy": 0.91, "f1": 0.85},  # Degraded!
            params={},
            artifacts=[],
        )

        # Rollback v2
        registry.rollback_version("v2.0.0", reason="Accuracy degraded in production evaluation")

        # Verify rollback
        v2_updated = registry.get_version("v2.0.0")
        assert v2_updated.status == VersionStatus.ROLLBACK
        assert len(v2_updated.deployment_history[-1].status) > 0
