from __future__ import annotations

import importlib

import pandas as pd


def test_mmr_rerank_importable():
    module = importlib.import_module("rank.mmr_rerank")
    assert hasattr(module, "mmr_rerank")


def test_mmr_rerank_outputs(tmp_path):
    from rank.mmr_rerank import DEFAULT_MOVIE_PROFILE, DEFAULT_RANKED, mmr_rerank

    output = tmp_path / "ranked_top10_mmr.csv"
    summary = mmr_rerank(DEFAULT_RANKED, DEFAULT_MOVIE_PROFILE, output, top_n=10, lambda_rel=0.7)
    assert summary["output_rows"] > 0
    assert output.exists()

    df = pd.read_csv(output)
    assert df.groupby("userId").size().max() <= 10
    assert df.groupby("userId")["rank_position"].min().eq(1).all()
    assert df["mmr_score"].notna().all()
    forbidden = [col for col in df.columns if "long_tail" in col.lower() or "novelty" in col.lower()]
    assert forbidden == []
