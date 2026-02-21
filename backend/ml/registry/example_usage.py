"""
Example usage of Model Registry and Experiment Comparison.

This demonstrates practical workflows for managing and comparing ML models in production.
"""

from backend.ml.registry import ModelRegistry, VersionStatus
from backend.ml.tracking.experiment_compare import ExperimentComparer, ExperimentMetrics
from datetime import datetime


def example_model_registry_workflow():
    """Demonstrate complete model registry workflow."""
    print("=" * 80)
    print("MODEL REGISTRY WORKFLOW EXAMPLE")
    print("=" * 80)

    # Initialize registry
    registry = ModelRegistry(registry_dir="data/models/registry")

    # 1. Register initial model
    print("\n1. Registering baseline model...")
    baseline = registry.register_version(
        version_id="v1.0.0",
        model_type="xgboost",
        feature_snapshot_id="snap_20260220_001",
        mlflow_run_id="mlflow_abc123",
        model_path="/models/xgboost_v1.pkl",
        metrics={
            "accuracy": 0.92,
            "f1": 0.88,
            "sharpe": 1.2,
            "max_drawdown": -0.15,
            "win_rate": 0.58,
        },
        hyperparameters={"max_depth": 5, "learning_rate": 0.1, "n_estimators": 100},
        feature_importance={"rsi": 0.18, "macd": 0.15, "sma_cross": 0.12},
        training_config={"batch_size": 32, "epochs": 100, "cv_folds": 5},
        created_by="data_scientist_alice",
        notes="Initial baseline model trained on Phase 1 data",
        tags=["baseline", "production-ready"],
    )
    print(f"✓ Registered {baseline.version_id} ({baseline.model_type})")
    print(f"  Metrics: accuracy={baseline.metrics['accuracy']:.3f}, f1={baseline.metrics['f1']:.3f}")

    # 2. Register improved version
    print("\n2. Registering improved model...")
    improved = registry.register_version(
        version_id="v1.1.0",
        model_type="xgboost",
        feature_snapshot_id="snap_20260220_002",
        mlflow_run_id="mlflow_xyz789",
        model_path="/models/xgboost_v1.1.pkl",
        metrics={
            "accuracy": 0.94,
            "f1": 0.91,
            "sharpe": 1.5,
            "max_drawdown": -0.12,
            "win_rate": 0.62,
        },
        hyperparameters={"max_depth": 7, "learning_rate": 0.05, "n_estimators": 150},
        feature_importance={"rsi": 0.20, "macd": 0.17, "sma_cross": 0.14},
        training_config={"batch_size": 32, "epochs": 120, "cv_folds": 5},
        created_by="data_scientist_bob",
        notes="Improved model with hyperparameter tuning and additional features",
        tags=["tuned", "candidate"],
    )
    print(f"✓ Registered {improved.version_id} ({improved.model_type})")
    print(f"  Metrics: accuracy={improved.metrics['accuracy']:.3f}, f1={improved.metrics['f1']:.3f}")

    # 3. Compare versions
    print("\n3. Comparing model versions...")
    comparison = registry.compare_versions(
        ["v1.0.0", "v1.1.0"], metrics_to_compare=["accuracy", "f1", "sharpe"]
    )
    print(f"  Best performer: {comparison['best_version']}")
    for version_data in comparison["versions"]:
        print(
            f"  {version_data['version_id']}: accuracy={version_data['metrics']['accuracy']:.3f}"
        )

    # 4. Promote through states
    print("\n4. Promoting v1.1.0 through deployment states...")
    registry.promote_version("v1.1.0", VersionStatus.STAGING, reason="Passed all validation tests")
    print("  ✓ Promoted to STAGING")
    registry.promote_version("v1.1.0", VersionStatus.PRODUCTION, reason="Approved by ML director")
    print("  ✓ Promoted to PRODUCTION")

    # 5. Deploy to production
    print("\n5. Deploying to production environment...")
    deployment = registry.deploy_version(
        "v1.1.0",
        environment="production",
        deployed_by="devops_charlie",
        metrics_before={"accuracy": 0.92, "f1": 0.88, "sharpe": 1.2},
    )
    print(f"  ✓ Deployed at {deployment.deployed_at}")
    print(f"  Metrics before: accuracy={deployment.metrics_before['accuracy']:.3f}")
    print(f"  Metrics after:  accuracy={deployment.metrics_after['accuracy']:.3f}")

    # 6. Record A/B test
    print("\n6. Recording A/B test results...")
    ab_test = registry.record_ab_test(
        test_id="ab_test_20260220_001",
        variant_a_version="v1.0.0",
        variant_b_version="v1.1.0",
        variant_a_wins=45,
        variant_b_wins=55,
        draws=0,
        statistical_significance=0.02,
        confidence_level=0.95,
        notes="A/B test on real trading data, statistically significant improvement",
    )
    print(f"  ✓ A/B Test recorded: {ab_test.test_id}")
    print(f"  Winner: {ab_test.winner()} (p-value={ab_test.statistical_significance:.3f})")

    # 7. List all versions
    print("\n7. Current model versions in registry...")
    all_versions = registry.list_versions()
    print(f"  Total versions: {len(all_versions)}")
    for v in all_versions:
        print(f"  - {v.version_id}: {v.status.value} (created: {v.created_at[:10]})")

    # 8. Query by status
    print("\n8. Production models:")
    prod_models = registry.get_versions_by_status(VersionStatus.PRODUCTION)
    if prod_models:
        current_prod = registry.get_current_production()
        print(f"  Current production: {current_prod.version_id}")
        print(f"  Deployed at: {current_prod.deployment_history[-1].deployed_at}")

    # 9. Generate report
    print("\n9. Registry status report:")
    report = registry.generate_registry_report()
    print(report)


