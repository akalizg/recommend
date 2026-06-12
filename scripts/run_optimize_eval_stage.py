"""
Run the offline recommendation-effect optimization stage.

Steps:
1. Tune ALS/ItemCF recall weights and write optimized merged recall.
2. Export optimized rank candidates from optimized recall.
3. Train XGBoost Ranker and predict Top50.
4. Tune MMR lambda and write optimized Top10.
5. Rebuild optimized offline metrics and ablation table.

This script does not modify FastAPI, Vue, old models, or old result files.
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
        "Tune recall weights",
        [
            python,
            "evaluate/tune_recall_weights.py",
            "--als",
            "data/recall/als_recall.csv",
            "--itemcf",
            "data/recall/itemcf_recall.csv",
            "--test",
            "data/processed/test_ratings.csv",
            "--movie-profile",
            "data/features/movie_profile.csv",
            "--output",
            "data/eval/recall_weight_tuning.csv",
            "--best-output",
            "data/eval/best_recall_weights.json",
            "--optimized-recall",
            "data/recall/merged_recall_candidates_optimized.csv",
            "--top-n",
            "100",
        ],
    )

    run_step(
        "Export optimized rank candidates",
        [
            python,
            "spark_jobs/spark_feature_export.py",
            "--user-profile",
            "data/features/user_profile.csv",
            "--movie-profile",
            "data/features/movie_profile.csv",
            "--merged-recall",
            "data/recall/merged_recall_candidates_optimized.csv",
            "--train-ratings",
            "data/processed/train_ratings.csv",
            "--test-ratings",
            "data/processed/test_ratings.csv",
            "--output-dir",
            "data/rank_optimized_tmp",
        ],
    )

    run_step(
        "Copy optimized rank candidate features",
        [
            python,
            "-c",
            (
                "import shutil, pathlib; "
                "pathlib.Path('data/rank').mkdir(parents=True, exist_ok=True); "
                "shutil.copyfile('data/rank_optimized_tmp/rank_candidates.csv','data/rank/rank_candidates_optimized.csv')"
            ),
        ],
    )

    run_step(
        "Train XGBoost Ranker and predict optimized Top50",
        [
            python,
            "rank/train_xgboost_ranker.py",
            "--train",
            "data/rank/rank_train.csv",
            "--candidates",
            "data/rank/rank_candidates_optimized.csv",
            "--features",
            "data/rank/rank_feature_columns.json",
            "--model-output",
            "models/xgb_ranker_model_spark.json",
            "--feature-output",
            "models/xgb_ranker_feature_columns.json",
            "--metrics-output",
            "data/rank/xgb_ranker_train_metrics.json",
            "--importance-output",
            "data/rank/xgb_ranker_feature_importance.csv",
            "--ranked-output",
            "data/rank/ranked_top50_ranker.csv",
            "--n-estimators",
            "200",
            "--max-depth",
            "5",
            "--learning-rate",
            "0.05",
        ],
    )

    run_step(
        "Tune MMR lambda",
        [
            python,
            "evaluate/tune_mmr_lambda.py",
            "--ranked",
            "data/rank/ranked_top50_ranker.csv",
            "--movie-profile",
            "data/features/movie_profile.csv",
            "--test",
            "data/processed/test_ratings.csv",
            "--output",
            "data/eval/mmr_lambda_tuning.csv",
            "--best-output",
            "data/eval/best_mmr_lambda.json",
            "--optimized-output",
            "data/rank/ranked_top10_mmr_optimized.csv",
            "--lambdas",
            "0.5,0.6,0.7,0.8,0.9",
        ],
    )

    run_step(
        "Build optimized offline metrics",
        [
            python,
            "-c",
            (
                "from evaluate.offline_metrics import evaluate_offline_metrics; "
                "evaluate_offline_metrics('data/processed/test_ratings.csv','data/features/movie_profile.csv','data/eval/optimized_tmp','5,10,20,50',{"
                "'ALS':'data/recall/als_recall.csv',"
                "'ItemCF':'data/recall/itemcf_recall.csv',"
                "'ALS+ItemCF_Merged_Original':'data/recall/merged_recall_candidates.csv',"
                "'ALS+ItemCF_Merged_Optimized':'data/recall/merged_recall_candidates_optimized.csv',"
                "'XGBoost_Classifier_Top50':'data/rank/ranked_top50.csv',"
                "'XGBoost_Ranker_Top50':'data/rank/ranked_top50_ranker.csv',"
                "'XGBoost_Ranker_MMR_Top10':'data/rank/ranked_top10_mmr_optimized.csv'"
                "}); "
                "import shutil; "
                "shutil.copyfile('data/eval/optimized_tmp/offline_metrics.csv','data/eval/optimized_offline_metrics.csv'); "
                "shutil.copyfile('data/eval/optimized_tmp/eval_summary.json','data/eval/optimized_eval_summary.json')"
            ),
        ],
    )

    run_step(
        "Build optimized ablation metrics",
        [
            python,
            "-c",
            (
                "import pandas as pd; "
                "src='data/eval/optimized_offline_metrics.csv'; dst='data/eval/optimized_ablation_metrics.csv'; "
                "df=pd.read_csv(src); k=10; keep=df[df['k']==k].copy(); "
                "order=['ALS','ItemCF','ALS+ItemCF_Merged_Original','ALS+ItemCF_Merged_Optimized','XGBoost_Classifier_Top50','XGBoost_Ranker_Top50','XGBoost_Ranker_MMR_Top10']; "
                "obs=[]; "
                "[obs.append({"
                "'variant':v,'k':k,"
                "'precision':float(keep[keep.model_name==v].precision.iloc[0]),"
                "'recall':float(keep[keep.model_name==v].recall.iloc[0]),"
                "'ndcg':float(keep[keep.model_name==v].ndcg.iloc[0]),"
                "'hit_rate':float(keep[keep.model_name==v].hit_rate.iloc[0]),"
                "'coverage':float(keep[keep.model_name==v].coverage.iloc[0]),"
                "'diversity':float(keep[keep.model_name==v].diversity.iloc[0])"
                "}) for v in order if not keep[keep.model_name==v].empty]; "
                "out=pd.DataFrame(obs); "
                "out['main_observation']=out['variant'].map(lambda v: 'Optimized stage metric row for '+v); "
                "out.to_csv(dst,index=False)"
            ),
        ],
    )

    logger.info("Optimization stage outputs:")
    for path in [
        "data/eval/recall_weight_tuning.csv",
        "data/eval/best_recall_weights.json",
        "data/recall/merged_recall_candidates_optimized.csv",
        "data/rank/rank_candidates_optimized.csv",
        "models/xgb_ranker_model_spark.json",
        "models/xgb_ranker_feature_columns.json",
        "data/rank/xgb_ranker_train_metrics.json",
        "data/rank/xgb_ranker_feature_importance.csv",
        "data/rank/ranked_top50_ranker.csv",
        "data/eval/mmr_lambda_tuning.csv",
        "data/eval/best_mmr_lambda.json",
        "data/rank/ranked_top10_mmr_optimized.csv",
        "data/eval/optimized_offline_metrics.csv",
        "data/eval/optimized_ablation_metrics.csv",
        "data/eval/optimized_eval_summary.json",
    ]:
        logger.info(" - %s", PROJECT_ROOT / path)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        logger.error("%s", exc)
        sys.exit(1)
