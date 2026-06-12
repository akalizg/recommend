from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import faiss
import numpy as np
import pandas as pd

from app.config import PROJECT_ROOT, get_settings
from search.es_recipe_repository import ESRecipeRepository


logger = logging.getLogger(__name__)

FAISS_HNSW_SPARK_INDEX_PATH = PROJECT_ROOT / "models" / "faiss_hnsw_spark.index"
FAISS_HNSW_SPARK_IDS_PATH = PROJECT_ROOT / "models" / "faiss_hnsw_spark_ids.npy"
FAISS_SPARK_VECTORS_PATH = PROJECT_ROOT / "data" / "faiss" / "movie_vectors.npy"
FAISS_SPARK_VECTOR_IDS_PATH = PROJECT_ROOT / "data" / "faiss" / "movie_ids.npy"
OFFLINE_MOVIE_PROFILE_PATH = PROJECT_ROOT / "data" / "features" / "movie_profile.csv"

POSITIVE_TYPES = {"click", "like", "seen"}
NEGATIVE_TYPES = {"dislike", "not_interested"}


class RealtimeRecipeRecommender:
    """Build lightweight realtime recommendations from recent feedback.

    The offline model still owns heavy training. This service only reuses ALS item
    embeddings and FAISS to react quickly when a user clicks or likes a recipe.
    """

    def __init__(
        self,
        index_path: str | Path = FAISS_HNSW_SPARK_INDEX_PATH,
        index_ids_path: str | Path = FAISS_HNSW_SPARK_IDS_PATH,
        vectors_path: str | Path = FAISS_SPARK_VECTORS_PATH,
        vector_ids_path: str | Path = FAISS_SPARK_VECTOR_IDS_PATH,
        profile_path: str | Path = OFFLINE_MOVIE_PROFILE_PATH,
        es_repository: ESRecipeRepository | None = None,
    ) -> None:
        self.index_path = Path(index_path)
        self.index_ids_path = Path(index_ids_path)
        self.vectors_path = Path(vectors_path)
        self.vector_ids_path = Path(vector_ids_path)
        self.profile_path = Path(profile_path)
        self.es_repository = es_repository or ESRecipeRepository()
        self._index: faiss.Index | None = None
        self._index_ids: np.ndarray | None = None
        self._vector_ids: np.ndarray | None = None
        self._vectors: np.ndarray | None = None
        self._profile_df: pd.DataFrame | None = None

    @staticmethod
    def cache_key(user_id: int, top_k: int) -> str:
        return f"recipe:realtime_rec:user:{int(user_id)}:k:{int(top_k)}"

    def build_for_profile(self, profile: dict[str, Any], top_k: int = 20) -> dict[str, Any] | None:
        user_id = int(profile.get("user_id") or 0)
        if user_id <= 0:
            return None

        seed_weights, blocked_ids = self._seed_weights(profile)
        if not seed_weights:
            return None

        candidates = self._collect_candidates(seed_weights, blocked_ids, top_k=top_k)
        if not candidates:
            return None

        items = self._build_items(candidates[:top_k])
        return {
            "user_id": user_id,
            "recommendations": items,
            "cached": False,
            "took_ms": 0.0,
            "source": "kafka_realtime_faiss",
            "seed_recipe_ids": list(seed_weights.keys()),
        }

    def build_and_cache(self, cache, profile: dict[str, Any], top_k: int = 20) -> dict[str, Any] | None:
        result = self.build_for_profile(profile, top_k=top_k)
        if not result:
            return None
        cache.set_json(
            self.cache_key(int(result["user_id"]), top_k),
            result,
            ttl=get_settings().redis_ttl_recommend,
        )
        return result

    def _load_assets(self) -> None:
        if self._index is not None:
            return
        required = [self.index_path, self.index_ids_path, self.vectors_path, self.vector_ids_path]
        missing = [str(path) for path in required if not path.exists()]
        if missing:
            raise FileNotFoundError(f"Realtime FAISS assets not found: {missing}")

        self._index = faiss.read_index(str(self.index_path))
        self._index_ids = np.load(self.index_ids_path).astype(np.int64)
        vector_ids = np.load(self.vector_ids_path).astype(np.int64)
        vectors = np.load(self.vectors_path).astype(np.float32)
        if len(self._index_ids) != self._index.ntotal or len(vector_ids) != len(vectors):
            raise ValueError("Realtime FAISS assets are out of sync")

        order = np.argsort(vector_ids)
        self._vector_ids = vector_ids[order]
        self._vectors = np.ascontiguousarray(vectors[order], dtype=np.float32)

    def _query_vector(self, recipe_id: int) -> np.ndarray | None:
        self._load_assets()
        assert self._vector_ids is not None
        assert self._vectors is not None
        pos = np.searchsorted(self._vector_ids, int(recipe_id))
        if pos >= len(self._vector_ids) or int(self._vector_ids[pos]) != int(recipe_id):
            return None
        return np.ascontiguousarray(self._vectors[pos : pos + 1], dtype=np.float32)

    def _collect_candidates(
        self,
        seed_weights: dict[int, float],
        blocked_ids: set[int],
        top_k: int,
    ) -> list[tuple[int, float]]:
        self._load_assets()
        assert self._index is not None
        assert self._index_ids is not None
        scores_by_id: dict[int, float] = {}
        search_k = min(max(top_k * 8, 40), int(self._index.ntotal))

        for seed_id, weight in seed_weights.items():
            query = self._query_vector(seed_id)
            if query is None:
                continue
            scores, positions = self._index.search(query, search_k)
            for score, pos in zip(scores[0], positions[0]):
                pos = int(pos)
                if pos < 0 or pos >= len(self._index_ids):
                    continue
                recipe_id = int(self._index_ids[pos])
                if recipe_id in blocked_ids or recipe_id == seed_id:
                    continue
                scores_by_id[recipe_id] = scores_by_id.get(recipe_id, 0.0) + float(score) * weight

        return sorted(scores_by_id.items(), key=lambda item: (-item[1], item[0]))

    def _seed_weights(self, profile: dict[str, Any]) -> tuple[dict[int, float], set[int]]:
        positive_ids = _int_list(profile.get("positive_recipe_ids") or profile.get("positive_movie_ids"))
        negative_ids = set(_int_list(profile.get("negative_recipe_ids") or profile.get("negative_movie_ids")))
        recent = profile.get("recent_feedback") if isinstance(profile.get("recent_feedback"), list) else []

        seed_weights: dict[int, float] = {}
        blocked_ids: set[int] = set(negative_ids)
        for idx, event in enumerate(recent[:50]):
            if not isinstance(event, dict):
                continue
            recipe_id = _event_recipe_id(event)
            if recipe_id is None:
                continue
            feedback_type = str(event.get("feedback_type") or "").strip().lower()
            feedback_value = event.get("feedback_value")
            if feedback_type in NEGATIVE_TYPES:
                blocked_ids.add(recipe_id)
                continue
            weight = _feedback_weight(feedback_type, feedback_value)
            if weight <= 0:
                continue
            recency = max(0.35, 1.0 - idx * 0.04)
            seed_weights[recipe_id] = max(seed_weights.get(recipe_id, 0.0), weight * recency)

        for recipe_id in positive_ids[:20]:
            seed_weights[recipe_id] = max(seed_weights.get(recipe_id, 0.0), 0.75)

        blocked_ids.update(seed_weights.keys())
        return seed_weights, blocked_ids

    def _build_items(self, candidates: list[tuple[int, float]]) -> list[dict[str, Any]]:
        recipe_ids = [recipe_id for recipe_id, _ in candidates]
        es_records = self.es_repository.get_recipes(recipe_ids)
        profile_records = self._profile_records(recipe_ids)
        items = []
        for recipe_id, score in candidates:
            info = es_records.get(recipe_id) or profile_records.get(recipe_id) or {}
            items.append(_movie_item_dict(recipe_id, score, info))
        return items

    def _profile_records(self, recipe_ids: list[int]) -> dict[int, dict[str, Any]]:
        if not recipe_ids or not self.profile_path.exists():
            return {}
        if self._profile_df is None:
            df = pd.read_csv(self.profile_path)
            if "movieId" not in df.columns:
                return {}
            df["movieId"] = pd.to_numeric(df["movieId"], errors="coerce")
            self._profile_df = df.dropna(subset=["movieId"]).set_index("movieId", drop=False)

        records: dict[int, dict[str, Any]] = {}
        assert self._profile_df is not None
        for recipe_id in recipe_ids:
            if recipe_id not in self._profile_df.index:
                continue
            row = self._profile_df.loc[recipe_id]
            if isinstance(row, pd.DataFrame):
                row = row.iloc[0]
            records[int(recipe_id)] = _json_safe_record(row.to_dict())
        return records


