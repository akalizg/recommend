from __future__ import annotations

import importlib
import json

import pandas as pd
import pytest


def test_spark_feature_export_importable():
    module = importlib.import_module("spark_jobs.spark_feature_export")
    assert hasattr(module, "export_rank_features")


def test_spark_feature_export_outputs(tmp_path):
    pytest.importorskip("pyspark")

    from spark_jobs.spark_feature_export import (
        DEFAULT_MERGED_RECALL,
        DEFAULT_MOVIE_PROFILE,
        DEFAULT_TEST_RATINGS,
        DEFAULT_TRAIN_RATINGS,
        DEFAULT_USER_PROFILE,
        export_rank_features,
    )

    output_dir = tmp_path / "rank"
    summary = export_rank_features(
        DEFAULT_USER_PROFILE,
        DEFAULT_MOVIE_PROFILE,
        DEFAULT_MERGED_RECALL,
        DEFAULT_TRAIN_RATINGS,
        DEFAULT_TEST_RATINGS,
        output_dir,
    )
    assert summary["rank_train_rows"] > 0
    assert summary["rank_candidates_rows"] > 0

    train_path = output_dir / "rank_train.csv"
    candidates_path = output_dir / "rank_candidates.csv"
    features_path = output_dir / "rank_feature_columns.json"
    assert train_path.exists()
    assert candidates_path.exists()
    assert features_path.exists()

    feature_columns = json.loads(features_path.read_text(encoding="utf-8"))
    train = pd.read_csv(train_path)
    candidates = pd.read_csv(candidates_path)

    required_base = {"userId", "movieId", "label"}
    assert required_base.issubset(train.columns)
    assert required_base.issubset(candidates.columns)
    assert set(train["label"].unique()).issubset({0, 1})
    assert set(candidates["label"].unique()).issubset({0, 1})
    assert (train["label"] == 1).any()
    assert (train["label"] == 0).any()

    for col in feature_columns:
        assert col in train.columns
        assert col in candidates.columns
        assert pd.api.types.is_numeric_dtype(train[col])
        assert pd.api.types.is_numeric_dtype(candidates[col])
