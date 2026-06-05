"""
Tests for the recall layer: FAISS index operations and recall service.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pytest


class TestFaissIndex:
    """Test FAISS HNSW index building, search, save/load."""

    def test_build_and_search(self):
        from recall.faiss_index import FaissHNSWIndex

        # Create random embeddings
        n, d = 100, 16
        embeddings = np.random.randn(n, d).astype(np.float32)
        # Normalize
        embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)

        movie_ids = np.arange(1, n + 1)

        index = FaissHNSWIndex(dimension=d)
        index.M = 16
        index.ef_construction = 100
        index.build(embeddings, movie_ids)

        assert index.ntotal == n

        # Search
        query = embeddings[0].copy()
        distances, ids = index.search(query, k=10)

        assert len(distances) == 10
        assert len(ids) == 10
        # The query vector itself should be the top result
        assert ids[0] == movie_ids[0]
        # Inner product of normalized vectors should be ~1.0 for self
        assert distances[0] > 0.99

    def test_save_and_load(self, tmp_path):
        from recall.faiss_index import FaissHNSWIndex

        n, d = 50, 8
        embeddings = np.random.randn(n, d).astype(np.float32)
        embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
        movie_ids = np.arange(1, n + 1)

        index = FaissHNSWIndex(dimension=d)
        index.M = 8
        index.build(embeddings, movie_ids)

        save_path = str(tmp_path / "test_index.faiss")
        index.save(save_path)

        # Load into new instance
        index2 = FaissHNSWIndex(dimension=d)
        index2.load(save_path)

        assert index2.ntotal == n

        # Verify search results match
        query = embeddings[5]
        d1, ids1 = index.search(query, k=5)
        d2, ids2 = index2.search(query, k=5)
        assert np.array_equal(ids1, ids2)

    def test_incremental_add(self):
        from recall.faiss_index import FaissHNSWIndex

        n, d = 20, 8
        embeddings = np.random.randn(n, d).astype(np.float32)
        embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
        movie_ids = list(range(1, n + 1))

        index = FaissHNSWIndex(dimension=d)
        index.M = 8
        index.build(embeddings[:10], np.array(movie_ids[:10]))
        assert index.ntotal == 10

        # Add more
        index.add(embeddings[10:], movie_ids[10:])
        assert index.ntotal == n

    def test_batch_search(self):
        from recall.faiss_index import FaissHNSWIndex

        n, d = 50, 16
        embeddings = np.random.randn(n, d).astype(np.float32)
        embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
        movie_ids = np.arange(1, n + 1)

        index = FaissHNSWIndex(dimension=d)
        index.M = 8
        index.build(embeddings, movie_ids)

        queries = embeddings[:3]
        distances, ids = index.search_batch(queries, k=5)

        assert distances.shape == (3, 5)
        assert ids.shape == (3, 5)
        # Self-match
        for i in range(3):
            assert ids[i, 0] == movie_ids[i]


class TestEmbeddingService:
    """Test embedding training and normalization."""

    def test_normalization(self):
        from embedding.embedding_service import EmbeddingService

        vecs = np.array([[3.0, 4.0], [1.0, 0.0], [0.0, 0.0]], dtype=np.float32)
        normalized = EmbeddingService._normalize(vecs)

        # [3,4] → [0.6, 0.8]
        assert np.allclose(normalized[0], [0.6, 0.8])
        # [1,0] → [1.0, 0.0]
        assert np.allclose(normalized[1], [1.0, 0.0])
        # Zero vector stays zero
        assert np.allclose(normalized[2], [0.0, 0.0])
