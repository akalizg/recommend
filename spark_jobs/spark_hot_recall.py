"""
Build popular/hot recall candidates for every profiled user.

The score follows the README design:
    hot_score = movie_avg_rating * log(movie_rating_count + 1)
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_USER_PROFILE = PROJECT_ROOT / "data" / "features" / "user_profile.csv"
DEFAULT_MOVIE_PROFILE = PROJECT_ROOT / "data" / "features" / "movie_profile.csv"
DEFAULT_TRAIN_RATINGS = PROJECT_ROOT / "data" / "processed" / "train_ratings.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "recall" / "hot_recall.csv"

OUTPUT_COLUMNS = ["userId", "movieId", "recall_type", "recall_score"]

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build hot recall candidates.")
    parser.add_argument("--user-profile", default=str(DEFAULT_USER_PROFILE))
    parser.add_argument("--movie-profile", default=str(DEFAULT_MOVIE_PROFILE))
    parser.add_argument("--train-ratings", default=str(DEFAULT_TRAIN_RATINGS))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--top-n", type=int, default=50)
    return parser.parse_args()


def _require_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Required input not found: {path}")


def _normalize(scores: pd.Series) -> pd.Series:
    scores = pd.to_numeric(scores, errors="coerce").fillna(0.0)
    min_score = float(scores.min()) if len(scores) else 0.0
    max_score = float(scores.max()) if len(scores) else 0.0
    if max_score <= min_score:
        return pd.Series(np.ones(len(scores)), index=scores.index)
    return (scores - min_score) / (max_score - min_score)


def build_hot_recall(
    user_profile_path: str | Path | None = None,
    movie_profile_path: str | Path | None = None,
    train_ratings_path: str | Path | None = None,
    output_path: str | Path | None = None,
    top_n: int = 50,
) -> dict:
    user_file = Path(user_profile_path).resolve() if user_profile_path else DEFAULT_USER_PROFILE
    movie_file = Path(movie_profile_path).resolve() if movie_profile_path else DEFAULT_MOVIE_PROFILE
    train_file = Path(train_ratings_path).resolve() if train_ratings_path else DEFAULT_TRAIN_RATINGS
    output_file = Path(output_path).resolve() if output_path else DEFAULT_OUTPUT

    if top_n <= 0:
        raise ValueError("top_n must be positive.")
    for path in (user_file, movie_file, train_file):
        _require_file(path)

    users = pd.read_csv(user_file, usecols=["userId"])
    movies = pd.read_csv(movie_file)
    ratings = pd.read_csv(train_file, usecols=["userId", "movieId"])
    required_movie_cols = {"movieId", "movie_avg_rating", "movie_rating_count"}
    missing = required_movie_cols - set(movies.columns)
    if missing:
        raise ValueError(f"movie profile missing required columns: {sorted(missing)}")

    users["userId"] = pd.to_numeric(users["userId"], errors="coerce")
    users = users.dropna(subset=["userId"]).drop_duplicates("userId")
    users["userId"] = users["userId"].astype(int)

    movies["movieId"] = pd.to_numeric(movies["movieId"], errors="coerce")
    movies["movie_avg_rating"] = pd.to_numeric(movies["movie_avg_rating"], errors="coerce").fillna(0.0)
    movies["movie_rating_count"] = pd.to_numeric(movies["movie_rating_count"], errors="coerce").fillna(0.0)
    movies = movies.dropna(subset=["movieId"]).copy()
    movies["movieId"] = movies["movieId"].astype(int)
    movies["hot_score_raw"] = movies["movie_avg_rating"] * np.log1p(movies["movie_rating_count"])
    movies["recall_score"] = _normalize(movies["hot_score_raw"])
    hot_movies = movies.sort_values(["recall_score", "movieId"], ascending=[False, True])[["movieId", "recall_score"]]

    ratings["userId"] = pd.to_numeric(ratings["userId"], errors="coerce")
    ratings["movieId"] = pd.to_numeric(ratings["movieId"], errors="coerce")
    rated_by_user = (
        ratings.dropna(subset=["userId", "movieId"])
        .astype({"userId": int, "movieId": int})
        .groupby("userId")["movieId"]
        .apply(set)
        .to_dict()
    )

    rows: list[dict] = []
    for user_id in users["userId"].tolist():
        seen = rated_by_user.get(int(user_id), set())
        selected = hot_movies[~hot_movies["movieId"].isin(seen)].head(top_n)
        rows.extend(
            {
                "userId": int(user_id),
                "movieId": int(row.movieId),
                "recall_type": "hot",
                "recall_score": float(row.recall_score),
            }
            for row in selected.itertuples(index=False)
        )

    output = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
    if output.empty:
        raise ValueError("hot recall output is empty.")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(output_file, index=False)
    summary = {
        "user_count": int(users["userId"].nunique()),
        "movie_count": int(movies["movieId"].nunique()),
        "output_rows": int(len(output)),
        "top_n": int(top_n),
        "output_path": str(output_file),
    }
    logger.info("Hot recall summary: %s", summary)
    return summary


def main() -> None:
    args = parse_args()
    try:
        build_hot_recall(args.user_profile, args.movie_profile, args.train_ratings, args.output, args.top_n)
    except Exception as exc:
        logger.error("%s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
