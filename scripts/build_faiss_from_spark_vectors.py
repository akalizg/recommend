"""
Build a standalone FAISS HNSW index from Spark ALS movie vectors.

This script intentionally writes to models/faiss_hnsw_spark.index and does not
overwrite the existing online index models/faiss_hnsw.index.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import faiss
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_VECTORS = PROJECT_ROOT / "data" / "faiss" / "movie_vectors.npy"
DEFAULT_IDS = PROJECT_ROOT / "data" / "faiss" / "movie_ids.npy"
DEFAULT_OUTPUT_INDEX = PROJECT_ROOT / "models" / "faiss_hnsw_spark.index"
DEFAULT_OUTPUT_IDS = PROJECT_ROOT / "models" / "faiss_hnsw_spark_ids.npy"

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build standalone FAISS index from Spark ALS vectors.")
    parser.add_argument("--vectors", default=str(DEFAULT_VECTORS), help="movie_vectors.npy path.")
    parser.add_argument("--ids", default=str(DEFAULT_IDS), help="movie_ids.npy path.")
    parser.add_argument("--output-index", default=str(DEFAULT_OUTPUT_INDEX), help="Output FAISS index path.")
    parser.add_argument("--output-ids", default=str(DEFAULT_OUTPUT_IDS), help="Output movie ID map path.")
    parser.add_argument("--m", type=int, default=32, help="HNSW M parameter.")
    parser.add_argument("--ef-construction", type=int, default=200, help="HNSW efConstruction parameter.")
    parser.add_argument("--ef-search", type=int, default=64, help="HNSW efSearch parameter for sample query.")
    return parser.parse_args()


def build_faiss_from_spark_vectors(
    vectors_path: str | Path | None = None,
    ids_path: str | Path | None = None,
    output_index_path: str | Path | None = None,
    output_ids_path: str | Path | None = None,
    m: int = 32,
    ef_construction: int = 200,
    ef_search: int = 64,
) -> dict:
    vectors_file = Path(vectors_path).resolve() if vectors_path else DEFAULT_VECTORS
    ids_file = Path(ids_path).resolve() if ids_path else DEFAULT_IDS
    output_index = Path(output_index_path).resolve() if output_index_path else DEFAULT_OUTPUT_INDEX
    output_ids = Path(output_ids_path).resolve() if output_ids_path else DEFAULT_OUTPUT_IDS

    if not vectors_file.exists():
        raise FileNotFoundError(f"Vectors file not found: {vectors_file}")
    if not ids_file.exists():
        raise FileNotFoundError(f"IDs file not found: {ids_file}")

    vectors = np.load(vectors_file)
    ids = np.load(ids_file)

    if vectors.ndim != 2:
        raise ValueError(f"Vectors must be 2D, got shape={vectors.shape}")
    if ids.ndim != 1:
        raise ValueError(f"IDs must be 1D, got shape={ids.shape}")
    if vectors.shape[0] != ids.shape[0]:
        raise ValueError(f"Vector rows {vectors.shape[0]} != ID rows {ids.shape[0]}")
    if vectors.dtype != np.float32:
        raise ValueError(f"Vectors dtype must be float32, got {vectors.dtype}")
    if not np.isfinite(vectors).all():
        raise ValueError("Vectors contain NaN or Inf")
    if ids.size == 0:
        raise ValueError("IDs array is empty")

    vectors = np.ascontiguousarray(vectors.astype(np.float32))
    dim = vectors.shape[1]
    index = faiss.IndexHNSWFlat(dim, m, faiss.METRIC_INNER_PRODUCT)
    index.hnsw.efConstruction = ef_construction
    index.hnsw.efSearch = ef_search
    index.add(vectors)

    output_index.parent.mkdir(parents=True, exist_ok=True)
    output_ids.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(output_index))
    np.save(output_ids, ids.astype(np.int64))

    distances, indices = index.search(vectors[:1], 10)
    sample_results = [
        {"movieId": int(ids[int(idx)]), "score": float(score)}
        for idx, score in zip(indices[0], distances[0])
        if int(idx) >= 0
    ]

    summary = {
        "vectors_path": str(vectors_file),
        "ids_path": str(ids_file),
        "vectors_shape": tuple(vectors.shape),
        "ids_shape": tuple(ids.shape),
        "vector_dim": int(dim),
        "index_type": "IndexHNSWFlat",
        "output_index_path": str(output_index),
        "output_ids_path": str(output_ids),
        "sample_search_result": sample_results,
        "build_success": output_index.exists() and output_ids.exists(),
    }

    logger.info("vectors path: %s", vectors_file)
    logger.info("ids path: %s", ids_file)
    logger.info("vectors shape: %s", vectors.shape)
    logger.info("ids shape: %s", ids.shape)
    logger.info("vector dim: %s", dim)
    logger.info("index type: IndexHNSWFlat")
    logger.info("output index path: %s", output_index)
    logger.info("output ids path: %s", output_ids)
    logger.info("sample search result: %s", sample_results)
    logger.info("build success: %s", summary["build_success"])
    return summary


def main() -> None:
    args = parse_args()
    try:
        build_faiss_from_spark_vectors(
            args.vectors,
            args.ids,
            args.output_index,
            args.output_ids,
            args.m,
            args.ef_construction,
            args.ef_search,
        )
    except Exception as exc:
        logger.error("%s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
