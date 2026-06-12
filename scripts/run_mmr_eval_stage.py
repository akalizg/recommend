"""
Run the offline MMR + evaluation + ablation stage.

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
        "MMR rerank XGBoost Top50",
        [
            python,
            "rank/mmr_rerank.py",
            "--ranked",
            "data/rank/ranked_top50.csv",
            "--movie-profile",
            "data/features/movie_profile.csv",
            "--output",
            "data/rank/ranked_top10_mmr.csv",
            "--top-n",
            "10",
            "--lambda-rel",
            "0.7",
        ],
    )

    run_step(
        "Evaluate offline metrics",
        [
            python,
            "evaluate/offline_metrics.py",
            "--test",
            "data/processed/test_ratings.csv",
            "--movie-profile",
            "data/features/movie_profile.csv",
            "--output-dir",
            "data/eval",
            "--ks",
            "5,10,20,50",
        ],
    )

    run_step(
        "Build ablation evaluation",
        [
            python,
            "evaluate/ablation_eval.py",
            "--metrics",
            "data/eval/offline_metrics.csv",
            "--output-dir",
            "data/eval",
            "--k",
            "10",
        ],
    )

    logger.info("MMR/evaluation stage outputs:")
    for path in [
        "data/rank/ranked_top10_mmr.csv",
        "data/eval/offline_metrics.csv",
        "data/eval/eval_summary.json",
        "data/eval/ablation_metrics.csv",
        "data/eval/ablation_summary.md",
    ]:
        logger.info(" - %s", PROJECT_ROOT / path)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        logger.error("%s", exc)
        sys.exit(1)
