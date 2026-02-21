"""Test suite for model registry functionality."""

import pytest
import tempfile
import json
from pathlib import Path
from datetime import datetime, timedelta

from backend.ml.registry import (
    ModelRegistry,
    ModelVersion,
    VersionStatus,
    DeploymentRecord,
    ABTestResult,
)


class TestModelRegistry:
    """Test ModelRegistry core functionality."""

    @pytest.fixture
    def registry(self):
        """Create temporary registry for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = ModelRegistry(registry_dir=tmpdir)
            yield registry

    def test_register_version(self, registry):
        """Test registering a new model version."""
        version = registry.register_version(
            version_id="v1.0.0",
            model_type="xgboost",
            feature_snapshot_id="snap_001",
            mlflow_run_id="abc123",
            model_path="/models/xgboost_v1.pkl",
            metrics={"accuracy": 0.92, "f1": 0.88, "sharpe": 1.5},
            hyperparameters={"max_depth": 7, "learning_rate": 0.1},
            feature_importance={"rsi": 0.15, "macd": 0.12},
            training_config={"batch_size": 32, "epochs": 100},
            created_by="data_scientist",
            notes="Initial baseline model",
        )

        assert version.version_id == "v1.0.0"
        assert version.model_type == "xgboost"
        assert version.status == VersionStatus.EXPERIMENTAL
        assert version.metrics["accuracy"] == 0.92
        assert version.created_by == "data_scientist"

    def test_duplicate_version_error(self, registry):
        """Test that duplicate version IDs raise error."""
        registry.register_version(
            version_id="v1.0.0",
            model_type="xgboost",
            feature_snapshot_id="snap_001",
            mlflow_run_id="abc123",
            model_path="/models/xgboost_v1.pkl",
            metrics={"accuracy": 0.92},
            hyperparameters={},
            feature_importance={},
            training_config={},
        )

        with pytest.raises(ValueError, match="already exists"):
            registry.register_version(
                version_id="v1.0.0",
                model_type="lightgbm",
                feature_snapshot_id="snap_002",
                mlflow_run_id="xyz789",
                model_path="/models/lightgbm_v1.pkl",
                metrics={"accuracy": 0.90},
                hyperparameters={},
                feature_importance={},
                training_config={},
            )

    def test_promote_version(self, registry):
        """Test promoting version through states."""
        registry.register_version(
            version_id="v1.0.0",
            model_type="xgboost",
            feature_snapshot_id="snap_001",
            mlflow_run_id="abc123",
            model_path="/models/xgboost_v1.pkl",
            metrics={"accuracy": 0.92},
            hyperparameters={},
            feature_importance={},
            training_config={},
        )

        # Promote to staging
        version = registry.promote_version(
            "v1.0.0", VersionStatus.STAGING, reason="Passed unit tests"
        )
        assert version.status == VersionStatus.STAGING

        # Promote to production
        version = registry.promote_version(
            "v1.0.0", VersionStatus.PRODUCTION, reason="Approved for production"
        )
        assert version.status == VersionStatus.PRODUCTION

    def test_invalid_promotion(self, registry):
        """Test that invalid state transitions raise error."""
        registry.register_version(
            version_id="v1.0.0",
            model_type="xgboost",
            feature_snapshot_id="snap_001",
            mlflow_run_id="abc123",
            model_path="/models/xgboost_v1.pkl",
            metrics={"accuracy": 0.92},
            hyperparameters={},
            feature_importance={},
            training_config={},
        )

        # Cannot directly go from experimental to production
        with pytest.raises(ValueError, match="Cannot transition"):
            registry.promote_version("v1.0.0", VersionStatus.PRODUCTION)

    def test_deploy_version(self, registry):
        """Test deployment tracking."""
        registry.register_version(
            version_id="v1.0.0",
            model_type="xgboost",
            feature_snapshot_id="snap_001",
            mlflow_run_id="abc123",
            model_path="/models/xgboost_v1.pkl",
            metrics={"accuracy": 0.92, "f1": 0.88},
            hyperparameters={},
            feature_importance={},
            training_config={},
        )

        registry.promote_version("v1.0.0", VersionStatus.STAGING)
        registry.promote_version("v1.0.0", VersionStatus.PRODUCTION)

        deployment = registry.deploy_version(
            "v1.0.0",
            environment="production",
            deployed_by="devops",
            metrics_before={"accuracy": 0.87, "f1": 0.83},
        )

        assert deployment.status == "success"
        assert deployment.environment == "production"
        assert deployment.deployed_by == "devops"
        assert deployment.metrics_before["accuracy"] == 0.87

    def test_rollback_version(self, registry):
        """Test rollback functionality."""
        registry.register_version(
            version_id="v1.0.0",
            model_type="xgboost",
            feature_snapshot_id="snap_001",
            mlflow_run_id="abc123",
            model_path="/models/xgboost_v1.pkl",
            metrics={"accuracy": 0.92},
            hyperparameters={},
            feature_importance={},
            training_config={},
        )

        registry.promote_version("v1.0.0", VersionStatus.STAGING)
        registry.promote_version("v1.0.0", VersionStatus.PRODUCTION)
        registry.deploy_version("v1.0.0", environment="production", deployed_by="devops")

        # Rollback
        deployment = registry.rollback_version("v1.0.0", reason="High error rate detected")
        assert deployment.status == "rolled_back"
        assert deployment.reverted_at is not None


class TestABTesting:
    """Test A/B testing functionality."""

    @pytest.fixture
    def registry(self):
        """Create registry with two versions for A/B testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = ModelRegistry(registry_dir=tmpdir)

            # Register two versions
            registry.register_version(
                version_id="v1.0.0",
                model_type="xgboost",
                feature_snapshot_id="snap_001",
                mlflow_run_id="abc123",
                model_path="/models/v1.pkl",
                metrics={"accuracy": 0.92, "f1": 0.88},
                hyperparameters={},
                feature_importance={},
                training_config={},
            )

            registry.register_version(
                version_id="v1.1.0",
                model_type="xgboost",
                feature_snapshot_id="snap_002",
                mlflow_run_id="xyz789",
                model_path="/models/v1.1.pkl",
                metrics={"accuracy": 0.94, "f1": 0.90},
                hyperparameters={},
                feature_importance={},
                training_config={},
            )

            yield registry

    def test_record_ab_test(self, registry):
        """Test recording A/B test result."""
        test = registry.record_ab_test(
            test_id="test_001",
            variant_a_version="v1.0.0",
            variant_b_version="v1.1.0",
            variant_a_wins=45,
            variant_b_wins=55,
            draws=0,
            statistical_significance=0.02,
            confidence_level=0.95,
            notes="Significant improvement in variant B",
        )

        assert test.test_id == "test_001"
        assert test.variant_a_wins == 45
        assert test.variant_b_wins == 55
        assert test.winner() == "v1.1.0"

    def test_ab_test_not_significant(self, registry):
        """Test A/B test with no statistical significance."""
        test = registry.record_ab_test(
            test_id="test_002",
            variant_a_version="v1.0.0",
            variant_b_version="v1.1.0",
            variant_a_wins=50,
            variant_b_wins=50,
            draws=0,
            statistical_significance=0.5,
            confidence_level=0.05,
            notes="No significant difference",
        )

        assert test.winner() is None


