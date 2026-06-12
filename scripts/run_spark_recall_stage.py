"""
Run the Spark recall stage:
1. Build standalone FAISS index from Spark ALS vectors.
2. Build ItemCF recall candidates.
3. Build lightweight LightGCN, content, and hot recall candidates.
4. Merge ALS, ItemCF, LightGCN, content, and hot recall candidates.

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


def run_step(name: str, command: list[str], required: bool = True) -> bool:
    logger.info("=== %s started ===", name)
    logger.info("Command: %s", " ".join(command))
    start = time.perf_counter()
    result = subprocess.run(command, cwd=PROJECT_ROOT)
    elapsed = time.perf_counter() - start
    if result.returncode != 0:
        logger.error("%s failed after %.1fs with exit code %s", name, elapsed, result.returncode)
        if required:
            raise RuntimeError(f"{name} failed")
        return False
    logger.info("=== %s finished in %.1fs ===", name, elapsed)
    return True


def main() -> None:
    python = sys.executable

    faiss_ok = run_step(
        "Build standalone Spark FAISS index",
        [
            python,
            "scripts/build_faiss_from_spark_vectors.py",
            "--vectors",
            "data/faiss/movie_vectors.npy",
            "--ids",
            "data/faiss/movie_ids.npy",
            "--output-index",
            "models/faiss_hnsw_spark.index",
            "--output-ids",
            "models/faiss_hnsw_spark_ids.npy",
        ],
        required=False,
    )
    if not faiss_ok:
        logger.warning("FAISS build failed; continuing with ItemCF and merge because they do not depend on the index.")

    run_step(
        "Build Spark ItemCF recall",
        [
            python,
            "spark_jobs/spark_itemcf_recall.py",
            "--train",
            "data/processed/train_ratings.csv",
            "--output",
            "data/recall/itemcf_recall.csv",
            "--top-sim",
            "50",
            "--top-n",
            "50",
            "--min-rating",
            "4.0",
            "--max-liked-per-user",
            "100",
        ],
        required=True,
    )

    run_step(
        "Export LightGCN graph",
        [
            python,
            "spark_jobs/spark_lightgcn_graph_export.py",
            "--train",
            "data/processed/train_ratings.csv",
            "--movie-profile",
            "data/features/movie_profile.csv",
            "--output",
            "data/lightgcn/graph_edges.csv",
        ],
        required=True,
    )

    run_step(
        "Build lightweight LightGCN recall",
        [
            python,
            "spark_jobs/spark_lightgcn_recall.py",
            "--user-profile",
            "data/features/user_profile.csv",
            "--movie-profile",
            "data/features/movie_profile.csv",
            "--train",
            "data/processed/train_ratings.csv",
            "--output",
            "data/recall/lightgcn_recall.csv",
            "--top-n",
            "50",
        ],
        required=True,
    )

    run_step(
        "Build content-based recall",
        [
            python,
            "spark_jobs/spark_content_recall.py",
            "--user-profile",
            "data/features/user_profile.csv",
            "--movie-profile",
            "data/features/movie_profile.csv",
            "--train-ratings",
            "data/processed/train_ratings.csv",
            "--output",
            "data/recall/content_recall.csv",
            "--top-n",
            "50",
        ],
        required=True,
    )

    run_step(
        "Build hot recall",
        [
            python,
            "spark_jobs/spark_hot_recall.py",
            "--user-profile",
            "data/features/user_profile.csv",
            "--movie-profile",
            "data/features/movie_profile.csv",
            "--train-ratings",
            "data/processed/train_ratings.csv",
            "--output",
            "data/recall/hot_recall.csv",
            "--top-n",
            "50",
        ],
        required=True,
    )

    run_step(
        "Merge Spark recall channels",
        [
            python,
            "spark_jobs/spark_merge_recall.py",
            "--als",
            "data/recall/als_recall.csv",
            "--itemcf",
            "data/recall/itemcf_recall.csv",
            "--lightgcn",
            "data/recall/lightgcn_recall.csv",
            "--content",
            "data/recall/content_recall.csv",
            "--hot",
            "data/recall/hot_recall.csv",
            "--output",
            "data/recall/merged_recall_candidates.csv",
            "--top-n",
            "100",
        ],
        required=True,
    )

    logger.info("Recall stage outputs:")
    for path in [
        "models/faiss_hnsw_spark.index",
        "models/faiss_hnsw_spark_ids.npy",
        "data/recall/itemcf_recall.csv",
        "data/lightgcn/graph_edges.csv",
        "data/recall/lightgcn_recall.csv",
        "data/recall/content_recall.csv",
        "data/recall/hot_recall.csv",
        "data/recall/merged_recall_candidates.csv",
    ]:
        logger.info(" - %s", PROJECT_ROOT / path)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        logger.error("%s", exc)
        sys.exit(1)
