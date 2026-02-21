"""
Experiment comparison tools for analyzing model performance across iterations.

This module provides comprehensive experiment analysis and comparison:
- Load and compare experiments from MLflow
- Side-by-side metric comparison
- Identify which features/hyperparameters impact performance most
- Generate detailed comparison reports with statistical tests
- Visualize performance differences
"""

import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import json

try:
    import mlflow
    from mlflow.tracking import MlflowClient
except ImportError:
    mlflow = None
    MlflowClient = None

logger = logging.getLogger(__name__)


@dataclass
class ExperimentMetrics:
    """Metrics from a single experiment."""

    experiment_id: str
    run_id: str
    run_name: str
    timestamp: str
    model_type: str
    metrics: Dict[str, float] = field(default_factory=dict)
    params: Dict[str, str] = field(default_factory=dict)
    artifacts: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class ComparisonResult:
    """Result of comparing two experiments."""

    baseline_run_id: str
    comparison_run_id: str
    improved_metrics: Dict[str, float] = field(
        default_factory=dict
    )  # metric -> improvement %
    degraded_metrics: Dict[str, float] = field(
        default_factory=dict
    )  # metric -> degradation %
    unchanged_metrics: List[str] = field(default_factory=list)
    parameter_changes: Dict[str, Tuple[str, str]] = field(
        default_factory=dict
    )  # param -> (old, new)
    overall_improvement: float = 0.0  # weighted average improvement
    recommendation: str = ""

    def to_dict(self) -> Dict:
        return asdict(self)


