"""
Production model registry for version management, deployment tracking, and A/B testing.

This module provides enterprise-grade model version management with:
- Multiple version states (production, staging, experimental)
- Deployment history and rollback capability
- A/B test result tracking
- Performance metrics per version
- Model metadata persistence
"""

import json
import pickle
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import logging

logger = logging.getLogger(__name__)


class VersionStatus(str, Enum):
    """Model version status enumeration."""

    EXPERIMENTAL = "experimental"
    STAGING = "staging"
    PRODUCTION = "production"
    ARCHIVED = "archived"
    ROLLBACK = "rollback"


@dataclass
class ABTestResult:
    """A/B test result tracking."""

    test_id: str
    variant_a_version: str
    variant_b_version: str
    variant_a_wins: int
    variant_b_wins: int
    draws: int
    statistical_significance: float
    confidence_level: float
    started_at: str
    ended_at: str
    notes: str = ""

    def winner(self) -> Optional[str]:
        """Determine statistical winner."""
        if self.statistical_significance >= 0.05:
            return None
        return (
            self.variant_a_version
            if self.variant_a_wins > self.variant_b_wins
            else self.variant_b_version
        )

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class DeploymentRecord:
    """Deployment history record."""

    version_id: str
    deployed_at: str
    deployed_by: str
    environment: str  # production, staging, testing
    status: str  # success, failed, rolled_back
    reason: str = ""
    reverted_at: Optional[str] = None
    metrics_before: Dict = field(default_factory=dict)
    metrics_after: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class ModelVersion:
    """Model version with complete metadata."""

    version_id: str
    model_type: str  # xgboost, lightgbm, tft, lstm
    status: VersionStatus
    created_at: str
    created_by: str
    feature_snapshot_id: str
    mlflow_run_id: str
    model_path: str
    metrics: Dict[str, float] = field(default_factory=dict)
    hyperparameters: Dict[str, Any] = field(default_factory=dict)
    feature_importance: Dict[str, float] = field(default_factory=dict)
    training_config: Dict[str, Any] = field(default_factory=dict)
    deployment_history: List[DeploymentRecord] = field(default_factory=list)
    ab_tests: List[str] = field(default_factory=list)  # test IDs
    notes: str = ""
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        data = asdict(self)
        data["status"] = self.status.value
        data["deployment_history"] = [d.to_dict() for d in self.deployment_history]
        return data

    @classmethod
    def from_dict(cls, data: Dict) -> "ModelVersion":
        """Reconstruct ModelVersion from dictionary."""
        data = data.copy()
        data["status"] = VersionStatus(data["status"])
        data["deployment_history"] = [
            DeploymentRecord(**d) for d in data.get("deployment_history", [])
        ]
        return cls(**data)


