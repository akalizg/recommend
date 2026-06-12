"""
Run the Spark profile -> ALS -> FAISS vector export offline stage.

This orchestration script only produces side-path offline artifacts. It does
not modify the current FastAPI/Vue online recommendation path.
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
        raise RuntimeError(f"{name} failed after {elapsed:.1f}s with exit code {result.returncode}")
    logger.info("=== %s finished in %.1fs ===", name, elapsed)


def main() -> None:
    python = sys.executable
    steps = [
        (
            "Spark build profiles",
            [
                python,
                "spark_jobs/spark_build_profile.py",
                "--train",
                "data/processed/train_ratings.csv",
                "--movies",
                "data/processed/movies_clean.csv",
                "--tags",
                "data/processed/movie_tags.csv",
                "--output-dir",
                "data/features",
            ],
        ),
        (
            "Spark ALS train",
            [
                python,
                "spark_jobs/spark_als_train.py",
                "--train",
                "data/processed/train_ratings.csv",
                "--factors-dir",
                "data/factors",
                "--recall-dir",
                "data/recall",
                "--model-dir",
                "models/spark_als",
                "--rank",
                "32",
                "--max-iter",
                "8",
                "--reg-param",
                "0.1",
                "--top-n",
                "50",
            ],
        ),
        (
            "Export FAISS vectors",
            [
                python,
                "spark_jobs/spark_export_faiss_vectors.py",
                "--movie-factors",
                "data/factors/movie_factors.csv",
                "--output-dir",
                "data/faiss",
                "--normalize",
                "true",
            ],
        ),
    ]

    for name, command in steps:
        run_step(name, command)

    logger.info("Offline stage outputs:")
    for path in [
        "data/features/user_profile.csv",
        "data/features/movie_profile.csv",
        "data/factors/user_factors.csv",
        "data/factors/movie_factors.csv",
        "data/recall/als_recall.csv",
        "data/faiss/movie_vectors.npy",
        "data/faiss/movie_ids.npy",
        "models/spark_als",
    ]:
        logger.info(" - %s", PROJECT_ROOT / path)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        logger.error("%s", exc)
        sys.exit(1)
