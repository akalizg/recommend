from __future__ import annotations

import importlib

import pandas as pd


def test_ablation_eval_importable():
    module = importlib.import_module("evaluate.ablation_eval")
    assert hasattr(module, "build_ablation_eval")


def test_ablation_eval_outputs(tmp_path):
    from evaluate.ablation_eval import VARIANT_ORDER, build_ablation_eval
    from evaluate.offline_metrics import DEFAULT_MOVIE_PROFILE, DEFAULT_TEST, MODEL_FILES, evaluate_offline_metrics
    from rank.mmr_rerank import DEFAULT_RANKED, mmr_rerank

    mmr_output = tmp_path / "rank" / "ranked_top10_mmr.csv"
    mmr_rerank(DEFAULT_RANKED, DEFAULT_MOVIE_PROFILE, mmr_output, top_n=10, lambda_rel=0.7)

    model_files = dict(MODEL_FILES)
    model_files["XGBoost_MMR_Top10"] = mmr_output
    eval_dir = tmp_path / "eval"
    evaluate_offline_metrics(DEFAULT_TEST, DEFAULT_MOVIE_PROFILE, eval_dir, "10", model_files)

    result = build_ablation_eval(eval_dir / "offline_metrics.csv", eval_dir, k=10)
    metrics_path = eval_dir / "ablation_metrics.csv"
    summary_path = eval_dir / "ablation_summary.md"
    assert result["rows"] >= 5
    assert metrics_path.exists()
    assert summary_path.exists()

    df = pd.read_csv(metrics_path)
    assert set(VARIANT_ORDER).issubset(set(df["variant"]))
    assert df["main_observation"].notna().all()
    assert (df["main_observation"].astype(str).str.len() > 0).all()
