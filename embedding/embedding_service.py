"""
Embedding service: orchestrates MF training, loading, and per-entity embedding retrieval.

Normalizes all embeddings to unit length for cosine similarity in FAISS.
"""
import logging
from typing import Optional

import numpy as np

from app.config import get_settings
from embedding.matrix_factorization import MatrixFactorization

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Central service for embedding operations.

    Responsibilities:
    1. Train or load MF model
    2. L2-normalize all embeddings for cosine-similarity ANN retrieval
    3. Provide lookup from original ID to embedding vector
    """

    def __init__(self, pipeline=None):
        self.settings = get_settings()
        self.pipeline = pipeline
        self.model: Optional[MatrixFactorization] = None
        self.user_embeddings: Optional[np.ndarray] = None  # normalized
        self.item_embeddings: Optional[np.ndarray] = None  # normalized
        self._item_embeddings_raw: Optional[np.ndarray] = None  # un-normalized

    def train(self, pipeline) -> "EmbeddingService":
        """Train MF on the pipeline's rating matrix."""
        logger.info("Starting embedding training")
        self.pipeline = pipeline

        self.model = MatrixFactorization(
            n_factors=self.settings.embedding_dim,
            regularization=0.1,
            iterations=20,
        )
        self.model.fit(pipeline.rating_matrix)

        raw_user = self.model.get_all_user_embeddings()
        raw_item = self.model.get_all_item_embeddings()

        self.user_embeddings = self._normalize(raw_user)
        self._item_embeddings_raw = raw_item
        self.item_embeddings = self._normalize(raw_item)

        logger.info(
            f"Embeddings ready: users={self.user_embeddings.shape}, "
            f"items={self.item_embeddings.shape}"
        )
        return self

    def load(self) -> "EmbeddingService":
        """Load pre-trained embeddings from disk."""
        path = self.settings.embedding_model_path
        logger.info(f"Loading embeddings from {path}")

        data = np.load(path, allow_pickle=True)
        self.user_embeddings = data["user_embeddings"]
        self.item_embeddings = data["item_embeddings"]
        self._item_embeddings_raw = data.get("item_embeddings_raw", self.item_embeddings)

        logger.info(
            f"Embeddings loaded: users={self.user_embeddings.shape}, "
            f"items={self.item_embeddings.shape}"
        )
        return self

    def save(self) -> None:
        """Persist embeddings to disk."""
        path = self.settings.embedding_model_path
        from pathlib import Path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            path,
            user_embeddings=self.user_embeddings,
            item_embeddings=self.item_embeddings,
            item_embeddings_raw=self._item_embeddings_raw,
        )
        logger.info(f"Embeddings saved to {path}")

    def get_user_embedding(self, user_id: int) -> Optional[np.ndarray]:
        """Get normalized embedding for a user by their original ID."""
        if self.pipeline is None or self.user_embeddings is None:
            return None
        idx = self.pipeline.user_id_to_idx.get(user_id)
        if idx is None:
            return None
        return self.user_embeddings[idx].copy()

    def get_item_embedding(self, movie_id: int) -> Optional[np.ndarray]:
        """Get normalized embedding for a movie by its original ID."""
        if self.pipeline is None or self.item_embeddings is None:
            return None
        idx = self.pipeline.movie_id_to_idx.get(movie_id)
        if idx is None:
            return None
        return self.item_embeddings[idx].copy()

    def user_id_to_internal_idx(self, user_id: int) -> Optional[int]:
        if self.pipeline is None:
            return None
        return self.pipeline.user_id_to_idx.get(user_id)

    def internal_idx_to_movie_id(self, idx: int) -> Optional[int]:
        if self.pipeline is None:
            return None
        return self.pipeline.idx_to_movie_id.get(idx)

    @staticmethod
    def _normalize(vectors: np.ndarray) -> np.ndarray:
        """L2-normalize vectors. Zero-vectors remain zero."""
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1.0, norms)
        return vectors / norms.astype(np.float32)
