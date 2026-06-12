"""
Tune ALS + ItemCF recall merge weights offline.

The script writes optimized recall candidates to a new file and does not
overwrite the original merged_recall_candidates.csv.
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from pathlib import Path
from typing import Iterable

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ALS = PROJECT_ROOT / "data" / "recall" / "als_recall.csv"
DEFAULT_ITEMCF = PROJECT_ROOT / "data" / "recall" / "itemcf_recall.csv"
DEFAULT_TEST = PROJECT_ROOT / "data" / "processed" / "test_ratings.csv"
DEFAULT_MOVIE_PROFILE = PROJECT_ROOT / "data" / "features" / "movie_profile.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "eval" / "recall_weight_tuning.csv"
DEFAULT_BEST_OUTPUT = PROJECT_ROOT / "data" / "eval" / "best_recall_weights.json"
DEFAULT_OPTIMIZED_RECALL = PROJECT_ROOT / "data" / "recall" / "merged_recall_candidates_optimized.csv"

OUTPUT_COLUMNS = [
    "userId",
    "movieId",
    "als_score",
    "itemcf_score",
    "embedding_score",
    "lightgcn_score",
    "content_score",
    "hot_score",
    "is_als_recall",
    "is_itemcf_recall",
    "is_embedding_recall",
    "is_lightgcn_recall",
    "is_content_recall",
    "is_hot_recall",
    "recall_source_count",
    "merged_recall_score",
]

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tune ALS/ItemCF recall merge weights.")
    parser.add_argument("--als", default=str(DEFAULT_ALS), help="ALS recall CSV.")
    parser.add_argument("--itemcf", default=str(DEFAULT_ITEMCF), help="ItemCF recall CSV.")
    parser.add_argument("--test", default=str(DEFAULT_TEST), help="test_ratings.csv input.")
    parser.add_argument("--movie-profile", default=str(DEFAULT_MOVIE_PROFILE), help="movie_profile.csv input.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Tuning CSV output.")
    parser.add_argument("--best-output", default=str(DEFAULT_BEST_OUTPUT), help="Best weight JSON output.")
    parser.add_argument("--optimized-recall", default=str(DEFAULT_OPTIMIZED_RECALL), help="Optimized merged recall CSV.")
    parser.add_argument("--top-n", type=int, default=100, help="Top-N candidates kept per user.")
    return parser.parse_args()


def _parse_genres(value: object) -> set[str]:
    if pd.isna(value):
        return set()
    text = str(value).strip()
    if not text or text == "(no genres listed)":
        return set()
    return {item.strip().lower() for item in text.split("|") if item.strip() and item.strip() != "(no genres listed)"}


def _jaccard(left: Iterable[str], right: Iterable[str]) -> float:
    left_set = set(left)
    right_set = set(right)
    if not left_set or not right_set:
        return 0.0
    union = left_set | right_set
    return len(left_set & right_set) / len(union) if union else 0.0


def _dcg(hits: list[int]) -> float:
    return sum(rel / math.log2(idx + 2) for idx, rel in enumerate(hits))


def _diversity(movie_ids: list[int], genres_by_movie: dict[int, set[str]]) -> float:
    if len(movie_ids) < 2:
        return 0.0
    sims = []
    for i in range(len(movie_ids)):
        for j in range(i + 1, len(movie_ids)):
            sims.append(_jaccard(genres_by_movie.get(movie_ids[i], set()), genres_by_movie.get(movie_ids[j], set())))
    return 1.0 - (sum(sims) / len(sims) if sims else 0.0)


def _read_recall(path: Path, expected_type: str, score_col: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Recall file not found: {path}")
    df = pd.read_csv(path)
    required = {"userId", "movieId", "recall_score"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"{path} missing required columns: {missing}")
    if "recall_type" in df.columns:
        df = df[df["recall_type"] == expected_type].copy()
    df["userId"] = pd.to_numeric(df["userId"], errors="coerce")
    df["movieId"] = pd.to_numeric(df["movieId"], errors="coerce")
    df[score_col] = pd.to_numeric(df["recall_score"], errors="coerce")
    df = df.dropna(subset=["userId", "movieId", score_col]).copy()
    df["userId"] = df["userId"].astype(int)
    df["movieId"] = df["movieId"].astype(int)
    return df[["userId", "movieId", score_col]].drop_duplicates(["userId", "movieId"], keep="first")


def _normalize_by_user(df: pd.DataFrame, score_col: str, flag_col: str, output_col: str) -> pd.Series:
    normalized = pd.Series(0.0, index=df.index)
    present = df[flag_col] == 1
    for _, idx in df[present].groupby("userId").groups.items():
        scores = df.loc[idx, score_col]
        min_score = scores.min()
        max_score = scores.max()
        if max_score == min_score:
            normalized.loc[idx] = 1.0
        else:
            normalized.loc[idx] = (scores - min_score) / (max_score - min_score)
    return normalized.rename(output_col)


def _build_base_recall(als: pd.DataFrame, itemcf: pd.DataFrame) -> pd.DataFrame:
    merged = als.merge(itemcf, on=["userId", "movieId"], how="outer")
    merged["is_als_recall"] = merged["als_score"].notna().astype(int)
    merged["is_itemcf_recall"] = merged["itemcf_score"].notna().astype(int)
    merged["als_score"] = merged["als_score"].fillna(0.0)
    merged["itemcf_score"] = merged["itemcf_score"].fillna(0.0)
    merged["normalized_als_score"] = _normalize_by_user(merged, "als_score", "is_als_recall", "normalized_als_score")
    merged["normalized_itemcf_score"] = _normalize_by_user(
        merged, "itemcf_score", "is_itemcf_recall", "normalized_itemcf_score"
    )
    merged["recall_source_count"] = merged["is_als_recall"] + merged["is_itemcf_recall"]
    return merged


def _topn_for_weights(base: pd.DataFrame, als_weight: float, itemcf_weight: float, source_bonus: float, top_n: int) -> pd.DataFrame:
    result = base.copy()
    result["merged_recall_score"] = (
        als_weight * result["normalized_als_score"]
        + itemcf_weight * result["normalized_itemcf_score"]
        + source_bonus * result["recall_source_count"]
    )
    return (
        result.sort_values(["userId", "merged_recall_score", "movieId"], ascending=[True, False, True], kind="mergesort")
        .groupby("userId", group_keys=False)
        .head(top_n)
        .copy()
    )


def _evaluate_at_10(
    recs: pd.DataFrame,
    relevant_by_user: dict[int, set[int]],
    movie_count: int,
    genres_by_movie: dict[int, set[str]],
) -> dict:
    users = sorted(set(recs["userId"].unique()) & set(relevant_by_user.keys()))
    precision = []
    recall = []
    ndcg = []
    hit_rate = []
    diversity = []
    recommended: set[int] = set()

    for user_id in users:
        relevant = relevant_by_user[user_id]
        top_movies = recs[recs["userId"] == user_id]["movieId"].head(10).astype(int).tolist()
        recommended.update(top_movies)
        hits = [1 if movie_id in relevant else 0 for movie_id in top_movies]
        hit_count = sum(hits)
        precision.append(hit_count / 10)
        recall.append(hit_count / len(relevant))
        hit_rate.append(1.0 if hit_count else 0.0)
        idcg = _dcg([1] * min(len(relevant), 10))
        ndcg.append(_dcg(hits) / idcg if idcg else 0.0)
        diversity.append(_diversity(top_movies, genres_by_movie))

    evaluated = len(precision)
    return {
        "precision_at_10": float(sum(precision) / evaluated) if evaluated else 0.0,
        "recall_at_10": float(sum(recall) / evaluated) if evaluated else 0.0,
        "ndcg_at_10": float(sum(ndcg) / evaluated) if evaluated else 0.0,
        "hit_rate_at_10": float(sum(hit_rate) / evaluated) if evaluated else 0.0,
        "coverage_at_10": float(len(recommended) / movie_count) if movie_count else 0.0,
        "diversity_at_10": float(sum(diversity) / evaluated) if evaluated else 0.0,
    }


def _format_output(topn: pd.DataFrame) -> pd.DataFrame:
    output = topn.copy()
    for col in ["embedding_score", "lightgcn_score", "content_score", "hot_score"]:
        output[col] = 0.0
    for col in ["is_embedding_recall", "is_lightgcn_recall", "is_content_recall", "is_hot_recall"]:
        output[col] = 0
    return output[OUTPUT_COLUMNS]


def tune_recall_weights(
    als_path: str | Path | None = None,
    itemcf_path: str | Path | None = None,
    test_path: str | Path | None = None,
    movie_profile_path: str | Path | None = None,
    output_path: str | Path | None = None,
    best_output_path: str | Path | None = None,
    optimized_recall_path: str | Path | None = None,
    top_n: int = 100,
) -> dict:
    als_file = Path(als_path).resolve() if als_path else DEFAULT_ALS
    itemcf_file = Path(itemcf_path).resolve() if itemcf_path else DEFAULT_ITEMCF
    test_file = Path(test_path).resolve() if test_path else DEFAULT_TEST
    movie_file = Path(movie_profile_path).resolve() if movie_profile_path else DEFAULT_MOVIE_PROFILE
    output_file = Path(output_path).resolve() if output_path else DEFAULT_OUTPUT
    best_file = Path(best_output_path).resolve() if best_output_path else DEFAULT_BEST_OUTPUT
    optimized_file = Path(optimized_recall_path).resolve() if optimized_recall_path else DEFAULT_OPTIMIZED_RECALL

    logger.info("ALS recall input: %s", als_file)
    logger.info("ItemCF recall input: %s", itemcf_file)
    logger.info("test input: %s", test_file)
    logger.info("movie profile input: %s", movie_file)
    logger.info("topN per user: %s", top_n)

    als = _read_recall(als_file, "als", "als_score")
    itemcf = _read_recall(itemcf_file, "itemcf", "itemcf_score")
    base = _build_base_recall(als, itemcf)

    test = pd.read_csv(test_file)
    test["userId"] = pd.to_numeric(test["userId"], errors="coerce")
    test["movieId"] = pd.to_numeric(test["movieId"], errors="coerce")
    test["rating"] = pd.to_numeric(test["rating"], errors="coerce")
    test = test.dropna(subset=["userId", "movieId", "rating"]).copy()
    test["userId"] = test["userId"].astype(int)
    test["movieId"] = test["movieId"].astype(int)
    relevant_by_user = test[test["rating"] >= 4.0].groupby("userId")["movieId"].apply(lambda s: set(s.astype(int))).to_dict()

    movie_profile = pd.read_csv(movie_file)
    movie_profile["movieId"] = pd.to_numeric(movie_profile["movieId"], errors="coerce")
    movie_profile = movie_profile.dropna(subset=["movieId"]).copy()
    movie_profile["movieId"] = movie_profile["movieId"].astype(int)
    genres_by_movie = dict(zip(movie_profile["movieId"], movie_profile["genres"].map(_parse_genres)))
    movie_count = int(movie_profile["movieId"].nunique())

    rows = []
    best_row: dict | None = None
    best_topn: pd.DataFrame | None = None
    for i in range(11):
        als_weight = round(i / 10, 1)
        itemcf_weight = round(1.0 - als_weight, 1)
        for source_bonus in [0.0, 0.05, 0.1]:
            topn = _topn_for_weights(base, als_weight, itemcf_weight, source_bonus, top_n)
            metrics = _evaluate_at_10(topn, relevant_by_user, movie_count, genres_by_movie)
            row = {
                "als_weight": als_weight,
                "itemcf_weight": itemcf_weight,
                "source_bonus": source_bonus,
                **metrics,
            }
            rows.append(row)
            if best_row is None or (
                row["ndcg_at_10"],
                row["recall_at_10"],
                row["diversity_at_10"],
            ) > (
                best_row["ndcg_at_10"],
                best_row["recall_at_10"],
                best_row["diversity_at_10"],
            ):
                best_row = row
                best_topn = topn

    if best_row is None or best_topn is None:
        raise ValueError("No recall weight candidates were evaluated.")

    tuning = pd.DataFrame(rows).sort_values(
        ["ndcg_at_10", "recall_at_10", "diversity_at_10"], ascending=[False, False, False]
    )
    output_file.parent.mkdir(parents=True, exist_ok=True)
    best_file.parent.mkdir(parents=True, exist_ok=True)
    optimized_file.parent.mkdir(parents=True, exist_ok=True)
    tuning.to_csv(output_file, index=False)
    _format_output(best_topn).to_csv(optimized_file, index=False)
    best_payload = {
        **best_row,
        "selection_rule": "maximize ndcg_at_10, then recall_at_10, then diversity_at_10",
        "optimized_recall_path": str(optimized_file),
    }
    best_file.write_text(json.dumps(best_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    for path in [output_file, best_file, optimized_file]:
        if not path.exists():
            raise RuntimeError(f"Expected output was not written: {path}")
    for metric in [
        "precision_at_10",
        "recall_at_10",
        "ndcg_at_10",
        "hit_rate_at_10",
        "coverage_at_10",
        "diversity_at_10",
    ]:
        if not tuning[metric].between(0, 1).all():
            raise ValueError(f"{metric} contains values outside [0, 1].")

    logger.info("evaluated weight combinations: %s", len(tuning))
    logger.info(
        "best weights: als=%.1f itemcf=%.1f source_bonus=%.2f ndcg@10=%.6f recall@10=%.6f diversity@10=%.6f",
        best_row["als_weight"],
        best_row["itemcf_weight"],
        best_row["source_bonus"],
        best_row["ndcg_at_10"],
        best_row["recall_at_10"],
        best_row["diversity_at_10"],
    )
    logger.info("tuning output: %s", output_file)
    logger.info("best weights output: %s", best_file)
    logger.info("optimized recall output: %s", optimized_file)
    logger.info("quality validation result: success")
    return {
        "tuning_path": str(output_file),
        "best_weights_path": str(best_file),
        "optimized_recall_path": str(optimized_file),
        "evaluated_combinations": int(len(tuning)),
        "best": best_payload,
        "optimized_rows": int(len(best_topn)),
    }


def main() -> None:
    args = parse_args()
    try:
        tune_recall_weights(
            args.als,
            args.itemcf,
            args.test,
            args.movie_profile,
            args.output,
            args.best_output,
            args.optimized_recall,
            args.top_n,
        )
    except Exception as exc:
        logger.error("%s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
