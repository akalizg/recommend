"""
FAISS HNSW index wrapper for ANN (Approximate Nearest Neighbor) retrieval.

UFAISS IndexHNSWFlat which combines:
- HNSW (Hierarchical Navigable Small World) graph for efficient approximate search
- Flat storage for exact distance computation on the selected candidates

Key parameters:
- M: Number of bi-directional links per node (higher = more accurate, more memory).
     Typical: 16-64. Default 32.
- efConstruction: Search depth during index building (higher = better graph quality,
     slower build). Typical: 100-500. Default 200.
- efSearch: Search depth during query (higher = more accurate, slower query).
     Can be tuned at query time without rebuilding. Typical: 16-512. Default 64.
"""
import logging
import os
import time
from pathlib import Path
from typing import List, Optional, Tuple

import faiss
import numpy as np

from app.config import get_settings

logger = logging.getLogger(__name__)


class FaissHNSWIndex:
    """
    FAISS IndexHNSWFlat wrapper for movie embedding ANN retrieval.

    Supports:
    - Building index from embedding vectors
    - Cosine similarity (via inner product on normalized vectors)
    - Top-K retrieval
    - Incremental addition of new vectors
    - Save/load persistence
    """

    def __init__(self, dimension: Optional[int] = None):
        settings = get_settings()
        self.dimension = dimension or settings.faiss_dimension
        self.M = settings.faiss_m
        self.ef_construction = settings.faiss_ef_construction
        self.ef_search = settings.faiss_ef_search
        self.index_path = settings.faiss_index_path

        self.index: Optional[faiss.IndexHNSWFlat] = None
        self._id_map: List[int] = []  # FAISS internal idx → movieId

    def build(self, embeddings: np.ndarray, movie_ids: np.ndarray) -> "FaissHNSWIndex":
        """
        Build a new HNSW index from item embeddings.

        Args:
            embeddings: (n_items, dim) float32 numpy array, L2-normalized.
            movie_ids: (n_items,) array of original movie IDs.
        """
        n, d = embeddings.shape
        self.dimension = d
        logger.info(
            f"Building FAISS IndexHNSWFlat: n={n}, dim={d}, "
            f"M={self.M}, efConstruction={self.ef_construction}"
        )

        t0 = time.perf_counter()

        # IndexHNSWFlat uses inner product (for cosine similarity on normalized vectors)
        self.index = faiss.IndexHNSWFlat(d, self.M, faiss.METRIC_INNER_PRODUCT)
        self.index.hnsw.efConstruction = self.ef_construction
        self.index.hnsw.efSearch = self.ef_search

        embeddings = np.ascontiguousarray(embeddings.astype(np.float32))
        self.index.add(embeddings)
        self._id_map = list(movie_ids)

        elapsed = time.perf_counter() - t0
        logger.info(f"Index built in {elapsed:.2f}s, total vectors: {self.index.ntotal}")

        # Persist immediately
        self.save()
        return self

    def search(self, query_vector: np.ndarray, k: int = 100) -> Tuple[np.ndarray, np.ndarray]:
        """
        Search for top-K nearest neighbors.

        Args:
            query_vector: (1, dim) or (dim,) float32 normalized query vector.
            k: Number of neighbors to retrieve.

        Returns:
            (distances, movie_ids) — each (k,) arrays.
            distances are inner-product similarity (higher = more similar).
        """
        if self.index is None:
            raise RuntimeError("Index not built or loaded.")

        query = np.ascontiguousarray(query_vector.astype(np.float32))
        if query.ndim == 1:
            query = query.reshape(1, -1)

        self.index.hnsw.efSearch = self.ef_search
        distances, indices = self.index.search(query, k)

        # Map internal indices to movie IDs
        movie_ids = np.array([self._id_map[i] if i < len(self._id_map) else -1 for i in indices[0]])

        return distances[0], movie_ids

    def search_batch(
        self, query_vectors: np.ndarray, k: int = 100
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Batch search: (batch_size, dim) → (batch_size, k) distances and movie IDs.
        """
        if self.index is None:
            raise RuntimeError("Index not built or loaded.")

        queries = np.ascontiguousarray(query_vectors.astype(np.float32))
        self.index.hnsw.efSearch = self.ef_search
        distances, indices = self.index.search(queries, k)

        movie_ids = np.zeros_like(indices)
        for i in range(len(indices)):
            movie_ids[i] = [self._id_map[j] if j < len(self._id_map) else -1 for j in indices[i]]

        return distances, movie_ids

    def add(self, embeddings: np.ndarray, movie_ids: List[int]) -> None:
        """
        Incrementally add new movie embeddings to the index.

        Note: HNSW supports incremental addition, though the graph quality
        degrades slightly vs rebuilding. For production, periodic rebuilds
        are recommended.
        """
        if self.index is None:
            raise RuntimeError("Index not built yet. Call build() first.")

        embeddings = np.ascontiguousarray(embeddings.astype(np.float32))
        start_idx = len(self._id_map)
        self.index.add(embeddings)
        self._id_map.extend(movie_ids)
        logger.info(f"Added {len(movie_ids)} vectors to index, total={self.index.ntotal}")

    def save(self, path: Optional[str] = None) -> None:
        """Persist the FAISS index and ID map to disk."""
        save_path = path or self.index_path
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)

        faiss.write_index(self.index, save_path)
        # Save ID map alongside
        idmap_path = save_path + ".idmap"
        np.save(idmap_path, np.array(self._id_map, dtype=np.int64))
        logger.info(f"Index saved to {save_path}")

    def load(self, path: Optional[str] = None) -> "FaissHNSWIndex":
        """Load a previously saved FAISS index."""
        load_path = path or self.index_path
        if not os.path.exists(load_path):
            raise FileNotFoundError(f"Index file not found: {load_path}")

        self.index = faiss.read_index(load_path)
        self.dimension = self.index.d

        # Load ID map
        idmap_path = load_path + ".idmap"
        if os.path.exists(idmap_path):
            self._id_map = np.load(idmap_path).tolist()

        # Restore HNSW parameters
        self.index.hnsw.efSearch = self.ef_search

        logger.info(
            f"Index loaded from {load_path}: {self.index.ntotal} vectors, dim={self.dimension}"
        )
        return self

    @property
    def ntotal(self) -> int:
        return self.index.ntotal if self.index else 0

    def set_ef_search(self, ef: int) -> None:
        """Dynamically adjust efSearch for query-time accuracy/speed trade-off."""
        self.ef_search = ef
        if self.index:
            self.index.hnsw.efSearch = ef
