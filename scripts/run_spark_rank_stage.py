"""
Run the offline Spark ranking stage:
1. Export Spark ranking features.
2. Train an XGBoost rank classifier.
3. Predict per-user Top50 rankings.

This script does not modify the current online recommendation chain.
"""
from __future__ import annotations

import logging
import subprocess
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def run_step(name: str, command: list[str]) -> None:
    logger.info("=== %s started ===", name)
    logger.info("Command: %s", " ".join(command))
    start = time.perf_counter()
    result = subprocess.run(command, cwd=PROJECT_ROOT)
    elapsed = time.perf_counter() - start
    if result.returncode != 0:
        logger.error("%s failed after %.1fs with exit code %s", name, elapsed, result.returncode)
        raise RuntimeError(f"{name} failed")
    logger.info("=== %s finished in %.1fs ===", name, elapsed)


def main() -> None:
    python = sys.executable

    run_step(
        "Export Spark rank features",
        [
            python,
            "spark_jobs/spark_feature_export.py",
            "--user-profile",
            "data/features/user_profile.csv",
            "--movie-profile",
            "data/features/movie_profile.csv",
            "--merged-recall",
            "data/recall/merged_recall_candidates.csv",
            "--train-ratings",
            "data/processed/train_ratings.csv",
            "--test-ratings",
            "data/processed/test_ratings.csv",
            "--output-dir",
            "data/rank",
        ],
    )

    run_step(
        "Train XGBoost rank model",
        [
            python,
            "rank/train_from_spark_features.py",
            "--train",
            "data/rank/rank_train.csv",
            "--features",
            "data/rank/rank_feature_columns.json",
            "--model-output",
            "models/xgb_rank_model_spark.json",
            "--model-features-output",
            "models/xgb_rank_feature_columns.json",
            "--metrics-output",
            "data/rank/xgb_train_metrics.json",
            "--importance-output",
            "data/rank/xgb_feature_importance.csv",
        ],
    )

    run_step(
        "Predict XGBoost Top50 rankings",
        [
            python,
            "rank/predict_from_spark_features.py",
            "--candidates",
            "data/rank/rank_candidates.csv",
            "--model",
            "models/xgb_rank_model_spark.json",
            "--features",
            "models/xgb_rank_feature_columns.json",
            "--output",
            "data/rank/ranked_top50.csv",
            "--top-n",
            "50",
        ],
    )

    logger.info("Rank stage outputs:")
    for path in [
        "data/rank/rank_train.csv",
        "data/rank/rank_candidates.csv",
        "data/rank/rank_feature_columns.json",
        "models/xgb_rank_model_spark.json",
        "models/xgb_rank_feature_columns.json",
        "data/rank/xgb_train_metrics.json",
        "data/rank/xgb_feature_importance.csv",
        "data/rank/ranked_top50.csv",
    ]:
        logger.info(" - %s", PROJECT_ROOT / path)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        logger.error("%s", exc)
        sys.exit(1)