def example_experiment_comparison_workflow():
    """Demonstrate experiment comparison workflow."""
    print("\n" + "=" * 80)
    print("EXPERIMENT COMPARISON WORKFLOW EXAMPLE")
    print("=" * 80)

    # Initialize comparer
    comparer = ExperimentComparer(cache_dir="data/experiment_cache")

    # 1. Create experiment metrics (in real scenario, would fetch from MLflow)
    print("\n1. Creating experiment metrics...")
    baseline_metrics = ExperimentMetrics(
        experiment_id="exp_001",
        run_id="run_baseline_001",
        run_name="XGBoost Baseline",
        timestamp=datetime.utcnow().isoformat(),
        model_type="xgboost",
        metrics={
            "accuracy": 0.90,
            "f1": 0.87,
            "precision": 0.88,
            "recall": 0.86,
            "sharpe": 1.2,
        },
        params={
            "max_depth": "5",
            "learning_rate": "0.1",
            "n_estimators": "100",
            "subsample": "0.8",
        },
        artifacts=["model.pkl", "feature_importance.json", "training_log.txt"],
    )
    comparer.experiments_cache["run_baseline_001"] = baseline_metrics
    print(f"  ✓ Baseline run: {baseline_metrics.run_name}")

    improved_metrics = ExperimentMetrics(
        experiment_id="exp_001",
        run_id="run_tuned_001",
        run_name="XGBoost Tuned v2",
        timestamp=datetime.utcnow().isoformat(),
        model_type="xgboost",
        metrics={
            "accuracy": 0.93,
            "f1": 0.91,
            "precision": 0.92,
            "recall": 0.90,
            "sharpe": 1.5,
        },
        params={
            "max_depth": "7",
            "learning_rate": "0.05",
            "n_estimators": "150",
            "subsample": "0.9",
        },
        artifacts=["model.pkl", "feature_importance.json", "training_log.txt"],
    )
    comparer.experiments_cache["run_tuned_001"] = improved_metrics
    print(f"  ✓ Improved run: {improved_metrics.run_name}")

    # 2. Compare runs
    print("\n2. Comparing experiments...")
    comparison = comparer.compare_runs("run_baseline_001", "run_tuned_001")
    print(f"  Overall improvement: {comparison.overall_improvement:.2f}%")
    print(f"  Recommendation: {comparison.recommendation}")

    # 3. Show improvement breakdown
    print("\n3. Metric improvements:")
    for metric, improvement in sorted(
        comparison.improved_metrics.items(), key=lambda x: x[1], reverse=True
    ):
        print(f"  ✓ {metric:20s}: +{improvement:6.2f}%")

    # 4. Show parameter changes
    print("\n4. Parameter changes:")
    for param, (old_val, new_val) in comparison.parameter_changes.items():
        print(f"  {param:20s}: {old_val:15s} → {new_val}")

    # 5. Identify feature impact
    print("\n5. Feature impact analysis:")
    feature_impact = comparer.identify_feature_impact("run_baseline_001", "run_tuned_001")
    for param, impact_data in list(feature_impact.items())[:3]:
        improvement = impact_data["avg_improvement"]
        print(f"  {param:20s}: avg improvement {improvement:+7.2f}%")

    # 6. Generate report
    print("\n6. Detailed comparison report:")
    report = comparer.generate_comparison_report("run_baseline_001", "run_tuned_001")
    print(report)

    # 7. Save cache
    print("\n7. Saving experiment cache...")
    comparer._save_cache()
    print("  ✓ Cache saved to disk for later analysis")


