"""Build a FAISS HNSW embedding recall channel from ALS item vectors."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import faiss
import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TRAIN = PROJECT_ROOT / "data" / "processed" / "train_ratings.csv"
DEFAULT_INDEX = PROJECT_ROOT / "models" / "faiss_hnsw_spark.index"
DEFAULT_INDEX_IDS = PROJECT_ROOT / "models" / "faiss_hnsw_spark_ids.npy"
DEFAULT_VECTORS = PROJECT_ROOT / "data" / "faiss" / "movie_vectors.npy"
DEFAULT_VECTOR_IDS = PROJECT_ROOT / "data" / "faiss" / "movie_ids.npy"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "recall" / "faiss_hnsw_recall.csv"

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build FAISS HNSW recall candidates from user liked recipe vectors.")
    parser.add_argument("--train", default=str(DEFAULT_TRAIN))
    parser.add_argument("--index", default=str(DEFAULT_INDEX))
    parser.add_argument("--index-ids", default=str(DEFAULT_INDEX_IDS))
    parser.add_argument("--vectors", default=str(DEFAULT_VECTORS))
    parser.add_argument("--vector-ids", default=str(DEFAULT_VECTOR_IDS))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--top-n", type=int, default=50)
    parser.add_argument("--search-k", type=int, default=200)
    parser.add_argument("--min-rating", type=float, default=4.0)
    parser.add_argument("--max-liked-per-user", type=int, default=100)
    return parser.parse_args()


def build_faiss_hnsw_recall(
    train_path: str | Path | None = None,
    index_path: str | Path | None = None,
    index_ids_path: str | Path | None = None,
    vectors_path: str | Path | None = None,
    vector_ids_path: str | Path | None = None,
    output_path: str | Path | None = None,
    top_n: int = 50,
    search_k: int = 200,
    min_rating: float = 4.0,
    max_liked_per_user: int = 100,
) -> dict:
    train_file = Path(train_path).resolve() if train_path else DEFAULT_TRAIN
    index_file = Path(index_path).resolve() if index_path else DEFAULT_INDEX
    index_ids_file = Path(index_ids_path).resolve() if index_ids_path else DEFAULT_INDEX_IDS
    vectors_file = Path(vectors_path).resolve() if vectors_path else DEFAULT_VECTORS
    vector_ids_file = Path(vector_ids_path).resolve() if vector_ids_path else DEFAULT_VECTOR_IDS
    output_file = Path(output_path).resolve() if output_path else DEFAULT_OUTPUT

    for path in [train_file, index_file, index_ids_file, vectors_file, vector_ids_file]:
        if not path.exists():
            raise FileNotFoundError(f"Required FAISS recall input not found: {path}")

    train = pd.read_csv(train_file, usecols=["userId", "movieId", "rating"])
    train["userId"] = pd.to_numeric(train["userId"], errors="coerce")
    train["movieId"] = pd.to_numeric(train["movieId"], errors="coerce")
    train["rating"] = pd.to_numeric(train["rating"], errors="coerce")
    train = train.dropna(subset=["userId", "movieId", "rating"]).copy()
    train["userId"] = train["userId"].astype(int)
    train["movieId"] = train["movieId"].astype(int)

    liked = train[train["rating"] >= min_rating].copy()
    if liked.empty:
        raise ValueError("No liked interactions available for FAISS HNSW recall.")

    index = faiss.read_index(str(index_file))
    index_ids = np.load(index_ids_file).astype(np.int64)
    vectors = np.load(vectors_file).astype(np.float32)
    vector_ids = np.load(vector_ids_file).astype(np.int64)
    if len(index_ids) != index.ntotal:
        raise ValueError("index_ids length does not match FAISS index ntotal")
    if len(vectors) != len(vector_ids):
        raise ValueError("vectors length does not match vector_ids length")

    order = np.argsort(vector_ids)
    sorted_ids = vector_ids[order]
    sorted_vectors = np.ascontiguousarray(vectors[order], dtype=np.float32)
    rated_by_user = train.groupby("userId")["movieId"].apply(lambda s: set(s.astype(int))).to_dict()

    rows = []
    search_k = max(search_k, top_n + max_liked_per_user)
    for user_id, group in liked.groupby("userId", sort=True):
        group = group.sort_values(["rating"], ascending=False).head(max_liked_per_user)
        liked_ids = group["movieId"].astype(int).to_numpy()
        positions = np.searchsorted(sorted_ids, liked_ids)
        valid = (positions < len(sorted_ids)) & (sorted_ids[positions] == liked_ids)
        positions = positions[valid]
        if len(positions) == 0:
            continue
        query = sorted_vectors[positions].mean(axis=0, keepdims=True).astype(np.float32)
        norm = np.linalg.norm(query, axis=1, keepdims=True)
        query = query / np.where(norm == 0, 1.0, norm)
        scores, indices = index.search(np.ascontiguousarray(query, dtype=np.float32), min(search_k, index.ntotal))
        seen = rated_by_user.get(int(user_id), set())
        added = 0
        for score, idx in zip(scores[0], indices[0]):
            if int(idx) < 0:
                continue
            movie_id = int(index_ids[int(idx)])
            if movie_id in seen:
                continue
            rows.append(
                {
                    "userId": int(user_id),
                    "movieId": movie_id,
                    "recall_type": "embedding",
                    "recall_score": float(score),
                }
            )
            added += 1
            if added >= top_n:
                break

    output = pd.DataFrame(rows, columns=["userId", "movieId", "recall_type", "recall_score"])
    if output.empty:
        raise ValueError("FAISS HNSW recall output is empty.")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(output_file, index=False)
    summary = {
        "user_count": int(output["userId"].nunique()),
        "recipe_count": int(output["movieId"].nunique()),
        "output_rows": int(len(output)),
        "top_n": int(top_n),
        "output_path": str(output_file),
    }
    logger.info("FAISS HNSW recall summary: %s", summary)
    return summary


def main() -> None:
    args = parse_args()
    try:
        build_faiss_hnsw_recall(
            args.train,
            args.index,
            args.index_ids,
            args.vectors,
            args.vector_ids,
            args.output,
            args.top_n,
            args.search_k,
            args.min_rating,
            args.max_liked_per_user,
        )
    except Exception as exc:
        logger.error("%s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
