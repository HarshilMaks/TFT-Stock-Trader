"""
Feature importance tracking and analysis.

Logs feature importance post-training and identifies:
- High-impact features (importance > 1%)
- Dead features (importance < 0.1%)
- Feature contribution trends
"""

import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import json

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class FeatureImportanceRecord:
    """Single feature importance record from training."""

    feature_name: str
    importance_score: float
    importance_pct: float  # As percentage
    model_type: str  # xgboost, lightgbm, tft, lstm
    training_date: str
    experiment_id: str
    feature_group: str = ""  # sentiment, technical, volume, etc.
    rank: int = 0  # Rank among all features

    def to_dict(self) -> Dict:
        return asdict(self)

    def __post_init__(self):
        """Classify feature by group for analysis."""
        if "sentiment" in self.feature_name.lower():
            self.feature_group = "sentiment"
        elif "rsi" in self.feature_name.lower() or "macd" in self.feature_name.lower():
            self.feature_group = "technical"
        elif "volume" in self.feature_name.lower():
            self.feature_group = "volume"
        elif "sma" in self.feature_name.lower() or "ma" in self.feature_name.lower():
            self.feature_group = "moving_average"
        else:
            self.feature_group = "other"


@dataclass
class FeatureImportanceSummary:
    """Summary statistics for feature importance analysis."""

    total_features: int
    high_impact_features: List[str] = field(default_factory=list)  # > 1%
    medium_impact_features: List[str] = field(default_factory=list)  # 0.1% - 1%
    dead_features: List[str] = field(default_factory=list)  # < 0.1%
    feature_group_importance: Dict[str, float] = field(
        default_factory=dict
    )  # Group -> total %
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return asdict(self)


