"""
Apply standard MMR diversity reranking to XGBoost Top50 candidates.

This script is an offline side-path job. It does not add long-tail or novelty
features and does not modify the online recommendation flow.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Iterable

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RANKED = PROJECT_ROOT / "data" / "rank" / "ranked_top50.csv"
DEFAULT_MOVIE_PROFILE = PROJECT_ROOT / "data" / "features" / "movie_profile.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "rank" / "ranked_top10_mmr.csv"

OUTPUT_COLUMNS = [
    "userId",
    "movieId",
    "rank_position",
    "rank_score",
    "mmr_score",
    "label",
    "als_score",
    "itemcf_score",
    "merged_recall_score",
    "recall_source_count",
    "genre_match_score",
    "movie_avg_rating",
    "movie_rating_count",
    "movie_popularity",
]

FORBIDDEN_COLUMN_PARTS = ("long_tail", "novelty")

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply MMR reranking to XGBoost Top50 results.")
    parser.add_argument("--ranked", default=str(DEFAULT_RANKED), help="XGBoost ranked Top50 CSV.")
    parser.add_argument("--movie-profile", default=str(DEFAULT_MOVIE_PROFILE), help="Movie profile CSV.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="MMR Top10 CSV output.")
    parser.add_argument("--top-n", type=int, default=10, help="Top-N rows to keep per user.")
    parser.add_argument("--lambda-rel", type=float, default=0.7, help="MMR relevance weight.")
    return parser.parse_args()


def _parse_genres(value: object) -> set[str]:
    if pd.isna(value):
        return set()
    text = str(value).strip()
    if not text or text == "(no genres listed)":
        return set()
    return {item.strip().lower() for item in text.split("|") if item.strip() and item.strip() != "(no genres listed)"}


def genre_jaccard(left: Iterable[str], right: Iterable[str]) -> float:
    left_set = set(left)
    right_set = set(right)
    if not left_set or not right_set:
        return 0.0
    union = left_set | right_set
    if not union:
        return 0.0
    return len(left_set & right_set) / len(union)


def _average_diversity(rows: pd.DataFrame, genres_by_movie: dict[int, set[str]]) -> float:
    scores: list[float] = []
    for _, group in rows.groupby("userId"):
        movie_ids = group["movieId"].astype(int).tolist()
        if len(movie_ids) < 2:
            scores.append(0.0)
            continue
        similarities = []
        for i in range(len(movie_ids)):
            for j in range(i + 1, len(movie_ids)):
                similarities.append(genre_jaccard(genres_by_movie.get(movie_ids[i], set()), genres_by_movie.get(movie_ids[j], set())))
        scores.append(1.0 - (sum(similarities) / len(similarities) if similarities else 0.0))
    return float(sum(scores) / len(scores)) if scores else 0.0


def _rerank_user(group: pd.DataFrame, genres_by_movie: dict[int, set[str]], top_n: int, lambda_rel: float) -> list[dict]:
    candidates = group.sort_values(["rank_score", "merged_recall_score", "movieId"], ascending=[False, False, True]).to_dict(
        orient="records"
    )
    selected: list[dict] = []
    remaining = candidates.copy()

    while remaining and len(selected) < top_n:
        best_index = 0
        best_score = None
        for idx, candidate in enumerate(remaining):
            movie_id = int(candidate["movieId"])
            relevance = float(candidate.get("rank_score", 0.0) or 0.0)
            max_similarity = 0.0
            if selected:
                candidate_genres = genres_by_movie.get(movie_id, set())
                max_similarity = max(
                    genre_jaccard(candidate_genres, genres_by_movie.get(int(item["movieId"]), set())) for item in selected
                )
            mmr_score = lambda_rel * relevance - (1.0 - lambda_rel) * max_similarity
            if best_score is None or mmr_score > best_score:
                best_score = mmr_score
                best_index = idx
        chosen = remaining.pop(best_index)
        chosen["mmr_score"] = float(best_score if best_score is not None else 0.0)
        chosen["rank_position"] = len(selected) + 1
        selected.append(chosen)
    return selected


def mmr_rerank(
    ranked_path: str | Path | None = None,
    movie_profile_path: str | Path | None = None,
    output_path: str | Path | None = None,
    top_n: int = 10,
    lambda_rel: float = 0.7,
) -> dict:
    ranked_file = Path(ranked_path).resolve() if ranked_path else DEFAULT_RANKED
    movie_profile_file = Path(movie_profile_path).resolve() if movie_profile_path else DEFAULT_MOVIE_PROFILE
    output_file = Path(output_path).resolve() if output_path else DEFAULT_OUTPUT

    if not 0 <= lambda_rel <= 1:
        raise ValueError("lambda_rel must be between 0 and 1.")
    if top_n <= 0:
        raise ValueError("top_n must be positive.")
    if not ranked_file.exists():
        raise FileNotFoundError(f"Ranked Top50 input not found: {ranked_file}")
    if not movie_profile_file.exists():
        raise FileNotFoundError(f"Movie profile input not found: {movie_profile_file}")

    logger.info("ranked Top50 input: %s", ranked_file)
    logger.info("movie profile input: %s", movie_profile_file)
    logger.info("output path: %s", output_file)
    logger.info("topN: %s", top_n)
    logger.info("lambda_rel: %.3f", lambda_rel)

    ranked = pd.read_csv(ranked_file)
    movie_profile = pd.read_csv(movie_profile_file)
    required = {
        "userId",
        "movieId",
        "rank_score",
        "label",
        "als_score",
        "itemcf_score",
        "merged_recall_score",
        "recall_source_count",
        "genre_match_score",
        "movie_avg_rating",
        "movie_popularity",
    }
    missing = sorted(required - set(ranked.columns))
    if missing:
        raise ValueError(f"ranked Top50 input missing required columns: {missing}")
    if not {"movieId", "genres", "movie_rating_count"}.issubset(movie_profile.columns):
        raise ValueError("movie_profile.csv must contain movieId, genres, movie_rating_count.")

    for col in ["userId", "movieId", "label"]:
        ranked[col] = pd.to_numeric(ranked[col], errors="coerce")
    for col in [
        "rank_score",
        "als_score",
        "itemcf_score",
        "merged_recall_score",
        "recall_source_count",
        "genre_match_score",
        "movie_avg_rating",
        "movie_popularity",
    ]:
        ranked[col] = pd.to_numeric(ranked[col], errors="coerce").fillna(0.0)
    ranked = ranked.dropna(subset=["userId", "movieId"]).copy()
    ranked["userId"] = ranked["userId"].astype(int)
    ranked["movieId"] = ranked["movieId"].astype(int)
    ranked["label"] = ranked["label"].fillna(0).astype(int).clip(0, 1)

    movie_profile["movieId"] = pd.to_numeric(movie_profile["movieId"], errors="coerce")
    movie_profile = movie_profile.dropna(subset=["movieId"]).copy()
    movie_profile["movieId"] = movie_profile["movieId"].astype(int)
    movie_profile["movie_rating_count"] = pd.to_numeric(movie_profile["movie_rating_count"], errors="coerce").fillna(0.0)
    genres_by_movie = dict(zip(movie_profile["movieId"], movie_profile["genres"].map(_parse_genres)))
    rating_count_by_movie = dict(zip(movie_profile["movieId"], movie_profile["movie_rating_count"]))

    ranked["movie_rating_count"] = ranked["movieId"].map(rating_count_by_movie).fillna(0.0)

    selected_rows: list[dict] = []
    for _, group in ranked.groupby("userId", sort=True):
        selected_rows.extend(_rerank_user(group, genres_by_movie, top_n, lambda_rel))

    output = pd.DataFrame(selected_rows)
    if output.empty:
        raise ValueError("MMR output is empty.")
    for col in OUTPUT_COLUMNS:
        if col not in output.columns:
            output[col] = 0.0
    output = output[OUTPUT_COLUMNS].copy()
    output["mmr_score"] = pd.to_numeric(output["mmr_score"], errors="coerce")
    output["rank_score"] = pd.to_numeric(output["rank_score"], errors="coerce").fillna(0.0)
    output["rank_position"] = pd.to_numeric(output["rank_position"], errors="coerce").astype(int)

    forbidden = [col for col in output.columns if any(part in col.lower() for part in FORBIDDEN_COLUMN_PARTS)]
    if forbidden:
        raise ValueError(f"MMR output must not contain long-tail or novelty columns: {forbidden}")

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(output_file, index=False)
    if not output_file.exists():
        raise RuntimeError(f"MMR output was not written: {output_file}")
    if output.groupby("userId").size().max() > top_n:
        raise ValueError(f"Quality check failed: some users have more than top_n={top_n} rows.")
    if output.groupby("userId")["rank_position"].min().min() != 1:
        raise ValueError("Quality check failed: rank_position must start at 1.")
    if output["mmr_score"].isna().any():
        raise ValueError("Quality check failed: mmr_score contains null values.")
    missing_output = sorted(set(OUTPUT_COLUMNS) - set(output.columns))
    if missing_output:
        raise ValueError(f"Quality check failed: missing output columns {missing_output}.")

    ranked_rows = int(len(ranked))
    user_count = int(ranked["userId"].nunique())
    movie_count = int(ranked["movieId"].nunique())
    output_rows = int(len(output))
    average_recs = float(output.groupby("userId").size().mean())
    average_diversity = _average_diversity(output, genres_by_movie)
    sample_rows = output.head(10).to_dict(orient="records")
    summary = {
        "ranked_top50_rows": ranked_rows,
        "user_count": user_count,
        "movie_count": movie_count,
        "top_n": top_n,
        "lambda_rel": lambda_rel,
        "output_rows": output_rows,
        "average_recommendations_per_user": average_recs,
        "average_diversity_score": average_diversity,
        "output_path": str(output_file),
        "sample_top10_rows": sample_rows,
    }

    logger.info("ranked_top50 rows: %s", ranked_rows)
    logger.info("user count: %s", user_count)
    logger.info("movie count: %s", movie_count)
    logger.info("topN: %s", top_n)
    logger.info("lambda_rel: %.3f", lambda_rel)
    logger.info("output rows: %s", output_rows)
    logger.info("average recommendations per user: %.4f", average_recs)
    logger.info("average diversity score: %.6f", average_diversity)
    logger.info("output path: %s", output_file)
    logger.info("sample top10 rows:")
    for row in sample_rows:
        logger.info("  %s", row)
    logger.info("quality validation result: success")
    return summary


def main() -> None:
    args = parse_args()
    try:
        mmr_rerank(args.ranked, args.movie_profile, args.output, args.top_n, args.lambda_rel)
    except Exception as exc:
        logger.error("%s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
