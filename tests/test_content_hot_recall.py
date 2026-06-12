from __future__ import annotations

import importlib

import pandas as pd


def _write_inputs(tmp_path):
    users = pd.DataFrame(
        [
            {"userId": 1, "favorite_genres": "Action|Adventure", "high_rating_movie_ids": "10"},
            {"userId": 2, "favorite_genres": "Comedy|Drama", "high_rating_movie_ids": "20"},
        ]
    )
    movies = pd.DataFrame(
        [
            {"movieId": 10, "title": "Action One", "clean_title": "Action One", "genres": "Action|Adventure", "movie_avg_rating": 4.5, "movie_rating_count": 100, "tag_text": "hero"},
            {"movieId": 11, "title": "Action Two", "clean_title": "Action Two", "genres": "Action|Adventure", "movie_avg_rating": 4.0, "movie_rating_count": 80, "tag_text": "hero quest"},
            {"movieId": 20, "title": "Comedy One", "clean_title": "Comedy One", "genres": "Comedy|Drama", "movie_avg_rating": 4.4, "movie_rating_count": 90, "tag_text": "funny"},
            {"movieId": 21, "title": "Comedy Two", "clean_title": "Comedy Two", "genres": "Comedy|Drama", "movie_avg_rating": 3.9, "movie_rating_count": 70, "tag_text": "funny warm"},
        ]
    )
    ratings = pd.DataFrame(
        [
            {"userId": 1, "movieId": 10},
            {"userId": 2, "movieId": 20},
        ]
    )
    user_path = tmp_path / "user_profile.csv"
    movie_path = tmp_path / "movie_profile.csv"
    rating_path = tmp_path / "train_ratings.csv"
    users.to_csv(user_path, index=False)
    movies.to_csv(movie_path, index=False)
    ratings.to_csv(rating_path, index=False)
    return user_path, movie_path, rating_path


def test_content_and_hot_recall_importable():
    assert hasattr(importlib.import_module("spark_jobs.spark_content_recall"), "build_content_recall")
    assert hasattr(importlib.import_module("spark_jobs.spark_hot_recall"), "build_hot_recall")


def test_content_recall_outputs(tmp_path):
    from spark_jobs.spark_content_recall import build_content_recall

    user_path, movie_path, rating_path = _write_inputs(tmp_path)
    output_path = tmp_path / "content_recall.csv"
    summary = build_content_recall(user_path, movie_path, rating_path, output_path, top_n=2)
    assert summary["output_rows"] > 0
    df = pd.read_csv(output_path)
    assert {"userId", "movieId", "recall_type", "recall_score"}.issubset(df.columns)
    assert set(df["recall_type"]) == {"content"}
    assert df.groupby("userId").size().max() <= 2
    assert not ((df["userId"] == 1) & (df["movieId"] == 10)).any()


def test_hot_recall_outputs(tmp_path):
    from spark_jobs.spark_hot_recall import build_hot_recall

    user_path, movie_path, rating_path = _write_inputs(tmp_path)
    output_path = tmp_path / "hot_recall.csv"
    summary = build_hot_recall(user_path, movie_path, rating_path, output_path, top_n=2)
    assert summary["output_rows"] == 4
    df = pd.read_csv(output_path)
    assert {"userId", "movieId", "recall_type", "recall_score"}.issubset(df.columns)
    assert set(df["recall_type"]) == {"hot"}
    assert df.groupby("userId").size().max() <= 2
    assert df["recall_score"].between(0, 1).all()
