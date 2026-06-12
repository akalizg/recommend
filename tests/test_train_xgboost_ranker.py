from __future__ import annotations

import importlib
import json

import pandas as pd


def test_train_xgboost_ranker_importable():
    module = importlib.import_module("rank.train_xgboost_ranker")
    assert hasattr(module, "train_xgboost_ranker")


def test_train_xgboost_ranker_outputs_exist():
    paths = [
        "models/xgb_ranker_model_spark.json",
        "models/xgb_ranker_feature_columns.json",
        "data/rank/xgb_ranker_train_metrics.json",
        "data/rank/xgb_ranker_feature_importance.csv",
        "data/rank/ranked_top50_ranker.csv",
    ]
    for path in paths:
        assert pd.io.common.file_exists(path)

    metrics = json.loads(open("data/rank/xgb_ranker_train_metrics.json", encoding="utf-8").read())
    assert metrics["model_type"] in {"ranker", "classifier"}
    assert 0 <= metrics["valid_ndcg_at_10"] <= 1

    ranked = pd.read_csv("data/rank/ranked_top50_ranker.csv")
    assert ranked.groupby("userId").size().max() <= 50
    assert ranked["rank_score"].between(0, 1).all()
