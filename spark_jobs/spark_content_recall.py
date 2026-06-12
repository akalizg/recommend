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
    parser.add_argument("--max-candidate-movies", type=int, default=20000)
    parser.add_argument("--query-batch-size", type=int, default=256)
    parser.add_argument("--candidate-extra", type=int, default=300)
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
    max_candidate_movies: int = 20000,
    query_batch_size: int = 256,
    candidate_extra: int = 300,
) -> dict:
    user_file = Path(user_profile_path).resolve() if user_profile_path else DEFAULT_USER_PROFILE
    movie_file = Path(movie_profile_path).resolve() if movie_profile_path else DEFAULT_MOVIE_PROFILE
    train_file = Path(train_ratings_path).resolve() if train_ratings_path else DEFAULT_TRAIN_RATINGS
    output_file = Path(output_path).resolve() if output_path else DEFAULT_OUTPUT

    if top_n <= 0:
        raise ValueError("top_n must be positive.")
    if max_candidate_movies <= 0:
        raise ValueError("max_candidate_movies must be positive.")
    if query_batch_size <= 0:
        raise ValueError("query_batch_size must be positive.")
    if candidate_extra < 0:
        raise ValueError("candidate_extra must be zero or positive.")
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
    for col in ["movie_popularity", "movie_rating_count", "movie_avg_rating"]:
        if col not in movies.columns:
            movies[col] = 0.0
        movies[col] = pd.to_numeric(movies[col], errors="coerce").fillna(0.0)
    movies["content_text"] = movies.apply(_movie_text, axis=1)
    candidate_movies = (
        movies.sort_values(
            ["movie_popularity", "movie_rating_count", "movie_avg_rating", "movieId"],
            ascending=[False, False, False, True],
        )
        .head(max_candidate_movies)
        .copy()
    )

    vectorizer = TfidfVectorizer(max_features=max_features, ngram_range=(1, 2), min_df=1)
    vectorizer.fit(movies["content_text"].fillna(""))
    movie_matrix = vectorizer.transform(candidate_movies["content_text"].fillna(""))
    movie_ids = candidate_movies["movieId"].to_numpy()
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

    query_rows: list[tuple[int, str]] = []
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
        query_rows.append((user_id, query_text))

    rows: list[dict] = []
    if query_rows:
        neighbor_count = min(len(movie_ids), top_n + candidate_extra)
        for start in range(0, len(query_rows), query_batch_size):
            batch = query_rows[start : start + query_batch_size]
            batch_user_ids = [user_id for user_id, _ in batch]
            batch_texts = [text for _, text in batch]
            query_matrix = vectorizer.transform(batch_texts)
            score_matrix = linear_kernel(query_matrix, movie_matrix)
            for row_idx, user_id in enumerate(batch_user_ids):
                scores = score_matrix[row_idx]
                if neighbor_count >= len(scores):
                    candidate_idx = np.argsort(scores)[::-1]
                else:
                    candidate_idx = np.argpartition(scores, -neighbor_count)[-neighbor_count:]
                    candidate_idx = candidate_idx[np.argsort(scores[candidate_idx])[::-1]]
                seen = rated_by_user.get(user_id, set())
                selected = 0
                for idx in candidate_idx:
                    score = float(scores[idx])
                    if score <= 0:
                        break
                    movie_id = int(movie_ids[idx])
                    if movie_id in seen:
                        continue
                    rows.append(
                        {
                            "userId": user_id,
                            "movieId": movie_id,
                            "recall_type": "content",
                            "recall_score": score,
                        }
                    )
                    selected += 1
                    if selected >= top_n:
                        break

    output = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
    if output.empty:
        raise ValueError("content recall output is empty.")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(output_file, index=False)
    summary = {
        "user_count": int(users["userId"].nunique()),
        "movie_count": int(movies["movieId"].nunique()),
        "candidate_movie_count": int(len(candidate_movies)),
        "query_user_count": int(len(query_rows)),
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
            args.max_candidate_movies,
            args.query_batch_size,
            args.candidate_extra,
        )
    except Exception as exc:
        logger.error("%s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
