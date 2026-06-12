from __future__ import annotations

import pandas as pd


def test_optimize_eval_stage_outputs_exist_and_valid():
    paths = [
        "data/eval/optimized_offline_metrics.csv",
        "data/eval/optimized_ablation_metrics.csv",
        "data/eval/optimized_eval_summary.json",
        "data/rank/ranked_top50_ranker.csv",
        "data/rank/ranked_top10_mmr_optimized.csv",
    ]
    for path in paths:
        assert pd.io.common.file_exists(path)

    metrics = pd.read_csv("data/eval/optimized_offline_metrics.csv")
    required_models = {
        "ALS",
        "ItemCF",
        "ALS+ItemCF_Merged_Original",
        "ALS+ItemCF_Merged_Optimized",
        "XGBoost_Classifier_Top50",
        "XGBoost_Ranker_Top50",
        "XGBoost_Ranker_MMR_Top10",
    }
    assert required_models.issubset(set(metrics["model_name"]))
    for col in ["precision", "recall", "ndcg", "hit_rate", "coverage", "diversity"]:
        assert metrics[col].between(0, 1).all()

    ablation = pd.read_csv("data/eval/optimized_ablation_metrics.csv")
    assert required_models.issubset(set(ablation["variant"]))
    assert ablation["main_observation"].notna().all()

    assert pd.io.common.file_exists("data/rank/ranked_top50.csv")
    assert pd.io.common.file_exists("models/xgb_rank_model_spark.json")