class TestVersionQuerying:
    """Test version querying and retrieval."""

    @pytest.fixture
    def registry_with_versions(self):
        """Create registry with multiple versions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = ModelRegistry(registry_dir=tmpdir)

            # Create multiple versions
            for i in range(3):
                registry.register_version(
                    version_id=f"v1.{i}.0",
                    model_type="xgboost" if i % 2 == 0 else "lightgbm",
                    feature_snapshot_id=f"snap_{i:03d}",
                    mlflow_run_id=f"run_{i:03d}",
                    model_path=f"/models/v1.{i}.pkl",
                    metrics={"accuracy": 0.85 + i * 0.03, "f1": 0.82 + i * 0.03},
                    hyperparameters={},
                    feature_importance={},
                    training_config={},
                )

            # Promote one to production
            registry.promote_version("v1.2.0", VersionStatus.STAGING)
            registry.promote_version("v1.2.0", VersionStatus.PRODUCTION)

            yield registry

    def test_get_versions_by_status(self, registry_with_versions):
        """Test querying by status."""
        experimental = registry_with_versions.get_versions_by_status(
            VersionStatus.EXPERIMENTAL
        )
        assert len(experimental) == 2

        production = registry_with_versions.get_versions_by_status(
            VersionStatus.PRODUCTION
        )
        assert len(production) == 1
        assert production[0].version_id == "v1.2.0"

    def test_get_versions_by_type(self, registry_with_versions):
        """Test querying by model type."""
        xgboost_versions = registry_with_versions.get_versions_by_type("xgboost")
        assert len(xgboost_versions) == 2

        lightgbm_versions = registry_with_versions.get_versions_by_type("lightgbm")
        assert len(lightgbm_versions) == 1

    def test_get_current_production(self, registry_with_versions):
        """Test getting current production model."""
        prod = registry_with_versions.get_current_production()
        assert prod is not None
        assert prod.version_id == "v1.2.0"

    def test_list_versions(self, registry_with_versions):
        """Test listing versions."""
        versions = registry_with_versions.list_versions()
        assert len(versions) == 3

        # Should be sorted by creation date (newest first)
        assert versions[0].created_at >= versions[1].created_at


class TestVersionComparison:
    """Test version comparison functionality."""

    @pytest.fixture
    def registry_for_comparison(self):
        """Create registry with comparable versions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = ModelRegistry(registry_dir=tmpdir)

            registry.register_version(
                version_id="baseline",
                model_type="xgboost",
                feature_snapshot_id="snap_001",
                mlflow_run_id="abc123",
                model_path="/models/baseline.pkl",
                metrics={"accuracy": 0.90, "f1": 0.87, "sharpe": 1.2},
                hyperparameters={"max_depth": 5},
                feature_importance={"rsi": 0.2, "macd": 0.15},
                training_config={},
            )

            registry.register_version(
                version_id="v1.1.0",
                model_type="xgboost",
                feature_snapshot_id="snap_002",
                mlflow_run_id="xyz789",
                model_path="/models/v1.1.pkl",
                metrics={"accuracy": 0.93, "f1": 0.91, "sharpe": 1.5},
                hyperparameters={"max_depth": 7},
                feature_importance={"rsi": 0.25, "macd": 0.18},
                training_config={},
            )

            yield registry

    def test_compare_versions(self, registry_for_comparison):
        """Test comparing multiple versions."""
        comparison = registry_for_comparison.compare_versions(
            ["baseline", "v1.1.0"], metrics_to_compare=["accuracy", "f1"]
        )

        assert len(comparison["versions"]) == 2
        assert comparison["best_version"] == "v1.1.0"
        assert comparison["comparison_data"]["baseline"]["accuracy"] == 0.90
        assert comparison["comparison_data"]["v1.1.0"]["f1"] == 0.91

    def test_compare_with_metrics_filter(self, registry_for_comparison):
        """Test comparison with specific metrics."""
        comparison = registry_for_comparison.compare_versions(
            ["baseline", "v1.1.0"], metrics_to_compare=["accuracy"]
        )

        for version_data in comparison["versions"]:
            assert "accuracy" in version_data["metrics"]
            assert len(version_data["metrics"]) == 1


