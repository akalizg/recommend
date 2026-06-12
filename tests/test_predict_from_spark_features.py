from __future__ import annotations

import importlib

import pandas as pd
import pytest


def test_predict_from_spark_features_importable():
    module = importlib.import_module("rank.predict_from_spark_features")
    assert hasattr(module, "predict_from_spark_features")


def test_predict_from_spark_features_outputs(tmp_path):
    pytest.importorskip("xgboost")

    from rank.predict_from_spark_features import DEFAULT_CANDIDATES, predict_from_spark_features
    from rank.train_from_spark_features import DEFAULT_FEATURES, DEFAULT_TRAIN, train_from_spark_features

    if not DEFAULT_TRAIN.exists() or not DEFAULT_FEATURES.exists() or not DEFAULT_CANDIDATES.exists():
        pytest.skip("Spark rank feature files have not been generated yet.")

    model_output = tmp_path / "models" / "xgb_rank_model_spark.json"
    model_features_output = tmp_path / "models" / "xgb_rank_feature_columns.json"
    metrics_output = tmp_path / "rank" / "xgb_train_metrics.json"
    importance_output = tmp_path / "rank" / "xgb_feature_importance.csv"
    output = tmp_path / "rank" / "ranked_top50.csv"

    train_from_spark_features(
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
    summary = predict_from_spark_features(DEFAULT_CANDIDATES, model_output, model_features_output, output, top_n=50)
    assert summary["ranked_rows"] > 0
    assert output.exists()

    ranked = pd.read_csv(output)
    required = {
        "userId",
        "movieId",
        "rank_position",
        "rank_score",
        "label",
        "als_score",
        "itemcf_score",
        "merged_recall_score",
        "recall_source_count",
        "genre_match_score",
        "movie_avg_rating",
        "movie_popularity",
    }
    assert required.issubset(ranked.columns)
    assert ranked.groupby("userId").size().max() <= 50
    assert ranked["rank_score"].between(0, 1).all()
    assert ranked.groupby("userId")["rank_position"].min().eq(1).all()
