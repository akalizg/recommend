from __future__ import annotations

import importlib
from pathlib import Path

import numpy as np


def test_spark_export_faiss_vectors_importable():
    module = importlib.import_module("spark_jobs.spark_export_faiss_vectors")
    assert hasattr(module, "export_faiss_vectors")


def test_spark_export_faiss_vectors_outputs(tmp_path):
    from spark_jobs.spark_export_faiss_vectors import DEFAULT_MOVIE_FACTORS, DEFAULT_OUTPUT_DIR, export_faiss_vectors

    output_dir = tmp_path / "faiss"
    summary = export_faiss_vectors(DEFAULT_MOVIE_FACTORS, output_dir, normalize=True)
    assert summary["movie_factors_rows"] > 0

    vectors_path = output_dir / "movie_vectors.npy"
    ids_path = output_dir / "movie_ids.npy"
    assert vectors_path.exists()
    assert ids_path.exists()

    vectors = np.load(vectors_path)
    ids = np.load(ids_path)
    assert vectors.shape[0] == ids.shape[0]
    assert vectors.dtype == np.float32
    assert np.isfinite(vectors).all()