class TestRegistryPersistence:
    """Test registry persistence to disk."""

    def test_save_and_load_registry(self):
        """Test that registry persists correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create and populate registry
            registry1 = ModelRegistry(registry_dir=tmpdir)
            registry1.register_version(
                version_id="v1.0.0",
                model_type="xgboost",
                feature_snapshot_id="snap_001",
                mlflow_run_id="abc123",
                model_path="/models/v1.pkl",
                metrics={"accuracy": 0.92},
                hyperparameters={"max_depth": 5},
                feature_importance={"rsi": 0.2},
                training_config={},
            )

            # Create new registry instance from same directory
            registry2 = ModelRegistry(registry_dir=tmpdir)
            assert len(registry2.versions) == 1
            assert "v1.0.0" in registry2.versions
            assert registry2.versions["v1.0.0"].metrics["accuracy"] == 0.92


class TestDeploymentTracking:
    """Test deployment history tracking."""

    @pytest.fixture
    def registry(self):
        """Create registry for deployment tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = ModelRegistry(registry_dir=tmpdir)

            registry.register_version(
                version_id="v1.0.0",
                model_type="xgboost",
                feature_snapshot_id="snap_001",
                mlflow_run_id="abc123",
                model_path="/models/v1.pkl",
                metrics={"accuracy": 0.92},
                hyperparameters={},
                feature_importance={},
                training_config={},
            )

            yield registry

    def test_get_deployment_history(self, registry):
        """Test retrieving deployment history."""
        registry.promote_version("v1.0.0", VersionStatus.STAGING)
        registry.promote_version("v1.0.0", VersionStatus.PRODUCTION)
        registry.deploy_version(
            "v1.0.0", environment="production", deployed_by="devops"
        )

        history = registry.get_deployment_history(version_id="v1.0.0")
        assert len(history) == 1
        assert history[0].environment == "production"

    def test_get_deployment_history_by_environment(self, registry):
        """Test querying deployment history by environment."""
        registry.promote_version("v1.0.0", VersionStatus.STAGING)
        registry.deploy_version("v1.0.0", environment="staging", deployed_by="devops")
        registry.promote_version("v1.0.0", VersionStatus.PRODUCTION)
        registry.deploy_version(
            "v1.0.0", environment="production", deployed_by="devops"
        )

        prod_history = registry.get_deployment_history(environment="production")
        assert len(prod_history) >= 1
        assert all(d.environment == "production" for d in prod_history)


class TestRegistryReport:
    """Test report generation."""

    @pytest.fixture
    def registry_with_data(self):
        """Create registry with various versions for reporting."""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = ModelRegistry(registry_dir=tmpdir)

            for i in range(3):
                registry.register_version(
                    version_id=f"v1.{i}.0",
                    model_type="xgboost",
                    feature_snapshot_id=f"snap_{i}",
                    mlflow_run_id=f"run_{i}",
                    model_path=f"/models/v1.{i}.pkl",
                    metrics={"accuracy": 0.85 + i * 0.03},
                    hyperparameters={},
                    feature_importance={},
                    training_config={},
                )

            registry.promote_version("v1.2.0", VersionStatus.STAGING)
            registry.promote_version("v1.2.0", VersionStatus.PRODUCTION)

            yield registry

    def test_generate_registry_report(self, registry_with_data):
        """Test report generation."""
        report = registry_with_data.generate_registry_report()

        assert "MODEL REGISTRY REPORT" in report
        assert "Total Versions: 3" in report
        assert "EXPERIMENTAL" in report
        assert "PRODUCTION" in report
