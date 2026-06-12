"""
Tune MMR lambda_rel for the optimized ranking output.

The script scans lambda values, evaluates Top10 metrics, and writes the best
MMR result to ranked_top10_mmr_optimized.csv.
"""
from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
import tempfile
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evaluate.offline_metrics import evaluate_offline_metrics
from rank.mmr_rerank import DEFAULT_MOVIE_PROFILE, mmr_rerank

DEFAULT_RANKED_RANKER = PROJECT_ROOT / "data" / "rank" / "ranked_top50_ranker.csv"
DEFAULT_RANKED_FALLBACK = PROJECT_ROOT / "data" / "rank" / "ranked_top50.csv"
DEFAULT_TEST = PROJECT_ROOT / "data" / "processed" / "test_ratings.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "eval" / "mmr_lambda_tuning.csv"
DEFAULT_BEST_OUTPUT = PROJECT_ROOT / "data" / "eval" / "best_mmr_lambda.json"
DEFAULT_OPTIMIZED_OUTPUT = PROJECT_ROOT / "data" / "rank" / "ranked_top10_mmr_optimized.csv"

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tune MMR lambda_rel.")
    parser.add_argument("--ranked", default=None, help="Ranked Top50 input. Defaults to ranker output if available.")
    parser.add_argument("--movie-profile", default=str(DEFAULT_MOVIE_PROFILE), help="movie_profile.csv input.")
    parser.add_argument("--test", default=str(DEFAULT_TEST), help="test_ratings.csv input.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Lambda tuning CSV output.")
    parser.add_argument("--best-output", default=str(DEFAULT_BEST_OUTPUT), help="Best lambda JSON output.")
    parser.add_argument("--optimized-output", default=str(DEFAULT_OPTIMIZED_OUTPUT), help="Optimized MMR Top10 output.")
    parser.add_argument("--lambdas", default="0.5,0.6,0.7,0.8,0.9", help="Comma-separated lambda values.")
    return parser.parse_args()


def _parse_lambdas(value: str) -> list[float]:
    lambdas = [round(float(item.strip()), 3) for item in value.split(",") if item.strip()]
    if not lambdas or any(item < 0 or item > 1 for item in lambdas):
        raise ValueError("lambda values must be within [0, 1].")
    return sorted(set(lambdas))


def _select_ranked_input(path: str | Path | None) -> Path:
    if path:
        selected = Path(path).resolve()
        if not selected.exists():
            raise FileNotFoundError(f"Ranked input not found: {selected}")
        return selected
    if DEFAULT_RANKED_RANKER.exists():
        return DEFAULT_RANKED_RANKER
    if DEFAULT_RANKED_FALLBACK.exists():
        return DEFAULT_RANKED_FALLBACK
    raise FileNotFoundError("Neither ranked_top50_ranker.csv nor ranked_top50.csv exists.")


