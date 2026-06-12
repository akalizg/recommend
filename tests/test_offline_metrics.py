from __future__ import annotations

import importlib
import json

import pandas as pd


def test_offline_metrics_importable():
    module = importlib.import_module("evaluate.offline_metrics")
    assert hasattr(module, "evaluate_offline_metrics")


def test_offline_metrics_outputs(tmp_path):
    from evaluate.offline_metrics import DEFAULT_MOVIE_PROFILE, DEFAULT_TEST, MODEL_FILES, evaluate_offline_metrics
    from rank.mmr_rerank import DEFAULT_RANKED, mmr_rerank

    mmr_output = tmp_path / "rank" / "ranked_top10_mmr.csv"
    mmr_rerank(DEFAULT_RANKED, DEFAULT_MOVIE_PROFILE, mmr_output, top_n=10, lambda_rel=0.7)

    model_files = dict(MODEL_FILES)
    model_files["XGBoost_MMR_Top10"] = mmr_output
    output_dir = tmp_path / "eval"
    summary = evaluate_offline_metrics(DEFAULT_TEST, DEFAULT_MOVIE_PROFILE, output_dir, "5,10", model_files)

    metrics_path = output_dir / "offline_metrics.csv"
    summary_path = output_dir / "eval_summary.json"
    assert summary["metrics_rows"] > 0
    assert metrics_path.exists()
    assert summary_path.exists()

    metrics = pd.read_csv(metrics_path)
    required = {
        "model_name",
        "k",
        "precision",
        "recall",
        "ndcg",
        "hit_rate",
        "coverage",
        "diversity",
        "evaluated_users",
        "recommended_items",
    }
    assert required.issubset(metrics.columns)
    for col in ["precision", "recall", "ndcg", "hit_rate", "coverage", "diversity"]:
        assert metrics[col].between(0, 1).all()
    forbidden = [col for col in metrics.columns if "longtail" in col.lower() or "long_tail" in col.lower() or "novelty" in col.lower()]
    assert forbidden == []

    loaded_summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert loaded_summary["evaluated_model_files"]
