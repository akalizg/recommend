"""
Score Spark recall candidates with the offline XGBoost rank model.

Outputs a per-user Top-N ranked CSV for offline inspection/evaluation.
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
DEFAULT_CANDIDATES = PROJECT_ROOT / "data" / "rank" / "rank_candidates.csv"
DEFAULT_MODEL = PROJECT_ROOT / "models" / "xgb_rank_model_spark.json"
DEFAULT_FEATURES = PROJECT_ROOT / "models" / "xgb_rank_feature_columns.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "rank" / "ranked_top50.csv"

OUTPUT_COLUMNS = [
    "userId",
    "movieId",
    "rank_position",
    "rank_score",
    "label",
    "als_score",
    "itemcf_score",
    "merged_recall_score",
    "recall_source_count",
    "genre_match_score",
    "movie_avg_rating",
    "movie_popularity",
]

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Predict offline Top-N rankings from Spark-exported features.")
    parser.add_argument("--candidates", default=str(DEFAULT_CANDIDATES), help="rank_candidates.csv input.")
    parser.add_argument("--model", default=str(DEFAULT_MODEL), help="XGBoost model input.")
    parser.add_argument("--features", default=str(DEFAULT_FEATURES), help="Feature columns JSON input.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Ranked Top-N CSV output.")
    parser.add_argument("--top-n", type=int, default=50, help="Maximum recommendations per user.")
    return parser.parse_args()


def _require_xgboost():
    try:
        import xgboost as xgb
    except ImportError as exc:
        raise RuntimeError("xgboost is required. Install dependencies with `pip install -r requirements.txt`.") from exc
    return xgb


def _read_feature_columns(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(f"Feature column file not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not all(isinstance(item, str) for item in data):
        raise ValueError(f"Feature column file must contain a JSON string list: {path}")
    return data


def predict_from_spark_features(
    candidates_path: str | Path | None = None,
    model_path: str | Path | None = None,
    feature_path: str | Path | None = None,
    output_path: str | Path | None = None,
    top_n: int = 50,
) -> dict:
    xgb = _require_xgboost()
    candidates_file = Path(candidates_path).resolve() if candidates_path else DEFAULT_CANDIDATES
    model_file = Path(model_path).resolve() if model_path else DEFAULT_MODEL
    feature_file = Path(feature_path).resolve() if feature_path else DEFAULT_FEATURES
    output_file = Path(output_path).resolve() if output_path else DEFAULT_OUTPUT

    if not candidates_file.exists():
        raise FileNotFoundError(f"Candidate input not found: {candidates_file}")
    if not model_file.exists():
        raise FileNotFoundError(f"XGBoost model not found: {model_file}")
    feature_columns = _read_feature_columns(feature_file)

    logger.info("candidate input: %s", candidates_file)
    logger.info("model path: %s", model_file)
    logger.info("feature columns input: %s", feature_file)
    logger.info("output path: %s", output_file)
    logger.info("top_n: %s", top_n)

    df = pd.read_csv(candidates_file)
    required = {"userId", "movieId", "label", *feature_columns}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"rank_candidates.csv is missing required columns: {missing}")

    for col in feature_columns:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    df["label"] = pd.to_numeric(df["label"], errors="coerce").fillna(0).astype(int).clip(0, 1)
    df["userId"] = pd.to_numeric(df["userId"], errors="coerce").astype("Int64")
    df["movieId"] = pd.to_numeric(df["movieId"], errors="coerce").astype("Int64")
    df = df.dropna(subset=["userId", "movieId"]).copy()
    df["userId"] = df["userId"].astype(int)
    df["movieId"] = df["movieId"].astype(int)

    model = xgb.XGBClassifier()
    model.load_model(str(model_file))

    X = df[feature_columns].astype(np.float32)
    rank_scores = model.predict_proba(X)[:, 1]
    if not np.isfinite(rank_scores).all():
        raise ValueError("rank_score contains non-finite values.")
    if rank_scores.min() < 0 or rank_scores.max() > 1:
        raise ValueError("rank_score must be in [0, 1].")

    df["rank_score"] = rank_scores.astype(float)
    keep_aux = [
        "als_score",
        "itemcf_score",
        "merged_recall_score",
        "recall_source_count",
        "genre_match_score",
        "movie_avg_rating",
        "movie_popularity",
    ]
    for col in keep_aux:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    ranked = (
        df.sort_values(
            ["userId", "rank_score", "merged_recall_score", "movieId"],
            ascending=[True, False, False, True],
            kind="mergesort",
        )
        .groupby("userId", group_keys=False)
        .head(top_n)
        .copy()
    )
    ranked["rank_position"] = ranked.groupby("userId").cumcount() + 1
    ranked = ranked[OUTPUT_COLUMNS].copy()
    ranked["rank_score"] = ranked["rank_score"].round(8)

    output_file.parent.mkdir(parents=True, exist_ok=True)
    ranked.to_csv(output_file, index=False)
    if not output_file.exists():
        raise RuntimeError(f"ranked_top50.csv was not written: {output_file}")
    if ranked.empty:
        raise ValueError("ranked output is empty.")
    if ranked.groupby("userId").size().max() > top_n:
        raise ValueError(f"Quality check failed: some users have more than top_n={top_n} rows.")
    if ranked["rank_score"].isna().any() or not ranked["rank_score"].between(0, 1).all():
        raise ValueError("Quality check failed: rank_score contains nulls or values outside [0, 1].")
    if ranked.groupby("userId")["rank_position"].min().min() != 1:
        raise ValueError("Quality check failed: rank_position must start at 1 for every user.")
    missing_output = sorted(set(OUTPUT_COLUMNS) - set(ranked.columns))
    if missing_output:
        raise ValueError(f"Quality check failed: ranked output missing columns {missing_output}.")

    user_count = int(ranked["userId"].nunique())
    movie_count = int(ranked["movieId"].nunique())
    ranked_rows = int(len(ranked))
    average_topn = float(ranked.groupby("userId").size().mean()) if ranked_rows else 0.0
    sample_rows = ranked.head(10).to_dict(orient="records")

    summary = {
        "candidate_rows": int(len(df)),
        "user_count": user_count,
        "movie_count": movie_count,
        "model_path": str(model_file),
        "feature_count": len(feature_columns),
        "ranked_rows": ranked_rows,
        "average_topn_per_user": average_topn,
        "output_path": str(output_file),
        "top_10_sample_rows": sample_rows,
    }
    logger.info("candidate rows: %s", summary["candidate_rows"])
    logger.info("user count: %s", user_count)
    logger.info("movie count: %s", movie_count)
    logger.info("model path: %s", model_file)
    logger.info("feature count: %s", len(feature_columns))
    logger.info("ranked rows: %s", ranked_rows)
    logger.info("average topN per user: %.4f", average_topn)
    logger.info("output path: %s", output_file)
    logger.info("top 10 sample rows:")
    for row in sample_rows:
        logger.info("  %s", row)
    logger.info("quality validation result: success")
    return summary


def main() -> None:
    args = parse_args()
    try:
        predict_from_spark_features(args.candidates, args.model, args.features, args.output, args.top_n)
    except Exception as exc:
        logger.error("%s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
