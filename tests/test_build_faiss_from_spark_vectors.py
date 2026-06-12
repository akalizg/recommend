from __future__ import annotations

import importlib
from pathlib import Path

import numpy as np


def test_build_faiss_from_spark_vectors_importable():
    module = importlib.import_module("scripts.build_faiss_from_spark_vectors")
    assert hasattr(module, "build_faiss_from_spark_vectors")


def test_build_faiss_from_spark_vectors_outputs(tmp_path):
    from scripts.build_faiss_from_spark_vectors import DEFAULT_IDS, DEFAULT_VECTORS, build_faiss_from_spark_vectors

    vectors = np.load(DEFAULT_VECTORS)
    ids = np.load(DEFAULT_IDS)
    assert vectors.shape[0] == ids.shape[0]

    output_index = tmp_path / "faiss_hnsw_spark.index"
    output_ids = tmp_path / "faiss_hnsw_spark_ids.npy"
    summary = build_faiss_from_spark_vectors(DEFAULT_VECTORS, DEFAULT_IDS, output_index, output_ids)

    assert summary["build_success"] is True
    assert output_index.exists()
    assert output_ids.exists()
    assert np.load(output_ids).shape[0] == vectors.shape[0]