class ModelRegistry:
    """
    Production model registry for managing model versions, deployments, and A/B tests.

    Features:
    - Register and manage multiple model versions (production, staging, experimental)
    - Track deployment history with rollback capability
    - Manage A/B test results and statistical significance
    - Persist model metadata and version information
    - Query models by status, type, and performance metrics
    - Generate comparison reports across versions
    """

    def __init__(self, registry_dir: str = "data/models/registry"):
        """
        Initialize model registry.

        Args:
            registry_dir: Directory for storing model metadata and history
        """
        self.registry_dir = Path(registry_dir)
        self.registry_dir.mkdir(parents=True, exist_ok=True)
        self.versions_file = self.registry_dir / "versions.json"
        self.ab_tests_file = self.registry_dir / "ab_tests.json"
        self.versions: Dict[str, ModelVersion] = {}
        self.ab_tests: Dict[str, ABTestResult] = {}
        self._load_registry()

    def _load_registry(self) -> None:
        """Load existing registry from disk."""
        if self.versions_file.exists():
            try:
                with open(self.versions_file, "r") as f:
                    versions_data = json.load(f)
                    self.versions = {
                        vid: ModelVersion.from_dict(vdata)
                        for vid, vdata in versions_data.items()
                    }
                logger.info(f"Loaded {len(self.versions)} model versions")
            except Exception as e:
                logger.error(f"Error loading versions: {e}")

        if self.ab_tests_file.exists():
            try:
                with open(self.ab_tests_file, "r") as f:
                    tests_data = json.load(f)
                    self.ab_tests = {
                        tid: ABTestResult(**tdata) for tid, tdata in tests_data.items()
                    }
                logger.info(f"Loaded {len(self.ab_tests)} A/B test results")
            except Exception as e:
                logger.error(f"Error loading A/B tests: {e}")

    def _save_registry(self) -> None:
        """Persist registry to disk."""
        # Save versions
        versions_data = {
            vid: v.to_dict() for vid, v in self.versions.items()
        }
        with open(self.versions_file, "w") as f:
            json.dump(versions_data, f, indent=2)

        # Save A/B tests
        ab_tests_data = {tid: t.to_dict() for tid, t in self.ab_tests.items()}
        with open(self.ab_tests_file, "w") as f:
            json.dump(ab_tests_data, f, indent=2)

    def register_version(
        self,
        version_id: str,
        model_type: str,
        feature_snapshot_id: str,
        mlflow_run_id: str,
        model_path: str,
        metrics: Dict[str, float],
        hyperparameters: Dict[str, Any],
        feature_importance: Dict[str, float],
        training_config: Dict[str, Any],
        created_by: str = "system",
        notes: str = "",
        tags: List[str] = None,
    ) -> ModelVersion:
        """
        Register a new model version.

        Args:
            version_id: Unique version identifier (e.g., "v1.0.0")
            model_type: Type of model (xgboost, lightgbm, tft, lstm)
            feature_snapshot_id: UUID of feature snapshot used for training
            mlflow_run_id: MLflow run ID for experiment tracking
            model_path: Path to serialized model file
            metrics: Performance metrics dict (accuracy, precision, recall, F1, Sharpe, etc.)
            hyperparameters: Hyperparameters used for training
            feature_importance: Feature importance scores
            training_config: Training configuration (batch size, epochs, etc.)
            created_by: User who created this version
            notes: Optional notes about version
            tags: Optional tags for organization

        Returns:
            Registered ModelVersion object
        """
        if version_id in self.versions:
            raise ValueError(f"Version {version_id} already exists")

        version = ModelVersion(
            version_id=version_id,
            model_type=model_type,
            status=VersionStatus.EXPERIMENTAL,
            created_at=datetime.utcnow().isoformat(),
            created_by=created_by,
            feature_snapshot_id=feature_snapshot_id,
            mlflow_run_id=mlflow_run_id,
            model_path=model_path,
            metrics=metrics,
            hyperparameters=hyperparameters,
            feature_importance=feature_importance,
            training_config=training_config,
            notes=notes,
            tags=tags or [],
        )

        self.versions[version_id] = version
        self._save_registry()
        logger.info(f"Registered version {version_id} ({model_type})")
        return version

    def promote_version(
        self, version_id: str, target_status: VersionStatus, reason: str = ""
    ) -> ModelVersion:
        """
        Promote version to new status (experimental → staging → production).

        Args:
            version_id: Version to promote
            target_status: Target status
            reason: Reason for promotion

        Returns:
            Updated ModelVersion
        """
        if version_id not in self.versions:
            raise ValueError(f"Version {version_id} not found")

        version = self.versions[version_id]
        old_status = version.status

        # Validate promotion path
        valid_transitions = {
            VersionStatus.EXPERIMENTAL: [VersionStatus.STAGING, VersionStatus.ARCHIVED],
            VersionStatus.STAGING: [
                VersionStatus.PRODUCTION,
                VersionStatus.EXPERIMENTAL,
                VersionStatus.ARCHIVED,
            ],
            VersionStatus.PRODUCTION: [VersionStatus.STAGING, VersionStatus.ROLLBACK],
            VersionStatus.ARCHIVED: [VersionStatus.EXPERIMENTAL],
        }

        if target_status not in valid_transitions.get(old_status, []):
            raise ValueError(
                f"Cannot transition from {old_status.value} to {target_status.value}"
            )

        version.status = target_status
        self._save_registry()
        logger.info(
            f"Promoted {version_id} from {old_status.value} to {target_status.value}. Reason: {reason}"
        )
        return version

    def deploy_version(
        self,
        version_id: str,
        environment: str,
        deployed_by: str,
        metrics_before: Dict[str, float] = None,
    ) -> DeploymentRecord:
        """
        Record model deployment.

        Args:
            version_id: Version being deployed
            environment: Deployment environment (production, staging, testing)
            deployed_by: User performing deployment
            metrics_before: Metrics before deployment (for comparison)

        Returns:
            DeploymentRecord
        """
        if version_id not in self.versions:
            raise ValueError(f"Version {version_id} not found")

        version = self.versions[version_id]
        deployment = DeploymentRecord(
            version_id=version_id,
            deployed_at=datetime.utcnow().isoformat(),
            deployed_by=deployed_by,
            environment=environment,
            status="success",
            metrics_before=metrics_before or {},
            metrics_after=version.metrics.copy(),
        )

        version.deployment_history.append(deployment)
        self._save_registry()
        logger.info(f"Deployed {version_id} to {environment}")
        return deployment

    def rollback_version(
        self, version_id: str, reason: str = ""
    ) -> DeploymentRecord:
        """
        Rollback model deployment.

        Args:
            version_id: Version to rollback
            reason: Reason for rollback

        Returns:
            Updated DeploymentRecord with rollback timestamp
        """
        if version_id not in self.versions:
            raise ValueError(f"Version {version_id} not found")

        version = self.versions[version_id]
        if not version.deployment_history:
            raise ValueError(f"Version {version_id} has no deployment history")

        # Update latest deployment with rollback
        latest = version.deployment_history[-1]
        latest.status = "rolled_back"
        latest.reverted_at = datetime.utcnow().isoformat()
        latest.reason = reason

        version.status = VersionStatus.ROLLBACK
        self._save_registry()
        logger.info(f"Rolled back {version_id}. Reason: {reason}")
        return latest

    def record_ab_test(
        self,
        test_id: str,
        variant_a_version: str,
        variant_b_version: str,
        variant_a_wins: int,
        variant_b_wins: int,
        draws: int,
        statistical_significance: float,
        confidence_level: float,
        notes: str = "",
    ) -> ABTestResult:
        """
        Record A/B test result between two model versions.

        Args:
            test_id: Unique test identifier
            variant_a_version: First model version ID
            variant_b_version: Second model version ID
            variant_a_wins: Number of times variant A performed better
            variant_b_wins: Number of times variant B performed better
            draws: Number of ties
            statistical_significance: p-value from statistical test
            confidence_level: Confidence level (0-1)
            notes: Optional notes about test

        Returns:
            ABTestResult
        """
        if test_id in self.ab_tests:
            raise ValueError(f"Test {test_id} already exists")

        test = ABTestResult(
            test_id=test_id,
            variant_a_version=variant_a_version,
            variant_b_version=variant_b_version,
            variant_a_wins=variant_a_wins,
            variant_b_wins=variant_b_wins,
            draws=draws,
            statistical_significance=statistical_significance,
            confidence_level=confidence_level,
            started_at=datetime.utcnow().isoformat(),
            ended_at=datetime.utcnow().isoformat(),
            notes=notes,
        )

        self.ab_tests[test_id] = test
        # Link test to both versions
        self.versions[variant_a_version].ab_tests.append(test_id)
        self.versions[variant_b_version].ab_tests.append(test_id)
        self._save_registry()
        logger.info(f"Recorded A/B test {test_id}")
        return test

    def get_version(self, version_id: str) -> Optional[ModelVersion]:
        """Get specific model version."""
        return self.versions.get(version_id)

    def get_versions_by_status(self, status: VersionStatus) -> List[ModelVersion]:
        """Get all versions with specific status."""
        return [v for v in self.versions.values() if v.status == status]

    def get_versions_by_type(self, model_type: str) -> List[ModelVersion]:
        """Get all versions of specific model type."""
        return [v for v in self.versions.values() if v.model_type == model_type]

    def get_current_production(self) -> Optional[ModelVersion]:
        """Get currently deployed production model."""
        production = self.get_versions_by_status(VersionStatus.PRODUCTION)
        if not production:
            return None
        # Return most recently deployed
        return max(
            production,
            key=lambda v: v.deployment_history[-1].deployed_at
            if v.deployment_history
            else v.created_at,
        )

    def compare_versions(
        self, version_ids: List[str], metrics_to_compare: List[str] = None
    ) -> Dict[str, Any]:
        """
        Compare metrics across multiple versions.

        Args:
            version_ids: List of version IDs to compare
            metrics_to_compare: Specific metrics to compare (all if None)

        Returns:
            Comparison dict with side-by-side metrics
        """
        comparison = {
            "versions": [],
            "metrics_compared": metrics_to_compare or [],
            "best_version": None,
            "comparison_data": {},
        }

        for vid in version_ids:
            if vid not in self.versions:
                logger.warning(f"Version {vid} not found")
                continue

            version = self.versions[vid]
            metrics = version.metrics

            if metrics_to_compare:
                metrics = {
                    k: v for k, v in metrics.items() if k in metrics_to_compare
                }

            comparison["versions"].append(
                {
                    "version_id": vid,
                    "type": version.model_type,
                    "status": version.status.value,
                    "created_at": version.created_at,
                    "metrics": metrics,
                }
            )
            comparison["comparison_data"][vid] = metrics

        # Find best version by F1 score (or first metric)
        if comparison["versions"]:
            best_metric = metrics_to_compare[0] if metrics_to_compare else "f1"
            best = max(
                comparison["versions"],
                key=lambda v: v["metrics"].get(best_metric, 0),
                default=None,
            )
            if best:
                comparison["best_version"] = best["version_id"]

        return comparison

    def get_deployment_history(
        self, version_id: str = None, environment: str = None
    ) -> List[DeploymentRecord]:
        """Get deployment history, optionally filtered."""
        records = []
        if version_id:
            if version_id in self.versions:
                records = self.versions[version_id].deployment_history
        else:
            for version in self.versions.values():
                records.extend(version.deployment_history)

        if environment:
            records = [r for r in records if r.environment == environment]

        return sorted(records, key=lambda r: r.deployed_at, reverse=True)

    def get_ab_test(self, test_id: str) -> Optional[ABTestResult]:
        """Get A/B test result."""
        return self.ab_tests.get(test_id)

    def list_versions(self, limit: int = None) -> List[ModelVersion]:
        """List all versions, optionally limited."""
        versions = sorted(
            self.versions.values(), key=lambda v: v.created_at, reverse=True
        )
        return versions[:limit] if limit else versions

    def generate_registry_report(self) -> str:
        """Generate human-readable registry report."""
        lines = [
            "=" * 80,
            "MODEL REGISTRY REPORT",
            "=" * 80,
            f"Total Versions: {len(self.versions)}",
            f"Total A/B Tests: {len(self.ab_tests)}",
            "",
        ]

        for status in VersionStatus:
            versions = self.get_versions_by_status(status)
            lines.append(f"{status.value.upper()} ({len(versions)})")
            for v in versions:
                lines.append(f"  • {v.version_id} ({v.model_type})")
                if v.metrics:
                    lines.append(
                        f"    Metrics: {', '.join(f'{k}={v:.4f}' for k, v in list(v.metrics.items())[:3])}"
                    )
                if v.deployment_history:
                    latest_deploy = v.deployment_history[-1]
                    lines.append(f"    Last deployed: {latest_deploy.deployed_at}")

        lines.extend(["", "=" * 80])
        return "\n".join(lines)
