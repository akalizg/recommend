from __future__ import annotations

import importlib

import pandas as pd


def test_ablation_eval_importable():
    module = importlib.import_module("evaluate.ablation_eval")
    assert hasattr(module, "build_ablation_eval")


def test_ablation_eval_outputs(tmp_path):
    from evaluate.ablation_eval import VARIANT_ORDER, build_ablation_eval

    eval_dir = tmp_path / "eval"
    eval_dir.mkdir(parents=True)
    rows = []
    for idx, variant in enumerate(VARIANT_ORDER):
        rows.append(
            {
                "model_name": variant,
                "k": 10,
                "precision": 0.0,
                "recall": 0.0,
                "ndcg": 0.0,
                "hit_rate": 0.0,
                "coverage": 0.1 + idx * 0.01,
                "diversity": 0.7 + idx * 0.01,
                "evaluated_users": 3,
                "recommended_items": 10 + idx,
            }
        )
    pd.DataFrame(rows).to_csv(eval_dir / "offline_metrics.csv", index=False)

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
