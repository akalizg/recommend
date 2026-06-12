"""
Lightweight tests for spark_jobs/spark_preprocess.py.

The processing test is skipped when pyspark is not installed so the regular
project test suite remains usable in non-Spark environments.
"""
from __future__ import annotations

import importlib
from pathlib import Path

import pandas as pd
import pytest


def test_spark_preprocess_importable():
    module = importlib.import_module("spark_jobs.spark_preprocess")
    assert hasattr(module, "preprocess")
    assert hasattr(module, "detect_input_dir")


def test_spark_preprocess_outputs_default_files():
    pytest.importorskip("pyspark")

    from spark_jobs.spark_preprocess import DEFAULT_INPUT_DIR, DEFAULT_OUTPUT_DIR, preprocess

    summary = preprocess(DEFAULT_INPUT_DIR, DEFAULT_OUTPUT_DIR)
    assert summary["files_written"] is True

    ratings_path = Path(DEFAULT_OUTPUT_DIR) / "ratings_clean.csv"
    movies_path = Path(DEFAULT_OUTPUT_DIR) / "movies_clean.csv"
    tags_path = Path(DEFAULT_OUTPUT_DIR) / "movie_tags.csv"

    assert ratings_path.exists()
    assert movies_path.exists()
    assert tags_path.exists()

    ratings_columns = set(pd.read_csv(ratings_path, nrows=1).columns)
    movies_columns = set(pd.read_csv(movies_path, nrows=1).columns)
    tags_columns = set(pd.read_csv(tags_path, nrows=1).columns)

    assert {"userId", "movieId", "rating", "rating_norm", "timestamp"}.issubset(ratings_columns)
    assert {"movieId", "title", "clean_title", "year", "genres", "genre_count"}.issubset(movies_columns)
    assert {"movieId", "tag", "tag_type"}.issubset(tags_columns)