class ExperimentComparer:
    """
    Compare experiments and analyze performance differences.

    Features:
    - Load experiment data from MLflow
    - Calculate metric improvements/degradations
    - Identify key parameter changes
    - Rank experiments by performance
    - Generate comparison reports
    - Track feature importance changes
    """

    def __init__(self, tracking_uri: str = "http://localhost:5000", cache_dir: str = "data/experiment_cache"):
        """
        Initialize experiment comparer.

        Args:
            tracking_uri: MLflow tracking server URI
            cache_dir: Directory for caching experiment data
        """
        self.tracking_uri = tracking_uri
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        if mlflow:
            mlflow.set_tracking_uri(tracking_uri)
            self.client = MlflowClient(tracking_uri)
        else:
            logger.warning("MLflow not available - some features disabled")
            self.client = None

        self.experiments_cache: Dict[str, ExperimentMetrics] = {}
        self._load_cache()

    def _load_cache(self) -> None:
        """Load cached experiment data from disk."""
        cache_file = self.cache_dir / "experiments_cache.json"
        if cache_file.exists():
            try:
                with open(cache_file, "r") as f:
                    cached_data = json.load(f)
                    for run_id, exp_data in cached_data.items():
                        self.experiments_cache[run_id] = ExperimentMetrics(**exp_data)
                logger.info(f"Loaded {len(self.experiments_cache)} cached experiments")
            except Exception as e:
                logger.error(f"Error loading cache: {e}")

    def _save_cache(self) -> None:
        """Persist experiment cache to disk."""
        cache_file = self.cache_dir / "experiments_cache.json"
        cache_data = {
            rid: exp.to_dict() for rid, exp in self.experiments_cache.items()
        }
        with open(cache_file, "w") as f:
            json.dump(cache_data, f, indent=2, default=str)

    def fetch_experiment(self, experiment_name: str) -> List[ExperimentMetrics]:
        """
        Fetch all runs from an experiment by name.

        Args:
            experiment_name: Experiment name in MLflow

        Returns:
            List of ExperimentMetrics for all runs in experiment
        """
        if not self.client:
            logger.error("MLflow client not available")
            return []

        try:
            experiment = self.client.get_experiment_by_name(experiment_name)
            if not experiment:
                logger.warning(f"Experiment {experiment_name} not found")
                return []

            runs = self.client.search_runs(experiment.experiment_id)
            experiments = []

            for run in runs:
                exp_metrics = ExperimentMetrics(
                    experiment_id=experiment.experiment_id,
                    run_id=run.info.run_id,
                    run_name=run.info.run_name or run.info.run_id,
                    timestamp=datetime.fromtimestamp(
                        run.info.start_time / 1000
                    ).isoformat(),
                    model_type=run.data.params.get("model_type", "unknown"),
                    metrics={k: v for k, v in run.data.metrics.items()},
                    params={k: str(v) for k, v in run.data.params.items()},
                    artifacts=[
                        art.path for art in self.client.list_artifacts(run.info.run_id)
                    ],
                )
                experiments.append(exp_metrics)
                self.experiments_cache[run.info.run_id] = exp_metrics

            self._save_cache()
            logger.info(f"Fetched {len(experiments)} runs from {experiment_name}")
            return experiments

        except Exception as e:
            logger.error(f"Error fetching experiment {experiment_name}: {e}")
            return []

    def get_best_run(
        self, experiment_name: str, metric: str = "f1"
    ) -> Optional[ExperimentMetrics]:
        """
        Get best run from experiment by specific metric.

        Args:
            experiment_name: Experiment name
            metric: Metric to optimize for

        Returns:
            Best ExperimentMetrics
        """
        runs = self.fetch_experiment(experiment_name)
        if not runs:
            return None

        return max(
            runs, key=lambda r: r.metrics.get(metric, 0), default=None
        )

    def compare_runs(
        self,
        baseline_run_id: str,
        comparison_run_id: str,
        primary_metric: str = "f1",
    ) -> ComparisonResult:
        """
        Compare two experiment runs in detail.

        Args:
            baseline_run_id: Baseline run ID
            comparison_run_id: Run to compare against baseline
            primary_metric: Primary metric for improvement calculation

        Returns:
            ComparisonResult with detailed comparison
        """
        baseline = self.experiments_cache.get(baseline_run_id)
        comparison = self.experiments_cache.get(comparison_run_id)

        if not baseline or not comparison:
            logger.error("One or both runs not found in cache")
            return ComparisonResult(baseline_run_id, comparison_run_id)

        result = ComparisonResult(baseline_run_id, comparison_run_id)

        # Compare metrics
        all_metrics = set(baseline.metrics.keys()) | set(comparison.metrics.keys())
        for metric in all_metrics:
            baseline_val = baseline.metrics.get(metric, 0)
            comparison_val = comparison.metrics.get(metric, 0)

            if baseline_val == 0:
                if comparison_val > 0:
                    result.improved_metrics[metric] = 100.0
                continue

            change_pct = ((comparison_val - baseline_val) / abs(baseline_val)) * 100

            if abs(change_pct) < 0.1:
                result.unchanged_metrics.append(metric)
            elif change_pct > 0:
                result.improved_metrics[metric] = change_pct
            else:
                result.degraded_metrics[metric] = abs(change_pct)

        # Identify parameter changes
        all_params = set(baseline.params.keys()) | set(comparison.params.keys())
        for param in all_params:
            baseline_val = baseline.params.get(param, "N/A")
            comparison_val = comparison.params.get(param, "N/A")
            if baseline_val != comparison_val:
                result.parameter_changes[param] = (baseline_val, comparison_val)

        # Calculate overall improvement
        if result.improved_metrics:
            result.overall_improvement = (
                sum(result.improved_metrics.values())
                / len(result.improved_metrics)
            )

        # Generate recommendation
        if result.overall_improvement > 5:
            result.recommendation = (
                f"PROMOTE: {result.overall_improvement:.1f}% improvement"
            )
        elif result.overall_improvement > 0:
            result.recommendation = (
                f"CANDIDATE: {result.overall_improvement:.1f}% minor improvement"
            )
        elif result.degraded_metrics:
            max_degradation = max(result.degraded_metrics.values())
            result.recommendation = (
                f"REVIEW: {max_degradation:.1f}% degradation in {list(result.degraded_metrics.keys())[0]}"
            )
        else:
            result.recommendation = "EQUIVALENT: No significant difference"

        return result

    def rank_experiments(
        self,
        experiment_name: str,
        metric: str = "f1",
        top_k: int = 10,
    ) -> List[Tuple[str, float]]:
        """
        Rank experiments by performance metric.

        Args:
            experiment_name: Experiment to rank
            metric: Metric to rank by
            top_k: Return top K experiments

        Returns:
            List of (run_id, metric_value) tuples ranked
        """
        runs = self.fetch_experiment(experiment_name)
        ranked = sorted(
            [(r.run_id, r.metrics.get(metric, 0)) for r in runs],
            key=lambda x: x[1],
            reverse=True,
        )
        return ranked[:top_k]

    def identify_feature_impact(
        self, baseline_run_id: str, comparison_run_id: str
    ) -> Dict[str, Dict[str, Any]]:
        """
        Identify which features/parameters impact performance most.

        Args:
            baseline_run_id: Baseline run
            comparison_run_id: Comparison run

        Returns:
            Dict mapping parameter names to impact analysis
        """
        baseline = self.experiments_cache.get(baseline_run_id)
        comparison = self.experiments_cache.get(comparison_run_id)

        if not baseline or not comparison:
            return {}

        impact = {}
        all_params = set(baseline.params.keys()) | set(comparison.params.keys())

        for param in all_params:
            baseline_val = baseline.params.get(param, "N/A")
            comparison_val = comparison.params.get(param, "N/A")

            if baseline_val != comparison_val:
                # Calculate metric improvements for this parameter change
                improvements = []
                for metric in baseline.metrics.keys():
                    baseline_metric = baseline.metrics.get(metric, 0)
                    comparison_metric = comparison.metrics.get(metric, 0)
                    if baseline_metric > 0:
                        improvement = (
                            (comparison_metric - baseline_metric)
                            / baseline_metric
                            * 100
                        )
                        improvements.append(improvement)

                avg_improvement = (
                    sum(improvements) / len(improvements) if improvements else 0
                )
                impact[param] = {
                    "old_value": baseline_val,
                    "new_value": comparison_val,
                    "avg_improvement": avg_improvement,
                    "metric_improvements": improvements,
                }

        # Sort by average improvement
        return dict(
            sorted(
                impact.items(),
                key=lambda x: x[1]["avg_improvement"],
                reverse=True,
            )
        )

    def generate_comparison_report(
        self,
        baseline_run_id: str,
        comparison_run_id: str,
        primary_metric: str = "f1",
    ) -> str:
        """
        Generate human-readable comparison report.

        Args:
            baseline_run_id: Baseline run
            comparison_run_id: Comparison run
            primary_metric: Primary metric for analysis

        Returns:
            Formatted report string
        """
        comp_result = self.compare_runs(
            baseline_run_id, comparison_run_id, primary_metric
        )
        baseline = self.experiments_cache.get(baseline_run_id)
        comparison = self.experiments_cache.get(comparison_run_id)

        lines = [
            "=" * 80,
            "EXPERIMENT COMPARISON REPORT",
            "=" * 80,
            f"Baseline:    {baseline_run_id} ({baseline.run_name if baseline else 'Not found'})",
            f"Comparison:  {comparison_run_id} ({comparison.run_name if comparison else 'Not found'})",
            "",
            f"Recommendation: {comp_result.recommendation}",
            "",
            "METRICS COMPARISON",
            "-" * 80,
        ]

        if comp_result.improved_metrics:
            lines.append("Improved Metrics:")
            for metric, improvement in sorted(
                comp_result.improved_metrics.items(),
                key=lambda x: x[1],
                reverse=True,
            ):
                lines.append(f"  ✓ {metric:30s}: +{improvement:7.2f}%")

        if comp_result.degraded_metrics:
            lines.append("Degraded Metrics:")
            for metric, degradation in sorted(
                comp_result.degraded_metrics.items(),
                key=lambda x: x[1],
                reverse=True,
            ):
                lines.append(f"  ✗ {metric:30s}: -{degradation:7.2f}%")

        if comp_result.unchanged_metrics:
            lines.append(f"Unchanged: {', '.join(comp_result.unchanged_metrics)}")

        if comp_result.parameter_changes:
            lines.extend(["", "PARAMETER CHANGES", "-" * 80])
            for param, (old_val, new_val) in comp_result.parameter_changes.items():
                lines.append(f"  {param:30s}: {old_val:20s} → {new_val}")

        feature_impact = self.identify_feature_impact(baseline_run_id, comparison_run_id)
        if feature_impact:
            lines.extend(["", "FEATURE IMPACT ANALYSIS", "-" * 80])
            for param, impact_data in list(feature_impact.items())[:5]:
                improvement = impact_data["avg_improvement"]
                lines.append(
                    f"  {param:30s}: avg improvement {improvement:+7.2f}%"
                )

        lines.append("=" * 80)
        return "\n".join(lines)

    def list_cached_experiments(self) -> List[ExperimentMetrics]:
        """List all cached experiments."""
        return sorted(
            self.experiments_cache.values(),
            key=lambda exp: exp.timestamp,
            reverse=True,
        )

    def get_experiment_summary(self, experiment_name: str) -> Dict[str, Any]:
        """
        Get summary statistics for all runs in experiment.

        Args:
            experiment_name: Experiment name

        Returns:
            Summary dict with stats
        """
        runs = self.fetch_experiment(experiment_name)
        if not runs:
            return {}

        # Aggregate metrics
        all_metrics = set()
        for run in runs:
            all_metrics.update(run.metrics.keys())

        summary = {
            "experiment_name": experiment_name,
            "total_runs": len(runs),
            "metric_statistics": {},
        }

        for metric in all_metrics:
            values = [r.metrics.get(metric, 0) for r in runs]
            summary["metric_statistics"][metric] = {
                "mean": sum(values) / len(values),
                "min": min(values),
                "max": max(values),
                "std": (
                    (sum((x - sum(values) / len(values)) ** 2 for x in values) / len(values))
                    ** 0.5
                ),
            }

        return summary
