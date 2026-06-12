"""
Lightweight tests for spark_jobs/spark_train_test_split.py.

The Spark execution test is skipped when pyspark is not installed.
"""
from __future__ import annotations

import importlib
from pathlib import Path

import pandas as pd
import pytest


REQUIRED_COLUMNS = {"userId", "movieId", "rating", "rating_norm", "timestamp"}


def test_spark_train_test_split_importable():
    module = importlib.import_module("spark_jobs.spark_train_test_split")
    assert hasattr(module, "split_train_test")


def test_spark_train_test_split_outputs_and_quality():
    pytest.importorskip("pyspark")

    from spark_jobs.spark_train_test_split import DEFAULT_INPUT, DEFAULT_OUTPUT_DIR, split_train_test

    summary = split_train_test(DEFAULT_INPUT, DEFAULT_OUTPUT_DIR)
    assert summary["outputs_written"] is True
    assert summary["duplicate_exists"] is False
    assert summary["test_max_one_per_user"] is True
    assert summary["test_users_missing_from_train"] == 0

    train_path = Path(DEFAULT_OUTPUT_DIR) / "train_ratings.csv"
    test_path = Path(DEFAULT_OUTPUT_DIR) / "test_ratings.csv"

    assert train_path.exists()
    assert test_path.exists()

    train = pd.read_csv(train_path)
    test = pd.read_csv(test_path)

    assert REQUIRED_COLUMNS.issubset(set(train.columns))
    assert REQUIRED_COLUMNS.issubset(set(test.columns))

    assert test.groupby("userId").size().max() <= 1
    assert set(test["userId"]).issubset(set(train["userId"]))

    train_keys = set(map(tuple, train[["userId", "movieId", "timestamp"]].to_numpy()))
    test_keys = set(map(tuple, test[["userId", "movieId", "timestamp"]].to_numpy()))
    assert train_keys.isdisjoint(test_keys)
