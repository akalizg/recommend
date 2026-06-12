"""
Build content-based recall candidates from movie profile text.

For each user, the job builds a preference query from favorite genres and
high-rated movie text, then retrieves unseen movies by TF-IDF cosine similarity.
"""
from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_USER_PROFILE = PROJECT_ROOT / "data" / "features" / "user_profile.csv"
DEFAULT_MOVIE_PROFILE = PROJECT_ROOT / "data" / "features" / "movie_profile.csv"
DEFAULT_TRAIN_RATINGS = PROJECT_ROOT / "data" / "processed" / "train_ratings.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "recall" / "content_recall.csv"

OUTPUT_COLUMNS = ["userId", "movieId", "recall_type", "recall_score"]

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build content-based recall candidates.")
    parser.add_argument("--user-profile", default=str(DEFAULT_USER_PROFILE))
    parser.add_argument("--movie-profile", default=str(DEFAULT_MOVIE_PROFILE))
    parser.add_argument("--train-ratings", default=str(DEFAULT_TRAIN_RATINGS))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--top-n", type=int, default=50)
    parser.add_argument("--max-features", type=int, default=20000)
    return parser.parse_args()


def _require_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Required input not found: {path}")


def _clean_text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).replace("|", " ").replace("_", " ")
    return re.sub(r"\s+", " ", text).strip().lower()


def _movie_text(row: pd.Series) -> str:
    parts = [
        row.get("clean_title"),
        row.get("title"),
        row.get("genres"),
        row.get("tag_text"),
        row.get("overview"),
        row.get("director"),
        row.get("actors"),
    ]
    return " ".join(_clean_text(part) for part in parts if _clean_text(part))


def _parse_ids(value: object) -> list[int]:
    text = "" if value is None or pd.isna(value) else str(value)
    ids: list[int] = []
    for part in re.split(r"[|,\s]+", text):
        if not part:
            continue
        try:
            ids.append(int(float(part)))
        except ValueError:
            continue
    return ids


def build_content_recall(
    user_profile_path: str | Path | None = None,
    movie_profile_path: str | Path | None = None,
    train_ratings_path: str | Path | None = None,
    output_path: str | Path | None = None,
    top_n: int = 50,
    max_features: int = 20000,
) -> dict:
    user_file = Path(user_profile_path).resolve() if user_profile_path else DEFAULT_USER_PROFILE
    movie_file = Path(movie_profile_path).resolve() if movie_profile_path else DEFAULT_MOVIE_PROFILE
    train_file = Path(train_ratings_path).resolve() if train_ratings_path else DEFAULT_TRAIN_RATINGS
    output_file = Path(output_path).resolve() if output_path else DEFAULT_OUTPUT

    if top_n <= 0:
        raise ValueError("top_n must be positive.")
    for path in (user_file, movie_file, train_file):
        _require_file(path)

    users = pd.read_csv(user_file)
    movies = pd.read_csv(movie_file)
    ratings = pd.read_csv(train_file, usecols=["userId", "movieId"])
    for col in ["userId", "favorite_genres"]:
        if col not in users.columns:
            raise ValueError(f"user profile missing required column: {col}")
    for col in ["movieId", "title", "genres"]:
        if col not in movies.columns:
            raise ValueError(f"movie profile missing required column: {col}")

    users["userId"] = pd.to_numeric(users["userId"], errors="coerce")
    users = users.dropna(subset=["userId"]).drop_duplicates("userId")
    users["userId"] = users["userId"].astype(int)
    movies["movieId"] = pd.to_numeric(movies["movieId"], errors="coerce")
    movies = movies.dropna(subset=["movieId"]).drop_duplicates("movieId").copy()
    movies["movieId"] = movies["movieId"].astype(int)
    movies["content_text"] = movies.apply(_movie_text, axis=1)

    vectorizer = TfidfVectorizer(max_features=max_features, ngram_range=(1, 2), min_df=1)
    movie_matrix = vectorizer.fit_transform(movies["content_text"].fillna(""))
    movie_ids = movies["movieId"].to_numpy()
    movie_text_by_id = dict(zip(movies["movieId"], movies["content_text"]))

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
    for user in users.to_dict(orient="records"):
        user_id = int(user["userId"])
        favorite_text = _clean_text(user.get("favorite_genres"))
        high_movie_text = " ".join(
            movie_text_by_id.get(movie_id, "")
            for movie_id in _parse_ids(user.get("high_rating_movie_ids"))[:20]
        )
        query_text = " ".join(part for part in [favorite_text, high_movie_text] if part).strip()
        if not query_text:
            continue
        query_vec = vectorizer.transform([query_text])
        scores = linear_kernel(query_vec, movie_matrix).ravel()
        seen = rated_by_user.get(user_id, set())
        order = np.argsort(scores)[::-1]
        selected = []
        for idx in order:
            score = float(scores[idx])
            movie_id = int(movie_ids[idx])
            if score <= 0:
                break
            if movie_id in seen:
                continue
            selected.append(
                {
                    "userId": user_id,
                    "movieId": movie_id,
                    "recall_type": "content",
                    "recall_score": score,
                }
            )
            if len(selected) >= top_n:
                break
        rows.extend(selected)

    output = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
    if output.empty:
        raise ValueError("content recall output is empty.")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(output_file, index=False)
    summary = {
        "user_count": int(users["userId"].nunique()),
        "movie_count": int(movies["movieId"].nunique()),
        "output_rows": int(len(output)),
        "top_n": int(top_n),
        "output_path": str(output_file),
    }
    logger.info("Content recall summary: %s", summary)
    return summary


def main() -> None:
    args = parse_args()
    try:
        build_content_recall(
            args.user_profile,
            args.movie_profile,
            args.train_ratings,
            args.output,
            args.top_n,
            args.max_features,
        )
    except Exception as exc:
        logger.error("%s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
