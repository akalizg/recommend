"""
Run the migrated Food.com recipe recommendation offline pipeline.

This keeps the old canonical column names internally so the existing Spark,
ranking, MMR, and reason-generation stages can be reused.
"""
from __future__ import annotations

import argparse
import logging
import subprocess
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Food.com recipe recommendation pipeline.")
    parser.add_argument("--input-dir", default="data/food-com")
    parser.add_argument("--canonical-dir", default="data/recipe-canonical")
    parser.add_argument("--max-recipes", type=int, default=12_000)
    parser.add_argument("--max-users", type=int, default=1_500)
    parser.add_argument("--max-interactions", type=int, default=120_000)
    parser.add_argument("--use-official-splits", action="store_true", help="Use Food.com interactions_train/validation/test.csv.")
    parser.add_argument("--official-split-dir", default="data", help="Directory containing official interactions_*.csv files.")
    parser.add_argument("--official-recipe-file", default="data/food-com/RAW_recipes.csv", help="RAW_recipes.csv used with official splits.")
    parser.add_argument("--max-train-interactions", type=int, default=0, help="Optional cap for official train split; 0 means full train.")
    parser.add_argument("--skip-convert", action="store_true")
    parser.add_argument("--skip-profile-als", action="store_true")
    parser.add_argument("--skip-recall", action="store_true")
    parser.add_argument("--skip-rank", action="store_true")
    parser.add_argument("--skip-mmr-eval", action="store_true")
    parser.add_argument("--skip-reasons", action="store_true")
    return parser.parse_args()


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
    args = parse_args()
    python = sys.executable

    if args.use_official_splits and not args.skip_convert:
        run_step(
            "Import official Food.com train/validation/test splits",
            [
                python,
                "scripts/import_foodcom_official_splits.py",
                "--split-dir",
                args.official_split_dir,
                "--recipe-file",
                args.official_recipe_file,
                "--canonical-dir",
                args.canonical_dir,
                "--processed-dir",
                "data/processed",
                "--max-train-interactions",
                str(args.max_train_interactions),
                "--max-users",
                str(args.max_users),
                "--max-recipes",
                str(args.max_recipes),
            ],
        )
    elif not args.skip_convert:
        run_step(
            "Convert Food.com to canonical schema",
            [
                python,
                "scripts/convert_foodcom_to_movielens_schema.py",
                "--input-dir",
                args.input_dir,
                "--output-dir",
                args.canonical_dir,
                "--max-recipes",
                str(args.max_recipes),
                "--max-users",
                str(args.max_users),
                "--max-interactions",
                str(args.max_interactions),
            ],
        )

    if not args.use_official_splits:
        run_step(
            "Spark preprocess recipe canonical data",
            [
                python,
                "spark_jobs/spark_preprocess.py",
                "--input-dir",
                args.canonical_dir,
                "--output-dir",
                "data/processed",
            ],
        )
        run_step(
            "Spark recipe train/test split",
            [
                python,
                "spark_jobs/spark_train_test_split.py",
                "--input",
                "data/processed/ratings_clean.csv",
                "--output-dir",
                "data/processed",
            ],
        )

    if not args.skip_profile_als:
        run_step("Recipe profile/ALS/FAISS stage", [python, "scripts/run_spark_profile_als.py"])
    if not args.skip_recall:
        run_step("Recipe multi-channel recall stage", [python, "scripts/run_spark_recall_stage.py"])
    if not args.skip_rank:
        run_step("Recipe rank stage", [python, "scripts/run_spark_rank_stage.py"])
    if not args.skip_mmr_eval:
        run_step("Recipe MMR/evaluation stage", [python, "scripts/run_mmr_eval_stage.py"])
    if not args.skip_reasons:
        run_step("Recipe reason generation", [python, "scripts/run_reason_generation.py", "--use-llm", "false"])

    logger.info("Recipe migration pipeline finished.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        logger.error("%s", exc)
        sys.exit(1)
