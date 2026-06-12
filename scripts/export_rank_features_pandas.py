"""
Export ranking features with pandas.

This is a local fallback for official Food.com split runs where Spark feature
joins exceed the available JVM heap. The output schema matches
spark_jobs/spark_feature_export.py.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from spark_jobs.spark_feature_export import FEATURE_COLUMNS, OUTPUT_COLUMNS, RECALL_COLUMNS  # noqa: E402

DEFAULT_USER_PROFILE = PROJECT_ROOT / "data" / "features" / "user_profile.csv"
DEFAULT_MOVIE_PROFILE = PROJECT_ROOT / "data" / "features" / "movie_profile.csv"
DEFAULT_MERGED_RECALL = PROJECT_ROOT / "data" / "recall" / "merged_recall_candidates.csv"
DEFAULT_TRAIN_RATINGS = PROJECT_ROOT / "data" / "processed" / "train_ratings.csv"
DEFAULT_TEST_RATINGS = PROJECT_ROOT / "data" / "processed" / "test_ratings.csv"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "rank"

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export ranking features with pandas.")
    parser.add_argument("--user-profile", default=str(DEFAULT_USER_PROFILE))
    parser.add_argument("--movie-profile", default=str(DEFAULT_MOVIE_PROFILE))
    parser.add_argument("--merged-recall", default=str(DEFAULT_MERGED_RECALL))
    parser.add_argument("--train-ratings", default=str(DEFAULT_TRAIN_RATINGS))
    parser.add_argument("--test-ratings", default=str(DEFAULT_TEST_RATINGS))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--negative-ratio", type=float, default=3.0)
    parser.add_argument("--candidate-chunk-size", type=int, default=300000)
    return parser.parse_args()


def _pipe_set(value: object) -> set[str]:
    if value is None or pd.isna(value):
        return set()
    return {item.strip().lower() for item in str(value).split("|") if item.strip()}


def _decade_code(value: object, year: object) -> float:
    text = "" if value is None or pd.isna(value) else str(value)
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) >= 4:
        return float(digits[:4])
    try:
        y = float(year)
    except (TypeError, ValueError):
        return -1.0
    return float(int(y // 10) * 10) if y > 0 else -1.0


def _active_level_code(value: object) -> float:
    text = "" if value is None or pd.isna(value) else str(value).strip().lower()
    if text == "low":
        return 0.0
    if text == "medium":
        return 1.0
    if text == "high":
        return 2.0
    return -1.0


def _read_users(path: Path) -> pd.DataFrame:
    usecols = [
        "userId",
        "user_rating_count",
        "user_avg_rating",
        "user_rating_std",
        "user_min_rating",
        "user_max_rating",
        "favorite_genres",
        "favorite_decades",
        "active_level",
    ]
    users = pd.read_csv(path, usecols=usecols)
    users["userId"] = pd.to_numeric(users["userId"], errors="coerce")
    users = users.dropna(subset=["userId"]).drop_duplicates("userId").copy()
    users["userId"] = users["userId"].astype("int32")
    for col in ["user_rating_count", "user_avg_rating", "user_rating_std", "user_min_rating", "user_max_rating"]:
        users[col] = pd.to_numeric(users[col], errors="coerce").fillna(0.0).astype("float32")
    users["active_level_code"] = users["active_level"].map(_active_level_code).astype("float32")
    users["_favorite_genres_set"] = users["favorite_genres"].map(_pipe_set)
    users["_favorite_decades_set"] = users["favorite_decades"].map(_pipe_set)
    return users.drop(columns=["favorite_genres", "favorite_decades", "active_level"])


def _read_movies(path: Path) -> pd.DataFrame:
    usecols = [
        "movieId",
        "year",
        "decade",
        "genres",
        "genre_count",
        "movie_avg_rating",
        "movie_rating_count",
        "movie_rating_std",
        "movie_popularity",
        "tag_count",
    ]
    movies = pd.read_csv(path, usecols=usecols)
    movies["movieId"] = pd.to_numeric(movies["movieId"], errors="coerce")
    movies = movies.dropna(subset=["movieId"]).drop_duplicates("movieId").copy()
    movies["movieId"] = movies["movieId"].astype("int32")
    movies["movie_year"] = pd.to_numeric(movies["year"], errors="coerce").fillna(0.0).astype("float32")
    movies["movie_decade_code"] = [
        _decade_code(decade, year) for decade, year in zip(movies["decade"], movies["movie_year"])
    ]
    movies["movie_decade_code"] = pd.Series(movies["movie_decade_code"], index=movies.index).astype("float32")
    movies["movie_decade_text"] = movies["decade"].fillna("").astype(str).str.lower()
    movies["_movie_genres_set"] = movies["genres"].map(_pipe_set)
    for col in [
        "genre_count",
        "movie_avg_rating",
        "movie_rating_count",
        "movie_rating_std",
        "movie_popularity",
        "tag_count",
    ]:
        movies[col] = pd.to_numeric(movies[col], errors="coerce").fillna(0.0).astype("float32")
    return movies.drop(columns=["year", "decade", "genres"])


def _read_ratings(path: Path) -> pd.DataFrame:
    ratings = pd.read_csv(path, usecols=["userId", "movieId", "rating", "rating_norm", "timestamp"])
    ratings["userId"] = pd.to_numeric(ratings["userId"], errors="coerce")
    ratings["movieId"] = pd.to_numeric(ratings["movieId"], errors="coerce")
    ratings["rating"] = pd.to_numeric(ratings["rating"], errors="coerce")
    ratings = ratings.dropna(subset=["userId", "movieId", "rating"]).copy()
    ratings["userId"] = ratings["userId"].astype("int32")
    ratings["movieId"] = ratings["movieId"].astype("int32")
    ratings["rating"] = ratings["rating"].astype("float32")
    return ratings


def _read_recall(path: Path) -> pd.DataFrame:
    recall = pd.read_csv(path, usecols=["userId", "movieId", *RECALL_COLUMNS])
    recall["userId"] = pd.to_numeric(recall["userId"], errors="coerce")
    recall["movieId"] = pd.to_numeric(recall["movieId"], errors="coerce")
    recall = recall.dropna(subset=["userId", "movieId"]).drop_duplicates(["userId", "movieId"]).copy()
    recall["userId"] = recall["userId"].astype("int32")
    recall["movieId"] = recall["movieId"].astype("int32")
    for col in RECALL_COLUMNS:
        recall[col] = pd.to_numeric(recall[col], errors="coerce").fillna(0.0).astype("float32")
    return recall


def _add_pair_features(df: pd.DataFrame) -> pd.DataFrame:
    favorite_genres = df["_favorite_genres_set"].tolist()
    favorite_decades = df["_favorite_decades_set"].tolist()
    movie_genres = df["_movie_genres_set"].tolist()
    genre_counts = pd.to_numeric(df["genre_count"], errors="coerce").fillna(0.0).to_numpy(dtype=np.float32)
    decade_texts = df["movie_decade_text"].fillna("").astype(str).str.lower().tolist()

    genre_scores = []
    decade_scores = []
    for fav_genres, fav_decades, genres, genre_count, decade_text in zip(
        favorite_genres,
        favorite_decades,
        movie_genres,
        genre_counts,
        decade_texts,
    ):
        genre_scores.append(float(len(fav_genres & genres) / genre_count) if genre_count > 0 else 0.0)
        decade_scores.append(1.0 if decade_text and decade_text in fav_decades else 0.0)

    df["genre_match_score"] = np.asarray(genre_scores, dtype=np.float32)
    df["decade_match_score"] = np.asarray(decade_scores, dtype=np.float32)
    df["user_movie_score_gap"] = (
        pd.to_numeric(df["user_avg_rating"], errors="coerce").fillna(0.0)
        - pd.to_numeric(df["movie_avg_rating"], errors="coerce").fillna(0.0)
    ).abs().astype("float32")
    df["label"] = pd.to_numeric(df.get("label", 0), errors="coerce").fillna(0).astype("int8")
    for col in FEATURE_COLUMNS:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0).astype("float32")
    return df[OUTPUT_COLUMNS].copy()


def _build_features(base: pd.DataFrame, users: pd.DataFrame, movies: pd.DataFrame, recall: pd.DataFrame | None = None) -> pd.DataFrame:
    df = base.merge(users, on="userId", how="left").merge(movies, on="movieId", how="left")
    if recall is not None:
        df = df.merge(recall, on=["userId", "movieId"], how="left")
    else:
        for col in RECALL_COLUMNS:
            df[col] = 0.0
    for col in RECALL_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0).astype("float32")
    df["_favorite_genres_set"] = df["_favorite_genres_set"].map(lambda value: value if isinstance(value, set) else set())
    df["_favorite_decades_set"] = df["_favorite_decades_set"].map(lambda value: value if isinstance(value, set) else set())
    df["_movie_genres_set"] = df["_movie_genres_set"].map(lambda value: value if isinstance(value, set) else set())
    df["movie_decade_text"] = df["movie_decade_text"].fillna("")
    return _add_pair_features(df)


def export_rank_features_pandas(
    user_profile_path: str | Path = DEFAULT_USER_PROFILE,
    movie_profile_path: str | Path = DEFAULT_MOVIE_PROFILE,
    merged_recall_path: str | Path = DEFAULT_MERGED_RECALL,
    train_ratings_path: str | Path = DEFAULT_TRAIN_RATINGS,
    test_ratings_path: str | Path = DEFAULT_TEST_RATINGS,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    negative_ratio: float = 3.0,
    candidate_chunk_size: int = 300000,
) -> dict:
    if negative_ratio <= 0:
        raise ValueError("negative_ratio must be positive.")
    if candidate_chunk_size <= 0:
        raise ValueError("candidate_chunk_size must be positive.")

    user_file = Path(user_profile_path).resolve()
    movie_file = Path(movie_profile_path).resolve()
    recall_file = Path(merged_recall_path).resolve()
    train_file = Path(train_ratings_path).resolve()
    test_file = Path(test_ratings_path).resolve()
    output_path = Path(output_dir).resolve()
    output_path.mkdir(parents=True, exist_ok=True)

    logger.info("Reading profiles and ratings...")
    users = _read_users(user_file)
    movies = _read_movies(movie_file)
    recall = _read_recall(recall_file)
    train_ratings = _read_ratings(train_file)
    test_ratings = _read_ratings(test_file)

    positives = train_ratings[train_ratings["rating"] >= 4.0][["userId", "movieId"]].copy()
    positives["label"] = 1
    negatives = train_ratings[train_ratings["rating"] <= 3.0][["userId", "movieId"]].copy()
    negatives["label"] = 0
    max_negatives = int(len(positives) * negative_ratio)
    if len(negatives) > max_negatives:
        negatives = negatives.sample(n=max_negatives, random_state=42)
    train_base = pd.concat([positives, negatives], ignore_index=True)
    if train_base["label"].nunique() < 2:
        raise ValueError("Both positive and negative samples are required for rank training.")

    logger.info("Building train features: positives=%s negatives=%s", len(positives), len(negatives))
    train_features = _build_features(train_base, users, movies, recall)
    train_output = output_path / "rank_train.csv"
    train_features.to_csv(train_output, index=False)

    positive_test = test_ratings[test_ratings["rating"] >= 4.0][["userId", "movieId"]].drop_duplicates().copy()
    positive_test["label"] = 1
    candidates_output = output_path / "rank_candidates.csv"
    if candidates_output.exists():
        candidates_output.unlink()
    logger.info("Building candidate features in chunks...")
    first = True
    candidate_rows = 0
    candidate_positive_labels = 0
    for start in range(0, len(recall), candidate_chunk_size):
        chunk_recall = recall.iloc[start : start + candidate_chunk_size].copy()
        base = chunk_recall[["userId", "movieId"]].merge(positive_test, on=["userId", "movieId"], how="left")
        base["label"] = pd.to_numeric(base["label"], errors="coerce").fillna(0).astype("int8")
        chunk_features = _build_features(base, users, movies, chunk_recall)
        candidate_rows += int(len(chunk_features))
        candidate_positive_labels += int((chunk_features["label"] == 1).sum())
        chunk_features.to_csv(candidates_output, index=False, mode="w" if first else "a", header=first)
        first = False
        logger.info("candidate feature rows written: %s / %s", candidate_rows, len(recall))

    feature_output = output_path / "rank_feature_columns.json"
    feature_output.write_text(json.dumps(FEATURE_COLUMNS, ensure_ascii=False, indent=2), encoding="utf-8")
    if not train_output.exists() or not candidates_output.exists() or not feature_output.exists():
        raise RuntimeError("Rank feature export did not write expected outputs.")

    summary = {
        "user_profile_rows": int(len(users)),
        "movie_profile_rows": int(len(movies)),
        "merged_recall_rows": int(len(recall)),
        "train_rating_rows": int(len(train_ratings)),
        "test_rating_rows": int(len(test_ratings)),
        "rank_train_rows": int(len(train_features)),
        "rank_candidates_rows": candidate_rows,
        "positive_train_samples": int((train_features["label"] == 1).sum()),
        "negative_train_samples": int((train_features["label"] == 0).sum()),
        "candidate_positive_labels": candidate_positive_labels,
        "candidate_negative_labels": candidate_rows - candidate_positive_labels,
        "feature_count": len(FEATURE_COLUMNS),
        "rank_train_path": str(train_output),
        "rank_candidates_path": str(candidates_output),
        "feature_columns_path": str(feature_output),
    }
    logger.info("Pandas rank feature export summary: %s", summary)
    return summary


def main() -> None:
    args = parse_args()
    export_rank_features_pandas(
        args.user_profile,
        args.movie_profile,
        args.merged_recall,
        args.train_ratings,
        args.test_ratings,
        args.output_dir,
        args.negative_ratio,
        args.candidate_chunk_size,
    )


if __name__ == "__main__":
    main()
