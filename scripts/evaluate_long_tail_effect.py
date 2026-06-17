"""Evaluate long-tail coverage and recommendation diversity.

This script measures how many long-tail recipes are surfaced in the merged
recall pool, the rank candidate pool, and the final ranked top-N output.

Long-tail is defined from movie_profile.csv using movie_popularity quantiles.
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MERGED_RECALL = PROJECT_ROOT / "data" / "recall" / "merged_recall_candidates.csv"
DEFAULT_MOVIE_PROFILE = PROJECT_ROOT / "data" / "features" / "movie_profile.csv"
DEFAULT_RANK_CANDIDATES = PROJECT_ROOT / "data" / "rank" / "rank_candidates.csv"
DEFAULT_RANKED_TOP50 = PROJECT_ROOT / "data" / "rank" / "enhanced" / "ranked_top50_enhanced.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "rank" / "enhanced" / "long_tail_eval_summary.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate long-tail effect of KG-enhanced recommendations.")
    parser.add_argument("--merged-recall", default=str(DEFAULT_MERGED_RECALL))
    parser.add_argument("--movie-profile", default=str(DEFAULT_MOVIE_PROFILE))
    parser.add_argument("--rank-candidates", default=str(DEFAULT_RANK_CANDIDATES))
    parser.add_argument("--ranked-top50", default=str(DEFAULT_RANKED_TOP50))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument(
        "--tail-quantile",
        type=float,
        default=0.7,
        help="Recipes at or below this movie_popularity quantile are considered long-tail.",
    )
    return parser.parse_args()


def _read_csv(path: str | Path, required: set[str]) -> pd.DataFrame:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(file_path)
    df = pd.read_csv(file_path)
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{file_path} missing required columns: {sorted(missing)}")
    return df


def _prepare_long_tail_map(movie_profile_path: str | Path, tail_quantile: float) -> tuple[pd.DataFrame, float]:
    movies = _read_csv(movie_profile_path, {"movieId", "movie_popularity"})[["movieId", "movie_popularity"]].copy()
    movies["movieId"] = pd.to_numeric(movies["movieId"], errors="coerce")
    movies["movie_popularity"] = pd.to_numeric(movies["movie_popularity"], errors="coerce").fillna(0.0)
    movies = movies.dropna(subset=["movieId"]).copy()
    movies["movieId"] = movies["movieId"].astype("int32")
    threshold = float(movies["movie_popularity"].quantile(tail_quantile))
    movies["is_long_tail"] = movies["movie_popularity"] <= threshold
    return movies[["movieId", "is_long_tail"]], threshold


def _attach_long_tail_flag(df: pd.DataFrame, long_tail_map: pd.DataFrame) -> pd.DataFrame:
    merged = df[["userId", "movieId"]].copy()
    merged["userId"] = pd.to_numeric(merged["userId"], errors="coerce")
    merged["movieId"] = pd.to_numeric(merged["movieId"], errors="coerce")
    merged = merged.dropna(subset=["userId", "movieId"]).copy()
    merged["userId"] = merged["userId"].astype("int32")
    merged["movieId"] = merged["movieId"].astype("int32")
    merged = merged.merge(long_tail_map, on="movieId", how="left")
    merged["is_long_tail"] = merged["is_long_tail"].fillna(False)
    return merged


def _safe_rate(numerator: float, denominator: float) -> float:
    return float(numerator / denominator) if denominator else 0.0


def _coverage_by_user(df: pd.DataFrame) -> float:
    if df.empty:
        return 0.0
    user_counts = df.groupby("userId")["movieId"].nunique()
    long_tail_counts = df[df["is_long_tail"]].groupby("userId")["movieId"].nunique()
    ratios = long_tail_counts.reindex(user_counts.index, fill_value=0) / user_counts
    return float(ratios.mean()) if not ratios.empty else 0.0


def _unique_recipe_coverage(df: pd.DataFrame) -> float:
    if df.empty:
        return 0.0
    return float(df["movieId"].nunique() / len(df))


def _summarize_pool(name: str, df: pd.DataFrame) -> dict:
    total = int(len(df))
    long_tail_total = int(df["is_long_tail"].sum())
    unique_total = int(df["movieId"].nunique())
    return {
        f"{name}_rows": total,
        f"{name}_unique_recipes": unique_total,
        f"{name}_long_tail_rows": long_tail_total,
        f"{name}_long_tail_ratio": _safe_rate(long_tail_total, total),
        f"{name}_unique_long_tail_recipes": int(df.loc[df["is_long_tail"], "movieId"].nunique()),
        f"{name}_unique_long_tail_ratio": _safe_rate(int(df.loc[df["is_long_tail"], "movieId"].nunique()), unique_total),
        f"{name}_user_long_tail_coverage": _coverage_by_user(df),
    }


def evaluate_long_tail_effect(
    merged_recall_path: str | Path,
    movie_profile_path: str | Path,
    rank_candidates_path: str | Path,
    ranked_top50_path: str | Path,
    tail_quantile: float,
) -> dict:
    merged_recall = _read_csv(merged_recall_path, {"userId", "movieId", "merged_recall_score"})
    rank_candidates = _read_csv(rank_candidates_path, {"userId", "movieId", "label"})
    ranked_top50 = _read_csv(ranked_top50_path, {"userId", "movieId", "rank_score"})

    long_tail_map, threshold = _prepare_long_tail_map(movie_profile_path, tail_quantile)
    merged_recall = _attach_long_tail_flag(merged_recall, long_tail_map)
    rank_candidates = _attach_long_tail_flag(rank_candidates, long_tail_map)
    ranked_top50 = _attach_long_tail_flag(ranked_top50, long_tail_map)

    summary = {
        "tail_quantile": tail_quantile,
        "tail_threshold_movie_popularity": threshold,
        "merged_recall": _summarize_pool("merged_recall", merged_recall),
        "rank_candidates": _summarize_pool("rank_candidates", rank_candidates),
        "ranked_top50": _summarize_pool("ranked_top50", ranked_top50),
        "coverage_metrics": {
            "merged_recall_unique_recipe_coverage": _unique_recipe_coverage(merged_recall),
            "rank_candidates_unique_recipe_coverage": _unique_recipe_coverage(rank_candidates),
            "ranked_top50_unique_recipe_coverage": _unique_recipe_coverage(ranked_top50),
        },
    }
    return summary


def main() -> None:
    args = parse_args()
    summary = evaluate_long_tail_effect(
        merged_recall_path=args.merged_recall,
        movie_profile_path=args.movie_profile,
        rank_candidates_path=args.rank_candidates,
        ranked_top50_path=args.ranked_top50,
        tail_quantile=args.tail_quantile,
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Long-tail evaluation summary written to %s", output_path)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
