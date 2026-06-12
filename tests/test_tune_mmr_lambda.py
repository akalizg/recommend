from __future__ import annotations

import importlib
import json

import pandas as pd


def test_tune_mmr_lambda_importable():
    module = importlib.import_module("evaluate.tune_mmr_lambda")
    assert hasattr(module, "tune_mmr_lambda")


def test_tune_mmr_lambda_outputs_exist():
    paths = [
        "data/eval/mmr_lambda_tuning.csv",
        "data/eval/best_mmr_lambda.json",
        "data/rank/ranked_top10_mmr_optimized.csv",
    ]
    for path in paths:
        assert pd.io.common.file_exists(path)

    tuning = pd.read_csv("data/eval/mmr_lambda_tuning.csv")
    required = {
        "lambda_rel",
        "precision_at_10",
        "recall_at_10",
        "ndcg_at_10",
        "hit_rate_at_10",
        "coverage_at_10",
        "diversity_at_10",
    }
    assert required.issubset(tuning.columns)
    for col in required - {"lambda_rel"}:
        assert tuning[col].between(0, 1).all()

    best = json.loads(open("data/eval/best_mmr_lambda.json", encoding="utf-8").read())
    assert 0 <= best["lambda_rel"] <= 1

    mmr = pd.read_csv("data/rank/ranked_top10_mmr_optimized.csv")
    assert mmr.groupby("userId").size().max() <= 10