class FeatureImportanceTracker:
    """
    Track and analyze feature importance post-training.

    Features:
    - Log feature importance after model training
    - Identify high-impact and dead features
    - Track importance trends across experiments
    - Generate recommendations for feature engineering
    - Group features by type for analysis
    """

    def __init__(self, storage_dir: str = "data/feature_importance"):
        """
        Initialize feature importance tracker.

        Args:
            storage_dir: Directory for storing importance records
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.records_file = self.storage_dir / "importance_records.json"
        self.records: Dict[str, FeatureImportanceRecord] = {}
        self._load_records()

    def _load_records(self) -> None:
        """Load existing importance records from disk."""
        if self.records_file.exists():
            try:
                with open(self.records_file, "r") as f:
                    records_data = json.load(f)
                    self.records = {
                        rid: FeatureImportanceRecord(**rdata)
                        for rid, rdata in records_data.items()
                    }
                logger.info(f"Loaded {len(self.records)} feature importance records")
            except Exception as e:
                logger.error(f"Error loading importance records: {e}")

    def _save_records(self) -> None:
        """Persist records to disk."""
        records_data = {rid: r.to_dict() for rid, r in self.records.items()}
        with open(self.records_file, "w") as f:
            json.dump(records_data, f, indent=2, default=str)

    def log_feature_importance(
        self,
        feature_importance_dict: Dict[str, float],
        model_type: str,
        experiment_id: str,
        training_date: Optional[str] = None,
    ) -> List[FeatureImportanceRecord]:
        """
        Log feature importance from trained model.

        Args:
            feature_importance_dict: Dict mapping feature names to importance scores
            model_type: Type of model (xgboost, lightgbm, tft, lstm)
            experiment_id: Experiment ID from MLflow
            training_date: Training date (uses current time if not provided)

        Returns:
            List of FeatureImportanceRecord objects created
        """
        if not training_date:
            training_date = datetime.utcnow().isoformat()

        # Normalize importance scores to sum to 100%
        total_importance = sum(feature_importance_dict.values())
        if total_importance == 0:
            logger.warning("Total importance is 0, skipping logging")
            return []

        records = []
        for rank, (feature_name, importance_score) in enumerate(
            sorted(feature_importance_dict.items(), key=lambda x: x[1], reverse=True), 1
        ):
            importance_pct = (importance_score / total_importance) * 100

            record_id = f"{experiment_id}_{feature_name}"
            record = FeatureImportanceRecord(
                feature_name=feature_name,
                importance_score=importance_score,
                importance_pct=importance_pct,
                model_type=model_type,
                training_date=training_date,
                experiment_id=experiment_id,
                rank=rank,
            )

            self.records[record_id] = record
            records.append(record)

        self._save_records()
        logger.info(f"Logged {len(records)} feature importance records for {experiment_id}")
        return records

    def get_feature_summary(
        self, experiment_id: str
    ) -> Optional[FeatureImportanceSummary]:
        """
        Get summary analysis for experiment features.

        Args:
            experiment_id: Experiment ID

        Returns:
            FeatureImportanceSummary or None if not found
        """
        # Get all records for this experiment
        exp_records = [
            r for r in self.records.values() if r.experiment_id == experiment_id
        ]

        if not exp_records:
            logger.warning(f"No records found for experiment {experiment_id}")
            return None

        summary = FeatureImportanceSummary(total_features=len(exp_records))

        # Categorize by impact level
        for record in exp_records:
            if record.importance_pct > 1.0:
                summary.high_impact_features.append(
                    f"{record.feature_name} ({record.importance_pct:.2f}%)"
                )
            elif record.importance_pct > 0.1:
                summary.medium_impact_features.append(
                    f"{record.feature_name} ({record.importance_pct:.2f}%)"
                )
            else:
                summary.dead_features.append(
                    f"{record.feature_name} ({record.importance_pct:.3f}%)"
                )

        # Group importance by feature group
        group_totals: Dict[str, float] = {}
        for record in exp_records:
            if record.feature_group not in group_totals:
                group_totals[record.feature_group] = 0.0
            group_totals[record.feature_group] += record.importance_pct

        summary.feature_group_importance = group_totals

        # Generate recommendations
        summary.recommendations = self._generate_recommendations(summary)

        return summary

    def _generate_recommendations(
        self, summary: FeatureImportanceSummary
    ) -> List[str]:
        """Generate recommendations based on feature importance."""
        recommendations = []

        # Dead features recommendation
        if len(summary.dead_features) > 5:
            recommendations.append(
                f"Consider removing {len(summary.dead_features)} dead features (<0.1%) to reduce complexity"
            )

        # Group dominance
        if summary.feature_group_importance:
            max_group = max(summary.feature_group_importance.items(), key=lambda x: x[1])
            if max_group[1] > 70:
                recommendations.append(
                    f"{max_group[0].upper()} features dominate ({max_group[1]:.1f}% importance) - "
                    f"consider adding more diverse feature groups"
                )

        # Feature count
        if summary.total_features > 50:
            recommendations.append(
                f"High dimensionality ({summary.total_features} features) - "
                f"consider dimensionality reduction or feature selection"
            )

        if len(summary.high_impact_features) < 5:
            recommendations.append(
                f"Few high-impact features - model relies on {len(summary.high_impact_features)} features, "
                f"consider adding more discriminative features"
            )

        return recommendations

    def compare_importance_across_experiments(
        self, experiment_ids: List[str], top_k: int = 10
    ) -> pd.DataFrame:
        """
        Compare top features across experiments.

        Args:
            experiment_ids: List of experiment IDs to compare
            top_k: Number of top features to include

        Returns:
            DataFrame with experiments as columns, top features as rows
        """
        comparison_data = {}

        for exp_id in experiment_ids:
            exp_records = [
                r for r in self.records.values() if r.experiment_id == exp_id
            ]
            exp_records = sorted(
                exp_records, key=lambda r: r.importance_pct, reverse=True
            )

            # Get top features
            for record in exp_records[:top_k]:
                if record.feature_name not in comparison_data:
                    comparison_data[record.feature_name] = {}
                comparison_data[record.feature_name][exp_id] = record.importance_pct

        # Create DataFrame with NaN for missing experiments
        df = pd.DataFrame(comparison_data).T
        df = df.fillna(0)
        return df

    def identify_emerging_features(
        self, experiment_ids: List[str], growth_threshold: float = 0.5
    ) -> Dict[str, float]:
        """
        Identify features with increasing importance.

        Args:
            experiment_ids: List of experiments in chronological order
            growth_threshold: Minimum percentage point increase

        Returns:
            Dict mapping features to growth percentage points
        """
        if len(experiment_ids) < 2:
            return {}

        first_exp = experiment_ids[0]
        last_exp = experiment_ids[-1]

        first_records = {
            r.feature_name: r.importance_pct
            for r in self.records.values()
            if r.experiment_id == first_exp
        }

        last_records = {
            r.feature_name: r.importance_pct
            for r in self.records.values()
            if r.experiment_id == last_exp
        }

        emerging = {}
        for feature_name, last_importance in last_records.items():
            first_importance = first_records.get(feature_name, 0.0)
            growth = last_importance - first_importance

            if growth >= growth_threshold:
                emerging[feature_name] = growth

        return dict(
            sorted(emerging.items(), key=lambda x: x[1], reverse=True)
        )

    def identify_declining_features(
        self, experiment_ids: List[str], decline_threshold: float = 0.5
    ) -> Dict[str, float]:
        """
        Identify features with decreasing importance.

        Args:
            experiment_ids: List of experiments in chronological order
            decline_threshold: Minimum percentage point decrease

        Returns:
            Dict mapping features to decline percentage points
        """
        if len(experiment_ids) < 2:
            return {}

        first_exp = experiment_ids[0]
        last_exp = experiment_ids[-1]

        first_records = {
            r.feature_name: r.importance_pct
            for r in self.records.values()
            if r.experiment_id == first_exp
        }

        last_records = {
            r.feature_name: r.importance_pct
            for r in self.records.values()
            if r.experiment_id == last_exp
        }

        declining = {}
        for feature_name, first_importance in first_records.items():
            last_importance = last_records.get(feature_name, 0.0)
            decline = first_importance - last_importance

            if decline >= decline_threshold:
                declining[feature_name] = decline

        return dict(
            sorted(declining.items(), key=lambda x: x[1], reverse=True)
        )

    def generate_importance_report(self, experiment_id: str) -> str:
        """Generate human-readable importance report."""
        summary = self.get_feature_summary(experiment_id)
        if not summary:
            return f"No records found for experiment {experiment_id}"

        lines = [
            "=" * 80,
            "FEATURE IMPORTANCE REPORT",
            "=" * 80,
            f"Experiment ID: {experiment_id}",
            f"Total Features: {summary.total_features}",
            "",
            "FEATURE CLASSIFICATION",
            "-" * 80,
            f"High Impact (>1%): {len(summary.high_impact_features)} features",
            f"Medium Impact (0.1%-1%): {len(summary.medium_impact_features)} features",
            f"Dead (<0.1%): {len(summary.dead_features)} features",
            "",
            "TOP HIGH-IMPACT FEATURES",
            "-" * 80,
        ]

        for feature in summary.high_impact_features[:10]:
            lines.append(f"  • {feature}")

        if summary.feature_group_importance:
            lines.extend(["", "IMPORTANCE BY FEATURE GROUP", "-" * 80])
            for group, importance in sorted(
                summary.feature_group_importance.items(), key=lambda x: x[1], reverse=True
            ):
                lines.append(f"  {group:20s}: {importance:6.2f}%")

        if summary.recommendations:
            lines.extend(["", "RECOMMENDATIONS", "-" * 80])
            for i, rec in enumerate(summary.recommendations, 1):
                lines.append(f"  {i}. {rec}")

        lines.append("=" * 80)
        return "\n".join(lines)

    def list_experiments(self) -> List[str]:
        """List all experiment IDs in tracker."""
        experiment_ids = set()
        for record in self.records.values():
            experiment_ids.add(record.experiment_id)
        return sorted(list(experiment_ids))

    def get_records_by_experiment(self, experiment_id: str) -> List[FeatureImportanceRecord]:
        """Get all importance records for an experiment."""
        return sorted(
            [r for r in self.records.values() if r.experiment_id == experiment_id],
            key=lambda r: r.importance_pct,
            reverse=True,
        )


def create_feature_importance_tracker() -> FeatureImportanceTracker:
    """Factory function to create feature importance tracker."""
    return FeatureImportanceTracker(storage_dir="data/feature_importance")
