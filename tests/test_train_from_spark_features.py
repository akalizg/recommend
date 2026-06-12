from __future__ import annotations

import importlib
import json

import pandas as pd
import pytest


def test_train_from_spark_features_importable():
    module = importlib.import_module("rank.train_from_spark_features")
    assert hasattr(module, "train_from_spark_features")


def test_train_from_spark_features_outputs(tmp_path):
    pytest.importorskip("xgboost")

    from rank.train_from_spark_features import DEFAULT_FEATURES, DEFAULT_TRAIN, train_from_spark_features

    if not DEFAULT_TRAIN.exists() or not DEFAULT_FEATURES.exists():
        pytest.skip("Spark rank feature files have not been generated yet.")

    model_output = tmp_path / "models" / "xgb_rank_model_spark.json"
    model_features_output = tmp_path / "models" / "xgb_rank_feature_columns.json"
    metrics_output = tmp_path / "rank" / "xgb_train_metrics.json"
    importance_output = tmp_path / "rank" / "xgb_feature_importance.csv"

    metrics = train_from_spark_features(
        DEFAULT_TRAIN,
        DEFAULT_FEATURES,
        model_output,
        model_features_output,
        metrics_output,
        importance_output,
        n_estimators=20,
        max_depth=3,
        learning_rate=0.08,
    )

    assert metrics["rank_train_rows"] > 0
    assert model_output.exists()
    assert model_features_output.exists()
    assert metrics_output.exists()
    assert importance_output.exists()

    saved_metrics = json.loads(metrics_output.read_text(encoding="utf-8"))
    assert "valid_auc" in saved_metrics or "valid_accuracy" in saved_metrics
    assert saved_metrics["positive_samples"] > 0
    assert saved_metrics["negative_samples"] > 0

    importance = pd.read_csv(importance_output)
    assert {"feature", "importance"}.issubset(importance.columns)
    assert not importance.empty