def example_integrated_workflow():
    """Demonstrate integrated registry and comparison workflow."""
    print("\n" + "=" * 80)
    print("INTEGRATED MODEL MANAGEMENT WORKFLOW")
    print("=" * 80)

    registry = ModelRegistry(registry_dir="data/models/registry")
    comparer = ExperimentComparer(cache_dir="data/experiment_cache")

    # Scenario: After running A/B tests, promote winner and retire loser
    print("\n1. Testing two candidates against production...")
    print("   Collecting A/B test results over 7 days...")

    # Record test results
    test_results = registry.record_ab_test(
        test_id="week1_ab_test",
        variant_a_version="v1.0.0",  # current production
        variant_b_version="v1.1.0",  # candidate
        variant_a_wins=110,
        variant_b_wins=130,
        draws=10,
        statistical_significance=0.01,
        confidence_level=0.99,
        notes="Significant outperformance on live trading data",
    )

    print(f"   Results: Variant B wins with p={test_results.statistical_significance:.3f}")
    print(f"   Winner: {test_results.winner()}")

    # Promote winner
    print("\n2. Promoting winner to production...")
    registry.promote_version(
        "v1.1.0", VersionStatus.PRODUCTION, reason="Won A/B test with statistical significance"
    )
    registry.deploy_version("v1.1.0", environment="production", deployed_by="ml_ops")
    print("   ✓ v1.1.0 now in production")

    # Retire previous production
    print("\n3. Archiving previous production model...")
    registry.promote_version(
        "v1.0.0", VersionStatus.ARCHIVED, reason="Replaced by v1.1.0 after successful A/B test"
    )
    print("   ✓ v1.0.0 archived for record-keeping")

    # Report
    print("\n4. Updated registry status:")
    prod = registry.get_current_production()
    print(f"   Current production: {prod.version_id}")
    print(f"   Model type: {prod.model_type}")
    print(f"   Performance metrics: accuracy={prod.metrics.get('accuracy', 'N/A')}")


if __name__ == "__main__":
    # Run examples
    example_model_registry_workflow()
    example_experiment_comparison_workflow()
    example_integrated_workflow()

    print("\n" + "=" * 80)
    print("EXAMPLES COMPLETED SUCCESSFULLY")
    print("=" * 80)
    print("\nNext steps:")
    print("1. Integrate with real MLflow experiment tracking")
    print("2. Set up automated model comparison pipelines")
    print("3. Implement model quality gates before production promotion")
    print("4. Add monitoring for deployed model performance")