def _int_list(values: Any) -> list[int]:
    if not isinstance(values, list):
        return []
    result = []
    for value in values:
        try:
            result.append(int(value))
        except (TypeError, ValueError):
            continue
    return result


def _event_recipe_id(event: dict[str, Any]) -> int | None:
    value = event.get("recipe_id", event.get("movie_id"))
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _feedback_weight(feedback_type: str, feedback_value: Any) -> float:
    if feedback_type == "like":
        return 1.25
    if feedback_type == "click":
        return 0.85
    if feedback_type == "seen":
        return 0.45
    if feedback_type == "rating":
        try:
            rating = float(feedback_value)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, (rating - 3.0) / 2.0)
    return 0.0


def _json_safe_record(record: dict[str, Any]) -> dict[str, Any]:
    safe = {}
    for key, value in record.items():
        if _is_missing(value):
            safe[key] = None
        elif hasattr(value, "item"):
            safe[key] = value.item()
        else:
            safe[key] = value
    return safe


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, (list, tuple, dict)):
        return False
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _first_text(info: dict[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        value = info.get(key)
        if not _is_missing(value):
            return str(value)
    return default


def _first_float(info: dict[str, Any], *keys: str, default: float = 0.0) -> float:
    for key in keys:
        value = info.get(key)
        if not _is_missing(value):
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
    return default


def _first_int(info: dict[str, Any], *keys: str, default: int = 0) -> int:
    return int(_first_float(info, *keys, default=float(default)))


def _movie_item_dict(recipe_id: int, score: float, info: dict[str, Any]) -> dict[str, Any]:
    return {
        "movie_id": int(recipe_id),
        "title": _first_text(info, "title", "movie_title", "name", "clean_title", default=f"Recipe {recipe_id}"),
        "score": float(score),
        "genres": _first_text(info, "genres", "movie_genres"),
        "avg_rating": _first_float(info, "rating_value", "avg_rating", "movie_avg_rating"),
        "rating_count": _first_int(info, "review_count", "rating_count", "movie_rating_count"),
        "review_count": _first_int(info, "review_count", "rating_count", "movie_rating_count"),
        "image_url": _first_text(info, "image_url"),
        "ready_in_display": _first_text(info, "ready_in_display"),
        "recipe_yield_raw": _first_text(info, "recipe_yield_raw"),
        "author_name": _first_text(info, "author_name"),
        "poster_url": _first_text(info, "poster_url"),
        "backdrop_url": _first_text(info, "backdrop_url"),
        "overview": _first_text(info, "overview", "description"),
        "release_date": _first_text(info, "release_date"),
        "runtime": info.get("runtime"),
        "vote_average": info.get("vote_average"),
        "popularity": info.get("popularity"),
        "tmdb_id": info.get("tmdb_id"),
        "imdb_id": _first_text(info, "imdb_id"),
    }
