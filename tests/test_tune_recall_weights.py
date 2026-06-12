from __future__ import annotations

import importlib
import json

import pandas as pd


def test_tune_recall_weights_importable():
    module = importlib.import_module("evaluate.tune_recall_weights")
    assert hasattr(module, "tune_recall_weights")


def test_tune_recall_weights_outputs_exist():
    paths = [
        "data/eval/recall_weight_tuning.csv",
        "data/eval/best_recall_weights.json",
        "data/recall/merged_recall_candidates_optimized.csv",
    ]
    for path in paths:
        assert pd.io.common.file_exists(path)

    tuning = pd.read_csv("data/eval/recall_weight_tuning.csv")
    required = {
        "als_weight",
        "itemcf_weight",
        "source_bonus",
        "precision_at_10",
        "recall_at_10",
        "ndcg_at_10",
        "hit_rate_at_10",
        "coverage_at_10",
        "diversity_at_10",
    }
    assert required.issubset(tuning.columns)
    for col in required - {"als_weight", "itemcf_weight", "source_bonus"}:
        assert tuning[col].between(0, 1).all()

    best = json.loads(open("data/eval/best_recall_weights.json", encoding="utf-8").read())
    assert "als_weight" in best and "itemcf_weight" in best
    assert pd.io.common.file_exists("data/recall/merged_recall_candidates.csv")
