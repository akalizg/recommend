"""
Train an offline XGBoost rank classifier from Spark-exported features.

This script reads data/rank/rank_train.csv and does not touch the online
FastAPI/Vue recommendation path.
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
DEFAULT_FEATURES = PROJECT_ROOT / "data" / "rank" / "rank_feature_columns.json"
DEFAULT_MODEL_OUTPUT = PROJECT_ROOT / "models" / "xgb_rank_model_spark.json"
DEFAULT_MODEL_FEATURES_OUTPUT = PROJECT_ROOT / "models" / "xgb_rank_feature_columns.json"
DEFAULT_METRICS_OUTPUT = PROJECT_ROOT / "data" / "rank" / "xgb_train_metrics.json"
DEFAULT_IMPORTANCE_OUTPUT = PROJECT_ROOT / "data" / "rank" / "xgb_feature_importance.csv"

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train XGBoost rank model from Spark-exported features.")
    parser.add_argument("--train", default=str(DEFAULT_TRAIN), help="rank_train.csv input.")
    parser.add_argument("--features", default=str(DEFAULT_FEATURES), help="Feature column JSON input.")
    parser.add_argument("--model-output", default=str(DEFAULT_MODEL_OUTPUT), help="XGBoost model output path.")
    parser.add_argument(
        "--model-features-output",
        default=str(DEFAULT_MODEL_FEATURES_OUTPUT),
        help="Feature columns copied next to the model.",
    )
    parser.add_argument("--metrics-output", default=str(DEFAULT_METRICS_OUTPUT), help="Training metrics JSON output.")
    parser.add_argument(
        "--importance-output",
        default=str(DEFAULT_IMPORTANCE_OUTPUT),
        help="Feature importance CSV output.",
    )
    parser.add_argument("--n-estimators", type=int, default=200, help="XGBoost n_estimators.")
    parser.add_argument("--max-depth", type=int, default=5, help="XGBoost max_depth.")
    parser.add_argument("--learning-rate", type=float, default=0.05, help="XGBoost learning_rate.")
    parser.add_argument("--test-size", type=float, default=0.2, help="Validation split ratio.")
    return parser.parse_args()


def _require_ml_dependencies():
    try:
        import xgboost as xgb
        from sklearn.metrics import accuracy_score, log_loss, roc_auc_score
        from sklearn.model_selection import train_test_split
    except ImportError as exc:
        raise RuntimeError(
            "xgboost and scikit-learn are required. Install dependencies with `pip install -r requirements.txt`."
        ) from exc
    return xgb, train_test_split, roc_auc_score, accuracy_score, log_loss


def _read_feature_columns(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(f"Feature column file not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not all(isinstance(item, str) for item in data):
        raise ValueError(f"Feature column file must contain a JSON string list: {path}")
    return data


def _safe_auc(metric_fn, y_true, y_score) -> float | None:
    if len(set(y_true.tolist())) < 2:
        return None
    return float(metric_fn(y_true, y_score))


def train_from_spark_features(
    train_path: str | Path | None = None,
    feature_path: str | Path | None = None,
    model_output_path: str | Path | None = None,
    model_features_output_path: str | Path | None = None,
    metrics_output_path: str | Path | None = None,
    importance_output_path: str | Path | None = None,
    n_estimators: int = 200,
    max_depth: int = 5,
    learning_rate: float = 0.05,
    test_size: float = 0.2,
) -> dict:
    xgb, train_test_split, roc_auc_score, accuracy_score, log_loss = _require_ml_dependencies()

    train_file = Path(train_path).resolve() if train_path else DEFAULT_TRAIN
    feature_file = Path(feature_path).resolve() if feature_path else DEFAULT_FEATURES
    model_file = Path(model_output_path).resolve() if model_output_path else DEFAULT_MODEL_OUTPUT
    model_feature_file = (
        Path(model_features_output_path).resolve() if model_features_output_path else DEFAULT_MODEL_FEATURES_OUTPUT
    )
    metrics_file = Path(metrics_output_path).resolve() if metrics_output_path else DEFAULT_METRICS_OUTPUT
    importance_file = Path(importance_output_path).resolve() if importance_output_path else DEFAULT_IMPORTANCE_OUTPUT

    if not train_file.exists():
        raise FileNotFoundError(f"Rank train input not found: {train_file}")
    feature_columns = _read_feature_columns(feature_file)

    logger.info("rank_train input: %s", train_file)
    logger.info("feature columns input: %s", feature_file)
    logger.info("model output: %s", model_file)
    logger.info("metrics output: %s", metrics_file)
    logger.info("feature importance output: %s", importance_file)

    df = pd.read_csv(train_file)
    required = {"userId", "movieId", "label", *feature_columns}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"rank_train.csv is missing required columns: {missing}")

    df = df.dropna(subset=["label"]).copy()
    df["label"] = df["label"].astype(int)
    if not set(df["label"].unique()).issubset({0, 1}):
        raise ValueError("label must contain only 0 and 1.")

    for col in feature_columns:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    rank_train_rows = int(len(df))
    positive_samples = int((df["label"] == 1).sum())
    negative_samples = int((df["label"] == 0).sum())
    if rank_train_rows <= 0:
        raise ValueError("rank_train.csv has no rows.")
    if positive_samples <= 0 or negative_samples <= 0:
        raise ValueError("Both positive and negative samples are required for XGBoost training.")

    X = df[feature_columns].astype(np.float32)
    y = df["label"].astype(np.int32)
    stratify = y if y.nunique() == 2 and y.value_counts().min() >= 2 else None
    X_train, X_valid, y_train, y_valid = train_test_split(
        X,
        y,
        test_size=test_size,
        random_state=42,
        stratify=stratify,
    )

    model = xgb.XGBClassifier(
        objective="binary:logistic",
        eval_metric="auc",
        max_depth=max_depth,
        learning_rate=learning_rate,
        n_estimators=n_estimators,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        n_jobs=-1,
        tree_method="hist",
    )
    model.fit(X_train, y_train, eval_set=[(X_valid, y_valid)], verbose=False)

    train_prob = model.predict_proba(X_train)[:, 1]
    valid_prob = model.predict_proba(X_valid)[:, 1]
    if not (np.isfinite(train_prob).all() and np.isfinite(valid_prob).all()):
        raise ValueError("Model produced non-finite probabilities.")
    if train_prob.min() < 0 or train_prob.max() > 1 or valid_prob.min() < 0 or valid_prob.max() > 1:
        raise ValueError("Model probabilities are outside [0, 1].")

    train_auc = _safe_auc(roc_auc_score, y_train, train_prob)
    valid_auc = _safe_auc(roc_auc_score, y_valid, valid_prob)
    train_accuracy = float(accuracy_score(y_train, train_prob >= 0.5))
    valid_accuracy = float(accuracy_score(y_valid, valid_prob >= 0.5))
    train_logloss = float(log_loss(y_train, train_prob, labels=[0, 1]))
    valid_logloss = float(log_loss(y_valid, valid_prob, labels=[0, 1]))

    model_file.parent.mkdir(parents=True, exist_ok=True)
    model_feature_file.parent.mkdir(parents=True, exist_ok=True)
    metrics_file.parent.mkdir(parents=True, exist_ok=True)
    importance_file.parent.mkdir(parents=True, exist_ok=True)

    model.save_model(str(model_file))
    model_feature_file.write_text(json.dumps(feature_columns, ensure_ascii=False, indent=2), encoding="utf-8")

    importance = pd.DataFrame(
        {
            "feature": feature_columns,
            "importance": model.feature_importances_.astype(float),
        }
    ).sort_values(["importance", "feature"], ascending=[False, True])
    importance.to_csv(importance_file, index=False)

    metrics = {
        "rank_train_rows": rank_train_rows,
        "feature_count": len(feature_columns),
        "positive_samples": positive_samples,
        "negative_samples": negative_samples,
        "train_rows": int(len(X_train)),
        "valid_rows": int(len(X_valid)),
        "train_auc": train_auc,
        "valid_auc": valid_auc,
        "train_accuracy": train_accuracy,
        "valid_accuracy": valid_accuracy,
        "train_logloss": train_logloss,
        "valid_logloss": valid_logloss,
        "n_estimators": n_estimators,
        "max_depth": max_depth,
        "learning_rate": learning_rate,
        "model_output_path": str(model_file),
        "feature_columns_path": str(model_feature_file),
        "metrics_output_path": str(metrics_file),
        "feature_importance_path": str(importance_file),
    }
    metrics_file.write_text(json.dumps(metrics, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")

    for path in (model_file, model_feature_file, metrics_file, importance_file):
        if not path.exists():
            raise RuntimeError(f"Expected output was not written: {path}")
    if importance.empty:
        raise ValueError("Feature importance output is empty.")
    if not all(math.isfinite(v) for v in valid_prob[: min(100, len(valid_prob))]):
        raise ValueError("Quality check failed: prediction probabilities contain invalid values.")

    logger.info("rank_train rows: %s", rank_train_rows)
    logger.info("feature count: %s", len(feature_columns))
    logger.info("positive samples: %s", positive_samples)
    logger.info("negative samples: %s", negative_samples)
    logger.info("train AUC: %s", f"{train_auc:.6f}" if train_auc is not None else "n/a")
    logger.info("valid AUC: %s", f"{valid_auc:.6f}" if valid_auc is not None else "n/a")
    logger.info("train accuracy: %.6f", train_accuracy)
    logger.info("valid accuracy: %.6f", valid_accuracy)
    logger.info("model output path: %s", model_file)
    logger.info("feature importance output path: %s", importance_file)
    logger.info("quality validation result: success")
    return metrics


def main() -> None:
    args = parse_args()
    try:
        train_from_spark_features(
            args.train,
            args.features,
            args.model_output,
            args.model_features_output,
            args.metrics_output,
            args.importance_output,
            args.n_estimators,
            args.max_depth,
            args.learning_rate,
            args.test_size,
        )
    except Exception as exc:
        logger.error("%s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
