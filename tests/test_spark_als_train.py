from __future__ import annotations

import importlib
from pathlib import Path

import pandas as pd
import pytest


def _feature_dim(value: str) -> int:
    return len(str(value).split("|"))


def test_spark_als_train_importable():
    module = importlib.import_module("spark_jobs.spark_als_train")
    assert hasattr(module, "train_als")


def test_spark_als_train_outputs(tmp_path):
    pytest.importorskip("pyspark")

    from spark_jobs.spark_als_train import DEFAULT_TRAIN, train_als

    factors_dir = tmp_path / "factors"
    recall_dir = tmp_path / "recall"
    model_dir = tmp_path / "spark_als"

    summary = train_als(
        DEFAULT_TRAIN,
        factors_dir,
        recall_dir,
        model_dir,
        rank=16,
        max_iter=3,
        reg_param=0.1,
        top_n=20,
    )
    assert summary["user_factor_rows"] > 0
    assert summary["movie_factor_rows"] > 0
    assert summary["als_recall_rows"] > 0

    user_factors = pd.read_csv(factors_dir / "user_factors.csv")
    movie_factors = pd.read_csv(factors_dir / "movie_factors.csv")
    als_recall = pd.read_csv(recall_dir / "als_recall.csv")

    assert not user_factors.empty
    assert not movie_factors.empty
    assert user_factors["features"].map(_feature_dim).nunique() == 1
    assert movie_factors["features"].map(_feature_dim).nunique() == 1
    assert movie_factors["features"].map(_feature_dim).iloc[0] == 16
    assert set(als_recall["recall_type"].unique()) == {"als"}
    assert als_recall.groupby("userId").size().max() <= 20
