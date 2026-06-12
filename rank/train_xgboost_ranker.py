"""
Train an optimized XGBoost ranking model and score optimized candidates.

The primary model is XGBRanker with objective=rank:ndcg. If the local
environment cannot train XGBRanker, the script falls back to XGBClassifier and
records the fallback reason in metrics.
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TRAIN = PROJECT_ROOT / "data" / "rank" / "rank_train.csv"
DEFAULT_CANDIDATES = PROJECT_ROOT / "data" / "rank" / "rank_candidates_optimized.csv"
DEFAULT_FEATURES = PROJECT_ROOT / "data" / "rank" / "rank_feature_columns.json"
DEFAULT_MODEL_OUTPUT = PROJECT_ROOT / "models" / "xgb_ranker_model_spark.json"
DEFAULT_FEATURE_OUTPUT = PROJECT_ROOT / "models" / "xgb_ranker_feature_columns.json"
DEFAULT_METRICS_OUTPUT = PROJECT_ROOT / "data" / "rank" / "xgb_ranker_train_metrics.json"
DEFAULT_IMPORTANCE_OUTPUT = PROJECT_ROOT / "data" / "rank" / "xgb_ranker_feature_importance.csv"
DEFAULT_RANKED_OUTPUT = PROJECT_ROOT / "data" / "rank" / "ranked_top50_ranker.csv"

RANKED_OUTPUT_COLUMNS = [
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
    parser = argparse.ArgumentParser(description="Train XGBoost Ranker from Spark ranking features.")
    parser.add_argument("--train", default=str(DEFAULT_TRAIN), help="rank_train.csv input.")
    parser.add_argument("--candidates", default=str(DEFAULT_CANDIDATES), help="rank_candidates_optimized.csv input.")
    parser.add_argument("--features", default=str(DEFAULT_FEATURES), help="Feature column JSON input.")
    parser.add_argument("--model-output", default=str(DEFAULT_MODEL_OUTPUT), help="XGBoost ranker model output.")
    parser.add_argument("--feature-output", default=str(DEFAULT_FEATURE_OUTPUT), help="Model feature columns output.")
    parser.add_argument("--metrics-output", default=str(DEFAULT_METRICS_OUTPUT), help="Training metrics JSON output.")
    parser.add_argument("--importance-output", default=str(DEFAULT_IMPORTANCE_OUTPUT), help="Feature importance CSV output.")
    parser.add_argument("--ranked-output", default=str(DEFAULT_RANKED_OUTPUT), help="Ranked Top50 output.")
    parser.add_argument("--n-estimators", type=int, default=200)
    parser.add_argument("--max-depth", type=int, default=5)
    parser.add_argument("--learning-rate", type=float, default=0.05)
    parser.add_argument("--valid-user-ratio", type=float, default=0.2)
    parser.add_argument("--top-n", type=int, default=50)
    return parser.parse_args()


def _require_dependencies():
    try:
        import xgboost as xgb
        from sklearn.model_selection import train_test_split
    except ImportError as exc:
        raise RuntimeError("xgboost and scikit-learn are required. Install dependencies with `pip install -r requirements.txt`.") from exc
    return xgb, train_test_split


def _read_features(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(f"Feature column file not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not all(isinstance(item, str) for item in data):
        raise ValueError("Feature column file must be a JSON string list.")
    return data


def _load_rank_data(path: Path, feature_columns: list[str]) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Rank data input not found: {path}")
    df = pd.read_csv(path)
    required = {"userId", "movieId", "label", *feature_columns}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"{path} missing required columns: {missing}")
    df["userId"] = pd.to_numeric(df["userId"], errors="coerce")
    df["movieId"] = pd.to_numeric(df["movieId"], errors="coerce")
    df["label"] = pd.to_numeric(df["label"], errors="coerce").fillna(0).astype(int).clip(0, 1)
    df = df.dropna(subset=["userId", "movieId"]).copy()
    df["userId"] = df["userId"].astype(int)
    df["movieId"] = df["movieId"].astype(int)
    for col in feature_columns:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    return df


def _sort_by_group(df: pd.DataFrame, feature_columns: list[str]) -> tuple[pd.DataFrame, np.ndarray, np.ndarray, np.ndarray]:
    ordered = df.sort_values(["userId", "label", "movieId"], ascending=[True, False, True], kind="mergesort").copy()
    group_sizes = ordered.groupby("userId", sort=False).size().to_numpy(dtype=np.uint32)
    X = ordered[feature_columns].astype(np.float32).to_numpy()
    y = ordered["label"].astype(np.float32).to_numpy()
    return ordered, X, y, group_sizes


def _ranking_metrics(df: pd.DataFrame, score_col: str, k: int = 10) -> dict:
    precision = []
    recall = []
    ndcg = []
    hit_rate = []
    for _, group in df.sort_values(["userId", score_col, "movieId"], ascending=[True, False, True]).groupby("userId"):
        relevant_count = int((group["label"] == 1).sum())
        if relevant_count <= 0:
            continue
        top = group.head(k)
        hits = top["label"].astype(int).tolist()
        hit_count = sum(hits)
        precision.append(hit_count / k)
        recall.append(hit_count / relevant_count)
        hit_rate.append(1.0 if hit_count else 0.0)
        dcg = sum(rel / math.log2(idx + 2) for idx, rel in enumerate(hits))
        idcg = sum(1 / math.log2(idx + 2) for idx in range(min(relevant_count, k)))
        ndcg.append(dcg / idcg if idcg else 0.0)
    count = len(precision)
    return {
        f"precision_at_{k}": float(sum(precision) / count) if count else 0.0,
        f"recall_at_{k}": float(sum(recall) / count) if count else 0.0,
        f"ndcg_at_{k}": float(sum(ndcg) / count) if count else 0.0,
        f"hit_rate_at_{k}": float(sum(hit_rate) / count) if count else 0.0,
        "evaluated_users": count,
    }


def _predict_scores(model, X: np.ndarray, model_type: str) -> np.ndarray:
    if model_type == "ranker":
        raw = model.predict(X)
    else:
        raw = model.predict_proba(X)[:, 1]
    raw = np.asarray(raw, dtype=float)
    if not np.isfinite(raw).all():
        raise ValueError("Model produced non-finite scores.")
    if model_type == "ranker":
        min_score = raw.min()
        max_score = raw.max()
        if max_score == min_score:
            return np.ones_like(raw)
        return (raw - min_score) / (max_score - min_score)
    return np.clip(raw, 0.0, 1.0)


def train_xgboost_ranker(
    train_path: str | Path | None = None,
    candidates_path: str | Path | None = None,
    feature_path: str | Path | None = None,
    model_output_path: str | Path | None = None,
    feature_output_path: str | Path | None = None,
    metrics_output_path: str | Path | None = None,
    importance_output_path: str | Path | None = None,
    ranked_output_path: str | Path | None = None,
    n_estimators: int = 200,
    max_depth: int = 5,
    learning_rate: float = 0.05,
    valid_user_ratio: float = 0.2,
    top_n: int = 50,
) -> dict:
    xgb, train_test_split = _require_dependencies()
    train_file = Path(train_path).resolve() if train_path else DEFAULT_TRAIN
    candidates_file = Path(candidates_path).resolve() if candidates_path else DEFAULT_CANDIDATES
    feature_file = Path(feature_path).resolve() if feature_path else DEFAULT_FEATURES
    model_file = Path(model_output_path).resolve() if model_output_path else DEFAULT_MODEL_OUTPUT
    feature_output_file = Path(feature_output_path).resolve() if feature_output_path else DEFAULT_FEATURE_OUTPUT
    metrics_file = Path(metrics_output_path).resolve() if metrics_output_path else DEFAULT_METRICS_OUTPUT
    importance_file = Path(importance_output_path).resolve() if importance_output_path else DEFAULT_IMPORTANCE_OUTPUT
    ranked_file = Path(ranked_output_path).resolve() if ranked_output_path else DEFAULT_RANKED_OUTPUT

    feature_columns = _read_features(feature_file)
    train = _load_rank_data(train_file, feature_columns)
    candidates = _load_rank_data(candidates_file, feature_columns)
    if train["label"].nunique() < 2:
        raise ValueError("Training data must contain both positive and negative labels.")

    users = np.array(sorted(train["userId"].unique()))
    train_users, valid_users = train_test_split(users, test_size=valid_user_ratio, random_state=42)
    train_df = train[train["userId"].isin(train_users)].copy()
    valid_df = train[train["userId"].isin(valid_users)].copy()
    if train_df.empty or valid_df.empty:
        raise ValueError("Train/valid user split produced empty data.")

    _, X_train, y_train, group_train = _sort_by_group(train_df, feature_columns)
    valid_ordered, X_valid, y_valid, group_valid = _sort_by_group(valid_df, feature_columns)

    fallback_reason = None
    model_type = "ranker"
    try:
        model = xgb.XGBRanker(
            objective="rank:ndcg",
            eval_metric="ndcg@10",
            n_estimators=n_estimators,
            max_depth=max_depth,
            learning_rate=learning_rate,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            n_jobs=-1,
            tree_method="hist",
        )
        model.fit(X_train, y_train, group=group_train, eval_set=[(X_valid, y_valid)], eval_group=[group_valid], verbose=False)
    except Exception as exc:
        fallback_reason = f"XGBRanker failed, fell back to XGBClassifier: {exc}"
        logger.warning("%s", fallback_reason)
        model_type = "classifier"
        model = xgb.XGBClassifier(
            objective="binary:logistic",
            eval_metric="auc",
            n_estimators=n_estimators,
            max_depth=max_depth,
            learning_rate=learning_rate,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            n_jobs=-1,
            tree_method="hist",
        )
        model.fit(X_train, y_train, eval_set=[(X_valid, y_valid)], verbose=False)

    valid_scores = _predict_scores(model, X_valid, model_type)
    valid_eval = valid_ordered[["userId", "movieId", "label"]].copy()
    valid_eval["score"] = valid_scores
    valid_metrics = _ranking_metrics(valid_eval, "score", 10)

    candidate_X = candidates[feature_columns].astype(np.float32).to_numpy()
    candidates["rank_score"] = _predict_scores(model, candidate_X, model_type)
    ranked = (
        candidates.sort_values(["userId", "rank_score", "merged_recall_score", "movieId"], ascending=[True, False, False, True])
        .groupby("userId", group_keys=False)
        .head(top_n)
        .copy()
    )
    ranked["rank_position"] = ranked.groupby("userId").cumcount() + 1
    for col in RANKED_OUTPUT_COLUMNS:
        if col not in ranked.columns:
            ranked[col] = 0.0
    ranked = ranked[RANKED_OUTPUT_COLUMNS].copy()
    ranked["rank_score"] = ranked["rank_score"].round(8)

    model_file.parent.mkdir(parents=True, exist_ok=True)
    feature_output_file.parent.mkdir(parents=True, exist_ok=True)
    metrics_file.parent.mkdir(parents=True, exist_ok=True)
    importance_file.parent.mkdir(parents=True, exist_ok=True)
    ranked_file.parent.mkdir(parents=True, exist_ok=True)
    model.save_model(str(model_file))
    feature_output_file.write_text(json.dumps(feature_columns, ensure_ascii=False, indent=2), encoding="utf-8")
    pd.DataFrame({"feature": feature_columns, "importance": model.feature_importances_.astype(float)}).sort_values(
        ["importance", "feature"], ascending=[False, True]
    ).to_csv(importance_file, index=False)
    ranked.to_csv(ranked_file, index=False)

    metrics = {
        "model_type": model_type,
        "fallback_reason": fallback_reason,
        "train_rows": int(len(train_df)),
        "valid_rows": int(len(valid_df)),
        "train_users": int(len(train_users)),
        "valid_users": int(len(valid_users)),
        "feature_count": len(feature_columns),
        "positive_samples": int((train["label"] == 1).sum()),
        "negative_samples": int((train["label"] == 0).sum()),
        "valid_precision_at_10": valid_metrics["precision_at_10"],
        "valid_recall_at_10": valid_metrics["recall_at_10"],
        "valid_ndcg_at_10": valid_metrics["ndcg_at_10"],
        "valid_hit_rate_at_10": valid_metrics["hit_rate_at_10"],
        "valid_evaluated_users": valid_metrics["evaluated_users"],
        "ranked_rows": int(len(ranked)),
        "ranked_user_count": int(ranked["userId"].nunique()),
        "model_output_path": str(model_file),
        "ranked_output_path": str(ranked_file),
    }
    metrics_file.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    for path in [model_file, feature_output_file, metrics_file, importance_file, ranked_file]:
        if not path.exists():
            raise RuntimeError(f"Expected output was not written: {path}")
    if ranked.groupby("userId").size().max() > top_n:
        raise ValueError(f"ranked output has more than top_n={top_n} rows for a user.")
    if not ranked["rank_score"].between(0, 1).all():
        raise ValueError("rank_score must be in [0, 1].")

    logger.info("model type: %s", model_type)
    logger.info("valid precision@10: %.6f", metrics["valid_precision_at_10"])
    logger.info("valid recall@10: %.6f", metrics["valid_recall_at_10"])
    logger.info("valid ndcg@10: %.6f", metrics["valid_ndcg_at_10"])
    logger.info("ranked rows: %s", metrics["ranked_rows"])
    logger.info("model output: %s", model_file)
    logger.info("ranked output: %s", ranked_file)
    logger.info("quality validation result: success")
    return metrics


def main() -> None:
    args = parse_args()
    try:
        train_xgboost_ranker(
            args.train,
            args.candidates,
            args.features,
            args.model_output,
            args.feature_output,
            args.metrics_output,
            args.importance_output,
            args.ranked_output,
            args.n_estimators,
            args.max_depth,
            args.learning_rate,
            args.valid_user_ratio,
            args.top_n,
        )
    except Exception as exc:
        logger.error("%s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
