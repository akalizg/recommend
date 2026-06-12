"""
Build a lightweight graph-style recall channel compatible with LightGCN output.

This is a deterministic fallback channel based on user favorite genres and movie
genre popularity. It produces `recall_type = lightgcn`, so the pipeline can be
replaced later by true LightGCN embeddings without changing downstream schemas.
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
DEFAULT_TRAIN = PROJECT_ROOT / "data" / "processed" / "train_ratings.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "recall" / "lightgcn_recall.csv"

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build lightweight LightGCN recall candidates.")
    parser.add_argument("--user-profile", default=str(DEFAULT_USER_PROFILE))
    parser.add_argument("--movie-profile", default=str(DEFAULT_MOVIE_PROFILE))
    parser.add_argument("--train", default=str(DEFAULT_TRAIN))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--top-n", type=int, default=50)
    return parser.parse_args()


def _genres(value: object) -> set[str]:
    if value is None or pd.isna(value):
        return set()
    return {item.strip().lower() for item in str(value).split("|") if item.strip() and item.strip() != "(no genres listed)"}


def build_lightgcn_recall(
    user_profile_path: str | Path | None = None,
    movie_profile_path: str | Path | None = None,
    train_path: str | Path | None = None,
    output_path: str | Path | None = None,
    top_n: int = 50,
) -> dict:
    user_file = Path(user_profile_path).resolve() if user_profile_path else DEFAULT_USER_PROFILE
    movie_file = Path(movie_profile_path).resolve() if movie_profile_path else DEFAULT_MOVIE_PROFILE
    train_file = Path(train_path).resolve() if train_path else DEFAULT_TRAIN
    output_file = Path(output_path).resolve() if output_path else DEFAULT_OUTPUT

    users = pd.read_csv(user_file, usecols=["userId", "favorite_genres"])
    movies = pd.read_csv(movie_file, usecols=["movieId", "genres", "movie_avg_rating", "movie_popularity"])
    ratings = pd.read_csv(train_file, usecols=["userId", "movieId"])

    movies["movieId"] = pd.to_numeric(movies["movieId"], errors="coerce")
    movies["movie_avg_rating"] = pd.to_numeric(movies["movie_avg_rating"], errors="coerce").fillna(0.0)
    movies["movie_popularity"] = pd.to_numeric(movies["movie_popularity"], errors="coerce").fillna(0.0)
    movies = movies.dropna(subset=["movieId"]).copy()
    movies["movieId"] = movies["movieId"].astype(int)
    movies["genre_set"] = movies["genres"].map(_genres)
    movies["quality_score"] = movies["movie_avg_rating"] * np.log1p(movies["movie_popularity"])

    rated_by_user = (
        ratings.dropna(subset=["userId", "movieId"])
        .astype({"userId": int, "movieId": int})
        .groupby("userId")["movieId"]
        .apply(set)
        .to_dict()
    )

    rows = []
    for user in users.dropna(subset=["userId"]).to_dict(orient="records"):
        user_id = int(user["userId"])
        fav = _genres(user.get("favorite_genres"))
        if not fav:
            continue
        seen = rated_by_user.get(user_id, set())
        candidates = movies[~movies["movieId"].isin(seen)].copy()
        candidates["genre_overlap"] = candidates["genre_set"].map(lambda gs: len(fav & gs) / max(len(gs), 1))
        candidates["recall_score"] = candidates["genre_overlap"] * 0.75 + candidates["quality_score"].rank(pct=True) * 0.25
        selected = candidates[candidates["recall_score"] > 0].sort_values(
            ["recall_score", "movieId"], ascending=[False, True]
        ).head(top_n)
        rows.extend(
            {
                "userId": user_id,
                "movieId": int(row.movieId),
                "recall_type": "lightgcn",
                "recall_score": float(row.recall_score),
            }
            for row in selected.itertuples(index=False)
        )

    output = pd.DataFrame(rows, columns=["userId", "movieId", "recall_type", "recall_score"])
    if output.empty:
        raise ValueError("lightgcn recall output is empty.")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(output_file, index=False)
    summary = {
        "user_count": int(users["userId"].nunique()),
        "output_rows": int(len(output)),
        "top_n": top_n,
        "output_path": str(output_file),
    }
    logger.info("LightGCN recall summary: %s", summary)
    return summary


def main() -> None:
    args = parse_args()
    try:
        build_lightgcn_recall(args.user_profile, args.movie_profile, args.train, args.output, args.top_n)
    except Exception as exc:
        logger.error("%s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
