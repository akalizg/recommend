"""
Offline recommendation metrics for recall/rank/MMR outputs.

Metrics: Precision@K, Recall@K, NDCG@K, HitRate@K, Coverage@K, Diversity@K.
No novelty or long-tail metrics are computed in this stage.
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
DEFAULT_TEST = PROJECT_ROOT / "data" / "processed" / "test_ratings.csv"
DEFAULT_MOVIE_PROFILE = PROJECT_ROOT / "data" / "features" / "movie_profile.csv"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "eval"
DEFAULT_KS = (5, 10, 20, 50)

MODEL_FILES = {
    "ALS": PROJECT_ROOT / "data" / "recall" / "als_recall.csv",
    "ItemCF": PROJECT_ROOT / "data" / "recall" / "itemcf_recall.csv",
    "FAISS_HNSW": PROJECT_ROOT / "data" / "recall" / "faiss_hnsw_recall.csv",
    "Merged_Recall": PROJECT_ROOT / "data" / "recall" / "merged_recall_candidates.csv",
    "XGBoost_Top50": PROJECT_ROOT / "data" / "rank" / "ranked_top50.csv",
    "LightGBM_Top50": PROJECT_ROOT / "data" / "rank" / "enhanced" / "ranked_top50_enhanced.csv",
    "LightGBM_MMR_Top10": PROJECT_ROOT / "data" / "rank" / "ranked_top10_mmr.csv",
}

METRIC_COLUMNS = [
    "model_name",
    "k",
    "precision",
    "recall",
    "ndcg",
    "hit_rate",
    "coverage",
    "diversity",
    "evaluated_users",
    "recommended_items",
]

FORBIDDEN_METRIC_PARTS = ("novelty", "longtail", "long_tail")

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate offline recommendation metrics.")
    parser.add_argument("--test", default=str(DEFAULT_TEST), help="test_ratings.csv input.")
    parser.add_argument("--movie-profile", default=str(DEFAULT_MOVIE_PROFILE), help="movie_profile.csv input.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Evaluation output directory.")
    parser.add_argument("--ks", default="5,10,20,50", help="Comma-separated K values.")
    return parser.parse_args()


def _parse_ks(value: str | Iterable[int]) -> list[int]:
    if isinstance(value, str):
        ks = [int(item.strip()) for item in value.split(",") if item.strip()]
    else:
        ks = [int(item) for item in value]
    if not ks or any(k <= 0 for k in ks):
        raise ValueError("K values must be positive integers.")
    return sorted(set(ks))


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
    return len(left_set & right_set) / len(union) if union else 0.0


def _rank_recommendations(df: pd.DataFrame) -> pd.DataFrame:
    required = {"userId", "movieId"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"Recommendation file missing required columns: {missing}")

    result = df.copy()
    result["userId"] = pd.to_numeric(result["userId"], errors="coerce")
    result["movieId"] = pd.to_numeric(result["movieId"], errors="coerce")
    result = result.dropna(subset=["userId", "movieId"]).copy()
    result["userId"] = result["userId"].astype(int)
    result["movieId"] = result["movieId"].astype(int)

    if "rank_position" in result.columns:
        result["_sort_a"] = pd.to_numeric(result["rank_position"], errors="coerce").fillna(10**9)
        result["_sort_b"] = 0.0
        result = result.sort_values(["userId", "_sort_a", "movieId"], ascending=[True, True, True])
    else:
        score_col = None
        for candidate in ["mmr_score", "rank_score", "merged_recall_score", "recall_score", "itemcf_score", "als_score"]:
            if candidate in result.columns:
                score_col = candidate
                break
        if score_col is None:
            result["_sort_b"] = 0.0
        else:
            result["_sort_b"] = pd.to_numeric(result[score_col], errors="coerce").fillna(0.0)
        result = result.sort_values(["userId", "_sort_b", "movieId"], ascending=[True, False, True])

    return result.drop_duplicates(["userId", "movieId"], keep="first")


def _dcg(binary_hits: list[int]) -> float:
    return sum(rel / math.log2(idx + 2) for idx, rel in enumerate(binary_hits))


def _diversity_for_movies(movie_ids: list[int], genres_by_movie: dict[int, set[str]]) -> float:
    if len(movie_ids) < 2:
        return 0.0
    similarities = []
    for i in range(len(movie_ids)):
        for j in range(i + 1, len(movie_ids)):
            similarities.append(genre_jaccard(genres_by_movie.get(movie_ids[i], set()), genres_by_movie.get(movie_ids[j], set())))
    return 1.0 - (sum(similarities) / len(similarities) if similarities else 0.0)


def _evaluate_model(
    model_name: str,
    recs: pd.DataFrame,
    relevant_by_user: dict[int, set[int]],
    all_movie_count: int,
    genres_by_movie: dict[int, set[str]],
    ks: list[int],
) -> list[dict]:
    ranked = _rank_recommendations(recs)
    recs_by_user = ranked.groupby("userId")["movieId"].apply(lambda values: values.astype(int).tolist()).to_dict()
    users = sorted(set(recs_by_user) & set(relevant_by_user.keys()))
    rows: list[dict] = []

    for k in ks:
        precision_values = []
        recall_values = []
        ndcg_values = []
        hit_values = []
        diversity_values = []
        recommended_items: set[int] = set()

        for user_id in users:
            relevant = relevant_by_user.get(user_id, set())
            if not relevant:
                continue
            user_recs = recs_by_user.get(user_id, [])[:k]
            recommended_items.update(user_recs)
            hits = [1 if movie_id in relevant else 0 for movie_id in user_recs]
            hit_count = sum(hits)
            precision_values.append(hit_count / k)
            recall_values.append(hit_count / len(relevant))
            hit_values.append(1.0 if hit_count > 0 else 0.0)

            idcg_len = min(len(relevant), k)
            idcg = _dcg([1] * idcg_len)
            ndcg_values.append(_dcg(hits) / idcg if idcg > 0 else 0.0)
            diversity_values.append(_diversity_for_movies(user_recs, genres_by_movie))

        evaluated_users = len(precision_values)
        row = {
            "model_name": model_name,
            "k": k,
            "precision": float(sum(precision_values) / evaluated_users) if evaluated_users else 0.0,
            "recall": float(sum(recall_values) / evaluated_users) if evaluated_users else 0.0,
            "ndcg": float(sum(ndcg_values) / evaluated_users) if evaluated_users else 0.0,
            "hit_rate": float(sum(hit_values) / evaluated_users) if evaluated_users else 0.0,
            "coverage": float(len(recommended_items) / all_movie_count) if all_movie_count else 0.0,
            "diversity": float(sum(diversity_values) / evaluated_users) if evaluated_users else 0.0,
            "evaluated_users": evaluated_users,
            "recommended_items": len(recommended_items),
        }
        rows.append(row)
    return rows


def _best_model(metrics: pd.DataFrame, metric: str, k: int = 10) -> str | None:
    subset = metrics[metrics["k"] == k]
    if subset.empty:
        return None
    return str(subset.sort_values([metric, "model_name"], ascending=[False, True]).iloc[0]["model_name"])


def evaluate_offline_metrics(
    test_path: str | Path | None = None,
    movie_profile_path: str | Path | None = None,
    output_dir: str | Path | None = None,
    ks: str | Iterable[int] = DEFAULT_KS,
    model_files: dict[str, str | Path] | None = None,
) -> dict:
    test_file = Path(test_path).resolve() if test_path else DEFAULT_TEST
    movie_profile_file = Path(movie_profile_path).resolve() if movie_profile_path else DEFAULT_MOVIE_PROFILE
    output_path = Path(output_dir).resolve() if output_dir else DEFAULT_OUTPUT_DIR
    output_metrics = output_path / "offline_metrics.csv"
    output_summary = output_path / "eval_summary.json"
    k_values = _parse_ks(ks)
    model_path_map = {name: Path(path).resolve() for name, path in (model_files or MODEL_FILES).items()}

    if not test_file.exists():
        raise FileNotFoundError(f"Test ratings input not found: {test_file}")
    if not movie_profile_file.exists():
        raise FileNotFoundError(f"Movie profile input not found: {movie_profile_file}")

    logger.info("test input: %s", test_file)
    logger.info("movie profile input: %s", movie_profile_file)
    logger.info("output directory: %s", output_path)
    logger.info("K values: %s", k_values)

    test = pd.read_csv(test_file)
    movie_profile = pd.read_csv(movie_profile_file)
    for col in ["userId", "movieId", "rating"]:
        if col not in test.columns:
            raise ValueError(f"test_ratings.csv missing column: {col}")
    if not {"movieId", "genres"}.issubset(movie_profile.columns):
        raise ValueError("movie_profile.csv must contain movieId and genres.")

    test["userId"] = pd.to_numeric(test["userId"], errors="coerce")
    test["movieId"] = pd.to_numeric(test["movieId"], errors="coerce")
    test["rating"] = pd.to_numeric(test["rating"], errors="coerce")
    test = test.dropna(subset=["userId", "movieId", "rating"]).copy()
    test["userId"] = test["userId"].astype(int)
    test["movieId"] = test["movieId"].astype(int)
    relevant = test[test["rating"] >= 4.0]
    relevant_by_user = relevant.groupby("userId")["movieId"].apply(lambda s: set(s.astype(int))).to_dict()

    movie_profile["movieId"] = pd.to_numeric(movie_profile["movieId"], errors="coerce")
    movie_profile = movie_profile.dropna(subset=["movieId"]).copy()
    movie_profile["movieId"] = movie_profile["movieId"].astype(int)
    genres_by_movie = dict(zip(movie_profile["movieId"], movie_profile["genres"].map(_parse_genres)))
    all_movie_count = int(movie_profile["movieId"].nunique())

    metric_rows: list[dict] = []
    evaluated_files: dict[str, str] = {}
    skipped_files: dict[str, str] = {}
    for model_name, path in model_path_map.items():
        if not path.exists():
            skipped_files[model_name] = str(path)
            logger.warning("Skipping missing model file: %s -> %s", model_name, path)
            continue
        recs = pd.read_csv(path)
        model_rows = _evaluate_model(model_name, recs, relevant_by_user, all_movie_count, genres_by_movie, k_values)
        metric_rows.extend(model_rows)
        evaluated_files[model_name] = str(path)
        at10 = next((row for row in model_rows if row["k"] == 10), None)
        if at10:
            logger.info(
                "%s @10 precision=%.6f recall=%.6f ndcg=%.6f hit_rate=%.6f coverage=%.6f diversity=%.6f",
                model_name,
                at10["precision"],
                at10["recall"],
                at10["ndcg"],
                at10["hit_rate"],
                at10["coverage"],
                at10["diversity"],
            )

    if not metric_rows:
        raise ValueError("No recommendation files were evaluated.")

    metrics = pd.DataFrame(metric_rows, columns=METRIC_COLUMNS)
    for col in ["precision", "recall", "ndcg", "hit_rate", "coverage", "diversity"]:
        if not metrics[col].between(0, 1).all():
            raise ValueError(f"Metric {col} contains values outside [0, 1].")
    forbidden = [col for col in metrics.columns if any(part in col.lower() for part in FORBIDDEN_METRIC_PARTS)]
    if forbidden:
        raise ValueError(f"Forbidden novelty/long-tail metrics found: {forbidden}")

    output_path.mkdir(parents=True, exist_ok=True)
    metrics.to_csv(output_metrics, index=False)
    if not output_metrics.exists():
        raise RuntimeError(f"offline_metrics.csv was not written: {output_metrics}")

    xgb = metrics[(metrics["model_name"] == "XGBoost_Top50") & (metrics["k"] == 10)]
    mmr = metrics[(metrics["model_name"] == "XGBoost_MMR_Top10") & (metrics["k"] == 10)]
    notes = [
        "Only test_ratings.csv is used as evaluation target; it is not used to build profiles or train ranking models.",
        "This stage computes Precision/Recall/NDCG/HitRate/Coverage/Diversity only; novelty and long-tail metrics are intentionally excluded.",
    ]
    if not xgb.empty and not mmr.empty:
        if float(mmr.iloc[0]["precision"]) < float(xgb.iloc[0]["precision"]) and float(mmr.iloc[0]["diversity"]) > float(
            xgb.iloc[0]["diversity"]
        ):
            notes.append("MMR reranking may trade part of relevance for higher recommendation-list diversity.")
        elif float(mmr.iloc[0]["diversity"]) > float(xgb.iloc[0]["diversity"]):
            notes.append("MMR reranking improves diversity on this run while keeping comparable relevance metrics.")
        else:
            notes.append("MMR reranking did not improve diversity on this run; tune lambda_rel or candidate quality before online use.")

    summary = {
        "best_precision_model": _best_model(metrics, "precision", 10),
        "best_recall_model": _best_model(metrics, "recall", 10),
        "best_ndcg_model": _best_model(metrics, "ndcg", 10),
        "best_diversity_model": _best_model(metrics, "diversity", 10),
        "evaluated_model_files": evaluated_files,
        "skipped_model_files": skipped_files,
        "test_rows": int(len(test)),
        "relevant_test_rows": int(len(relevant)),
        "movie_profile_rows": int(len(movie_profile)),
        "ks": k_values,
        "notes": notes,
    }
    output_summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    if not output_summary.exists():
        raise RuntimeError(f"eval_summary.json was not written: {output_summary}")

    logger.info("test rows: %s", len(test))
    logger.info("relevant test rows: %s", len(relevant))
    logger.info("movie profile rows: %s", len(movie_profile))
    logger.info("evaluated model files: %s", list(evaluated_files.keys()))
    logger.info("offline metrics output: %s", output_metrics)
    logger.info("eval summary output: %s", output_summary)
    logger.info("quality validation result: success")
    return {
        "metrics_path": str(output_metrics),
        "summary_path": str(output_summary),
        "metrics_rows": int(len(metrics)),
        "evaluated_models": list(evaluated_files.keys()),
        "summary": summary,
    }


def main() -> None:
    args = parse_args()
    try:
        evaluate_offline_metrics(args.test, args.movie_profile, args.output_dir, args.ks)
    except Exception as exc:
        logger.error("%s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
