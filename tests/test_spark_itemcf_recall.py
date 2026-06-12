from __future__ import annotations

import importlib

import pandas as pd
import pytest


def test_spark_itemcf_recall_importable():
    module = importlib.import_module("spark_jobs.spark_itemcf_recall")
    assert hasattr(module, "build_itemcf_recall")


def test_spark_itemcf_recall_outputs(tmp_path):
    pytest.importorskip("pyspark")

    from spark_jobs.spark_itemcf_recall import DEFAULT_TRAIN, build_itemcf_recall

    output = tmp_path / "itemcf_recall.csv"
    summary = build_itemcf_recall(DEFAULT_TRAIN, output, top_sim=20, top_n=20, min_rating=4.0, max_liked_per_user=50)
    assert summary["itemcf_recall_rows"] > 0
    assert output.exists()

    df = pd.read_csv(output)
    assert {"userId", "movieId", "recall_type", "recall_score"}.issubset(df.columns)
    assert set(df["recall_type"].unique()) == {"itemcf"}
    assert df.groupby("userId").size().max() <= 20
    assert df["recall_score"].notna().all()
