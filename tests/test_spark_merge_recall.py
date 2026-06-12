from __future__ import annotations

import importlib

import pandas as pd
import pytest


def test_spark_merge_recall_importable():
    module = importlib.import_module("spark_jobs.spark_merge_recall")
    assert hasattr(module, "merge_recall")


def test_spark_merge_recall_outputs(tmp_path):
    pytest.importorskip("pyspark")

    from spark_jobs.spark_itemcf_recall import DEFAULT_TRAIN, build_itemcf_recall
    from spark_jobs.spark_merge_recall import DEFAULT_ALS, merge_recall

    itemcf_output = tmp_path / "itemcf_recall.csv"
    embedding_output = tmp_path / "faiss_hnsw_recall.csv"
    merged_output = tmp_path / "merged_recall_candidates.csv"
    build_itemcf_recall(DEFAULT_TRAIN, itemcf_output, top_sim=20, top_n=20, min_rating=4.0, max_liked_per_user=50)
    als = pd.read_csv(DEFAULT_ALS).head(20)
    embedding = als[["userId", "movieId", "recall_score"]].copy()
    embedding["recall_type"] = "embedding"
    embedding.to_csv(embedding_output, index=False)
    summary = merge_recall(DEFAULT_ALS, itemcf_output, merged_output, top_n=30, embedding_path=embedding_output)
    assert summary["merged_rows_after_topn"] > 0
    assert summary["embedding_recall_rows"] > 0
    assert merged_output.exists()

    df = pd.read_csv(merged_output)
    required = {
        "userId",
        "movieId",
        "als_score",
        "itemcf_score",
        "embedding_score",
        "lightgcn_score",
        "content_score",
        "hot_score",
        "is_als_recall",
        "is_itemcf_recall",
        "is_embedding_recall",
        "is_lightgcn_recall",
        "is_content_recall",
        "is_hot_recall",
        "recall_source_count",
        "merged_recall_score",
    }
    assert required.issubset(df.columns)
    assert df.groupby("userId").size().max() <= 30
    assert (df["recall_source_count"] >= 1).all()
    assert df["merged_recall_score"].notna().all()
    assert df["is_embedding_recall"].sum() > 0
