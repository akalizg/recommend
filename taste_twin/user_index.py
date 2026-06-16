from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Iterable, List, Optional, Tuple

import faiss
import numpy as np


@dataclass(frozen=True)
class UserFaissPaths:
    embeddings_path: Path
    user_ids_path: Path


class UserTasteFaissIndex:
    """Process-local FAISS index for discoverable LightGCN user vectors."""

    def __init__(self, paths: UserFaissPaths) -> None:
        self.paths = paths
        self._lock = RLock()
        self._index: Optional[faiss.IndexFlatIP] = None
        self._indexed_user_ids = np.array([], dtype=np.int64)
        self._all_user_ids = np.array([], dtype=np.int64)
        self._all_embeddings = np.empty((0, 0), dtype=np.float32)

    @property
    def size(self) -> int:
        with self._lock:
            return int(self._index.ntotal) if self._index is not None else 0

    def load(self, discoverable_user_ids: Iterable[int]) -> None:
        if not self.paths.embeddings_path.exists():
            raise FileNotFoundError(f"User embedding file not found: {self.paths.embeddings_path}")
        if not self.paths.user_ids_path.exists():
            raise FileNotFoundError(f"LightGCN user id file not found: {self.paths.user_ids_path}")

        embeddings = np.load(self.paths.embeddings_path).astype(np.float32)
        user_ids = np.load(self.paths.user_ids_path).astype(np.int64)
        if embeddings.ndim != 2:
            raise ValueError("lightgcn_user_embeddings.npy must be a 2D array")
        if len(user_ids) != embeddings.shape[0]:
            raise ValueError("lightgcn_user_ids.npy length must match embedding rows")

        allowed_ids = np.array(sorted({int(user_id) for user_id in discoverable_user_ids}), dtype=np.int64)
        mask = np.isin(user_ids, allowed_ids) if allowed_ids.size else np.zeros(len(user_ids), dtype=bool)
        indexed_embeddings = embeddings[mask].copy()
        indexed_user_ids = user_ids[mask].copy()

        index = faiss.IndexFlatIP(embeddings.shape[1])
        if indexed_embeddings.size:
            faiss.normalize_L2(indexed_embeddings)
            index.add(indexed_embeddings)

        with self._lock:
            self._index = index
            self._indexed_user_ids = indexed_user_ids
            self._all_user_ids = user_ids
            self._all_embeddings = embeddings

    def search_all_users(self, user_id: int, top_k: int) -> List[Tuple[int, float]]:
        with self._lock:
            positions = np.where(self._all_user_ids == int(user_id))[0]
            if positions.size == 0 or self._all_embeddings.size == 0:
                return []
            query = self._all_embeddings[int(positions[0])].astype(np.float32, copy=True).reshape(1, -1)
            candidates = self._all_embeddings.astype(np.float32, copy=True)
            faiss.normalize_L2(query)
            faiss.normalize_L2(candidates)
            scores = candidates @ query.reshape(-1)
            order = np.argsort(-scores)
            matches: List[Tuple[int, float]] = []
            for pos in order:
                matched_user_id = int(self._all_user_ids[int(pos)])
                if matched_user_id == int(user_id):
                    continue
                matches.append((matched_user_id, float(scores[int(pos)])))
                if len(matches) >= top_k:
                    break
            return matches

    def search(self, user_id: int, top_k: int) -> List[Tuple[int, float]]:
        with self._lock:
            if self._index is None:
                raise RuntimeError("Taste Twin user FAISS index is not initialized")
            positions = np.where(self._all_user_ids == int(user_id))[0]
            if positions.size == 0 or self._index.ntotal == 0:
                return []
            query = self._all_embeddings[int(positions[0])].astype(np.float32, copy=True).reshape(1, -1)
            faiss.normalize_L2(query)
            scores, indices = self._index.search(query, min(top_k + 1, max(int(self._index.ntotal), 1)))
            matches: List[Tuple[int, float]] = []
            for score, index_pos in zip(scores[0], indices[0]):
                if int(index_pos) < 0:
                    continue
                matched_user_id = int(self._indexed_user_ids[int(index_pos)])
                if matched_user_id == int(user_id):
                    continue
                matches.append((matched_user_id, float(score)))
                if len(matches) >= top_k:
                    break
            return matches
