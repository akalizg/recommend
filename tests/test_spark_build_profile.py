from __future__ import annotations

import importlib
from pathlib import Path

import pandas as pd
import pytest


def test_spark_build_profile_importable():
    module = importlib.import_module("spark_jobs.spark_build_profile")
    assert hasattr(module, "build_profiles")


def test_spark_build_profile_outputs(tmp_path):
    pytest.importorskip("pyspark")

    from spark_jobs.spark_build_profile import DEFAULT_MOVIES, DEFAULT_TAGS, DEFAULT_TRAIN, build_profiles

    output_dir = tmp_path / "features"
    summary = build_profiles(DEFAULT_TRAIN, DEFAULT_MOVIES, DEFAULT_TAGS, output_dir)
    assert summary["user_profile_rows"] > 0
    assert summary["movie_profile_rows"] >= summary["movies_rows"]

    user_path = output_dir / "user_profile.csv"
    movie_path = output_dir / "movie_profile.csv"
    assert user_path.exists()
    assert movie_path.exists()

    user_columns = set(pd.read_csv(user_path, nrows=1).columns)
    movie_columns = set(pd.read_csv(movie_path, nrows=1).columns)

    assert {"userId", "user_rating_count", "user_avg_rating", "favorite_genres", "active_level"}.issubset(user_columns)
    assert {"movieId", "movie_avg_rating", "movie_rating_count", "movie_popularity", "genres", "tag_text"}.issubset(
        movie_columns
    )
