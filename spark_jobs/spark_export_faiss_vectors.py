"""
Export Spark ALS movie factors to FAISS-readable NumPy files.

Reads data/factors/movie_factors.csv and writes:
    - data/faiss/movie_vectors.npy
    - data/faiss/movie_ids.npy
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MOVIE_FACTORS = PROJECT_ROOT / "data" / "factors" / "movie_factors.csv"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "faiss"

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def parse_bool(value: str | bool) -> bool:
    if isinstance(value, bool):
        return value
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise argparse.ArgumentTypeError(f"Invalid boolean value: {value}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Spark ALS movie factors for FAISS.")
    parser.add_argument("--movie-factors", default=str(DEFAULT_MOVIE_FACTORS), help="Spark movie factors CSV.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="FAISS vector output directory.")
    parser.add_argument("--normalize", type=parse_bool, default=True, help="L2-normalize vectors for cosine search.")
    return parser.parse_args()


def _parse_feature_vector(value: str) -> list[float]:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Empty feature vector")
    return [float(item) for item in value.split("|")]


def export_faiss_vectors(
    movie_factors_path: str | Path | None = None,
    output_dir: str | Path | None = None,
    normalize: bool = True,
) -> dict:
    """Convert movie_factors.csv into movie_vectors.npy and movie_ids.npy."""
    source = Path(movie_factors_path).resolve() if movie_factors_path else DEFAULT_MOVIE_FACTORS
    output_path = Path(output_dir).resolve() if output_dir else DEFAULT_OUTPUT_DIR
    vectors_output = output_path / "movie_vectors.npy"
    ids_output = output_path / "movie_ids.npy"

    if not source.exists():
        raise FileNotFoundError(f"Movie factors input not found: {source}")

    logger.info("Movie factors input: %s", source)
    logger.info("Output directory: %s", output_path)
    logger.info("Normalize enabled: %s", normalize)

    df = pd.read_csv(source)
    missing = {"movieId", "features"} - set(df.columns)
    if missing:
        raise ValueError(f"{source} is missing required columns: {sorted(missing)}")
    if df.empty:
        raise ValueError(f"{source} is empty")

    df = df.dropna(subset=["movieId", "features"]).copy()
    df["movieId"] = df["movieId"].astype(int)
    df = df.sort_values("movieId").reset_index(drop=True)

    parsed = [_parse_feature_vector(value) for value in df["features"]]
    dims = {len(vector) for vector in parsed}
    if len(dims) != 1:
        raise ValueError(f"Inconsistent factor dimensions in {source}: {sorted(dims)}")
    factor_dim = dims.pop()

    movie_vectors = np.asarray(parsed, dtype=np.float32)
    movie_ids = df["movieId"].to_numpy(dtype=np.int64)

    if not np.isfinite(movie_vectors).all():
        raise ValueError("movie_vectors contains NaN or Inf before normalization")

    if normalize:
        norms = np.linalg.norm(movie_vectors, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1.0, norms)
        movie_vectors = (movie_vectors / norms).astype(np.float32)

    output_path.mkdir(parents=True, exist_ok=True)
    np.save(vectors_output, movie_vectors)
    np.save(ids_output, movie_ids)

    if not vectors_output.exists():
        raise RuntimeError(f"movie_vectors.npy was not written: {vectors_output}")
    if not ids_output.exists():
        raise RuntimeError(f"movie_ids.npy was not written: {ids_output}")
    if movie_vectors.shape[0] != movie_ids.shape[0]:
        raise ValueError("movie_vectors row count does not match movie_ids row count")
    if movie_vectors.shape[1] != factor_dim:
        raise ValueError("movie_vectors factor dimension changed unexpectedly")
    if movie_vectors.dtype != np.float32:
        raise ValueError(f"movie_vectors dtype must be float32, got {movie_vectors.dtype}")
    if not np.isfinite(movie_vectors).all():
        raise ValueError("movie_vectors contains NaN or Inf")
    if normalize:
        norms = np.linalg.norm(movie_vectors, axis=1)
        nonzero = norms > 0
        if nonzero.any() and not np.allclose(norms[nonzero], 1.0, atol=1e-4):
            raise ValueError("Normalized movie vector norms are not close to 1")

    summary = {
        "movie_factors_rows": int(len(df)),
        "factor_dimension": int(factor_dim),
        "movie_vectors_shape": tuple(movie_vectors.shape),
        "movie_ids_shape": tuple(movie_ids.shape),
        "normalize": normalize,
        "movie_vectors_path": str(vectors_output),
        "movie_ids_path": str(ids_output),
    }
    logger.info("movie factors rows: %s", summary["movie_factors_rows"])
    logger.info("factor dimension: %s", factor_dim)
    logger.info("movie_vectors shape: %s", movie_vectors.shape)
    logger.info("movie_ids shape: %s", movie_ids.shape)
    logger.info("normalize enabled: %s", normalize)
    logger.info("output paths: %s, %s", vectors_output, ids_output)
    logger.info("validation result: success")
    return summary


def main() -> None:
    args = parse_args()
    try:
        export_faiss_vectors(args.movie_factors, args.output_dir, args.normalize)
    except Exception as exc:
        logger.error("%s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
