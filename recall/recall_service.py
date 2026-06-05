"""
Recall service: orchestrates ANN retrieval via FAISS HNSW.

Flow:
1. Accept user_id
2. Look up user embedding
3. Search FAISS index for TopK similar movies
4. Apply cold-start fallback (popular movies) if user has no embedding
5. Return candidate movie IDs with similarity scores
"""
import logging
import time
from typing import List, Optional

import numpy as np

from app.config import get_settings
from embedding.embedding_service import EmbeddingService
from feature.pipeline import FeaturePipeline
from recall.faiss_index import FaissHNSWIndex

logger = logging.getLogger(__name__)


class RecallService:
    """
    Recall layer: ANN-based candidate generation.

    Supports:
    - Single-user recall
    - Batch recall for multiple users
    - Cold-start fallback to popular movies
    - Millisecond-level latency
    """

    def __init__(
        self,
        faiss_index: FaissHNSWIndex,
        embedding_service: EmbeddingService,
        pipeline: FeaturePipeline,
    ):
        self.index = faiss_index
        self.embedding = embedding_service
        self.pipeline = pipeline
        self.settings = get_settings()

    def recall(self, user_id: int, k: Optional[int] = None) -> List[dict]:
        """
        Retrieve top-K candidate movies for a user.

        Args:
            user_id: Original user ID from MovieLens.
            k: Number of candidates (default from settings).

        Returns:
            List of {"movie_id": int, "score": float} sorted by similarity descending.
        """
        k = k or self.settings.recall_top_k
        t0 = time.perf_counter()

        user_vec = self.embedding.get_user_embedding(user_id)

        if user_vec is None:
            # Cold start: user not in training set → return popular fallback
            logger.info(f"User {user_id} not in embeddings, using popular fallback")
            return self._popular_fallback(k)

        distances, movie_ids = self.index.search(user_vec, k)

        # Build result, filtering out invalid IDs
        user_history = self._get_user_rated_movies(user_id)
        results = []
        for dist, mid in zip(distances, movie_ids):
            if mid == -1 or mid in user_history:
                continue
            results.append({"movie_id": int(mid), "score": round(float(dist), 6)})

        elapsed_ms = (time.perf_counter() - t0) * 1000
        logger.debug(f"Recall for user {user_id}: {len(results)} candidates in {elapsed_ms:.2f}ms")

        return results[:k]

    def recall_batch(self, user_ids: List[int], k: Optional[int] = None) -> dict:
        """
        Batch recall for multiple users.

        Returns:
            dict mapping user_id → list of candidate dicts.
        """
        k = k or self.settings.recall_top_k
        user_vectors = []
        valid_users = []
        fallback_users = []

        for uid in user_ids:
            vec = self.embedding.get_user_embedding(uid)
            if vec is not None:
                user_vectors.append(vec)
                valid_users.append(uid)
            else:
                fallback_users.append(uid)

        results = {}

        if valid_users:
            query_matrix = np.stack(user_vectors)
            distances_mat, movie_ids_mat = self.index.search_batch(query_matrix, k)

            for i, uid in enumerate(valid_users):
                history = self._get_user_rated_movies(uid)
                candidates = []
                for dist, mid in zip(distances_mat[i], movie_ids_mat[i]):
                    if mid == -1 or mid in history:
                        continue
                    candidates.append({"movie_id": int(mid), "score": round(float(dist), 6)})
                results[uid] = candidates[:k]

        for uid in fallback_users:
            results[uid] = self._popular_fallback(k)

        return results

    def _get_user_rated_movies(self, user_id: int) -> set:
        """Get set of movie IDs this user has already rated."""
        history = self.pipeline.get_user_history(user_id)
        return set(history["movieId"].values) if len(history) > 0 else set()

    def _popular_fallback(self, k: int) -> List[dict]:
        """Return popular movies as cold-start fallback."""
        popular = self.pipeline.get_popular_movies(k)
        return [{"movie_id": m["movie_id"], "score": m.get("popularity_score", 0.0)} for m in popular]