def tune_mmr_lambda(
    ranked_path: str | Path | None = None,
    movie_profile_path: str | Path | None = None,
    test_path: str | Path | None = None,
    output_path: str | Path | None = None,
    best_output_path: str | Path | None = None,
    optimized_output_path: str | Path | None = None,
    lambdas: str = "0.5,0.6,0.7,0.8,0.9",
) -> dict:
    ranked_file = _select_ranked_input(ranked_path)
    movie_file = Path(movie_profile_path).resolve() if movie_profile_path else DEFAULT_MOVIE_PROFILE
    test_file = Path(test_path).resolve() if test_path else DEFAULT_TEST
    output_file = Path(output_path).resolve() if output_path else DEFAULT_OUTPUT
    best_file = Path(best_output_path).resolve() if best_output_path else DEFAULT_BEST_OUTPUT
    optimized_file = Path(optimized_output_path).resolve() if optimized_output_path else DEFAULT_OPTIMIZED_OUTPUT
    lambda_values = _parse_lambdas(lambdas)

    logger.info("ranked input: %s", ranked_file)
    logger.info("movie profile input: %s", movie_file)
    logger.info("test input: %s", test_file)
    logger.info("lambda values: %s", lambda_values)

    tmp_dir = Path(tempfile.mkdtemp(prefix="mmr_lambda_", dir=str(output_file.parent if output_file.parent.exists() else PROJECT_ROOT)))
    rows = []
    best_row: dict | None = None
    best_mmr_path: Path | None = None
    try:
        for value in lambda_values:
            mmr_path = tmp_dir / f"ranked_top10_mmr_lambda_{str(value).replace('.', '_')}.csv"
            mmr_rerank(ranked_file, movie_file, mmr_path, top_n=10, lambda_rel=value)
            eval_dir = tmp_dir / f"eval_{str(value).replace('.', '_')}"
            model_files = {"MMR": mmr_path}
            evaluate_offline_metrics(test_file, movie_file, eval_dir, "10", model_files)
            metrics = pd.read_csv(eval_dir / "offline_metrics.csv").iloc[0]
            row = {
                "lambda_rel": value,
                "precision_at_10": float(metrics["precision"]),
                "recall_at_10": float(metrics["recall"]),
                "ndcg_at_10": float(metrics["ndcg"]),
                "hit_rate_at_10": float(metrics["hit_rate"]),
                "coverage_at_10": float(metrics["coverage"]),
                "diversity_at_10": float(metrics["diversity"]),
            }
            rows.append(row)
            if best_row is None:
                best_row = row
                best_mmr_path = mmr_path
                continue
            ndcg_tolerance = 0.001
            best_key = (best_row["ndcg_at_10"], best_row["diversity_at_10"], best_row["recall_at_10"])
            row_key = (row["ndcg_at_10"], row["diversity_at_10"], row["recall_at_10"])
            if row["ndcg_at_10"] >= best_row["ndcg_at_10"] - ndcg_tolerance:
                if row["diversity_at_10"] > best_row["diversity_at_10"] or row_key > best_key:
                    best_row = row
                    best_mmr_path = mmr_path

        if best_row is None or best_mmr_path is None:
            raise ValueError("No lambda candidates were evaluated.")

        output_file.parent.mkdir(parents=True, exist_ok=True)
        best_file.parent.mkdir(parents=True, exist_ok=True)
        optimized_file.parent.mkdir(parents=True, exist_ok=True)
        tuning = pd.DataFrame(rows).sort_values(["ndcg_at_10", "diversity_at_10"], ascending=[False, False])
        tuning.to_csv(output_file, index=False)
        shutil.copyfile(best_mmr_path, optimized_file)
        best_payload = {
            **best_row,
            "selection_rule": "prefer no obvious NDCG@10 drop; within tolerance choose higher Diversity@10",
            "ranked_input": str(ranked_file),
            "optimized_output": str(optimized_file),
        }
        best_file.write_text(json.dumps(best_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

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
        if not pd.read_csv(output_file)[metric].between(0, 1).all():
            raise ValueError(f"{metric} contains values outside [0, 1].")
    optimized = pd.read_csv(optimized_file)
    if optimized.groupby("userId").size().max() > 10:
        raise ValueError("Optimized MMR output has more than 10 rows for a user.")

    logger.info(
        "best lambda: %.3f ndcg@10=%.6f recall@10=%.6f diversity@10=%.6f",
        best_row["lambda_rel"],
        best_row["ndcg_at_10"],
        best_row["recall_at_10"],
        best_row["diversity_at_10"],
    )
    logger.info("lambda tuning output: %s", output_file)
    logger.info("best lambda output: %s", best_file)
    logger.info("optimized MMR output: %s", optimized_file)
    logger.info("quality validation result: success")
    return {
        "tuning_path": str(output_file),
        "best_lambda_path": str(best_file),
        "optimized_mmr_path": str(optimized_file),
        "best": best_row,
        "evaluated_lambdas": len(lambda_values),
    }


def main() -> None:
    args = parse_args()
    try:
        tune_mmr_lambda(
            args.ranked,
            args.movie_profile,
            args.test,
            args.output,
            args.best_output,
            args.optimized_output,
            args.lambdas,
        )
    except Exception as exc:
        logger.error("%s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
