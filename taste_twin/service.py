from __future__ import annotations

import asyncio
import json
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from fastapi import HTTPException

from app.config import PROJECT_ROOT, get_settings
from .schemas import (
    CopyRecipeResponse,
    DemoTwinsResponse,
    JointMenuResponse,
    TasteTwinRecipe,
    TasteTwinRecord,
    TasteTwinRecordMutationResponse,
    TasteTwinRecordsResponse,
    TasteTwinSettingsResponse,
    TasteTwinSettingsUpdate,
    TwinMatchCard,
    TwinProfileResponse,
)
from .user_index import UserFaissPaths, UserTasteFaissIndex


@dataclass(frozen=True)
class TasteTwinPaths:
    auth_db_path: Path
    recommendation_db_path: Path
    ratings_path: Path
    movie_profile_path: Path
    user_profile_path: Path
    embeddings_path: Path
    user_ids_path: Path


class TasteTwinService:
    """Taste Twin service isolated from recall/rank/MMR recommendation logic."""

    def __init__(self, paths: TasteTwinPaths) -> None:
        self.paths = paths
        self.user_index = UserTasteFaissIndex(UserFaissPaths(paths.embeddings_path, paths.user_ids_path))
        self._lock = RLock()
        self._ratings: Optional[pd.DataFrame] = None
        self._movie_by_id: Dict[int, dict] = {}
        self._profile_by_user_id: Dict[int, dict] = {}

    @classmethod
    def create_default(cls) -> "TasteTwinService":
        settings = get_settings()
        return cls(
            TasteTwinPaths(
                auth_db_path=Path(settings.auth_db_path),
                recommendation_db_path=Path(settings.recommendation_db_path),
                ratings_path=PROJECT_ROOT / "data" / "processed" / "ratings_clean.csv",
                movie_profile_path=PROJECT_ROOT / "data" / "features" / "movie_profile.csv",
                user_profile_path=PROJECT_ROOT / "data" / "features" / "user_profile.csv",
                embeddings_path=PROJECT_ROOT / "data" / "lightgcn" / "lightgcn_user_embeddings.npy",
                user_ids_path=PROJECT_ROOT / "data" / "lightgcn" / "lightgcn_user_ids.npy",
            )
        )

    def initialize(self) -> None:
        self._ensure_schema()
        self._load_tables()
        self.rebuild_index()

    def rebuild_index(self) -> None:
        self.user_index.load(self._discoverable_user_ids())

    async def get_settings(self, user_id: int) -> TasteTwinSettingsResponse:
        return await asyncio.to_thread(self._get_settings, user_id)

    async def update_settings(self, user_id: int, payload: TasteTwinSettingsUpdate) -> TasteTwinSettingsResponse:
        result = await asyncio.to_thread(self._update_settings, user_id, payload)
        await asyncio.to_thread(self.rebuild_index)
        return result

    async def match_twins(self, user_id: int, limit: int) -> List[TwinMatchCard]:
        return await asyncio.to_thread(self._match_twins, user_id, limit)

    async def get_profile(
        self,
        user_id: int,
        twin_user_id: int,
        high_page: int,
        low_page: int,
        page_size: int,
    ) -> TwinProfileResponse:
        return await asyncio.to_thread(self._get_profile, user_id, twin_user_id, high_page, low_page, page_size)

    async def copy_recipe(self, user_id: int, movie_id: int) -> CopyRecipeResponse:
        return await asyncio.to_thread(self._copy_recipe, user_id, movie_id)

    async def joint_menu(self, user_id: int, twin_user_id: int, offset: int) -> JointMenuResponse:
        return await asyncio.to_thread(self._joint_menu, user_id, twin_user_id, offset)

    async def create_demo_twins(self, user_id: int, count: int = 5) -> DemoTwinsResponse:
        result = await asyncio.to_thread(self._create_demo_twins, user_id, count)
        await asyncio.to_thread(self.rebuild_index)
        return result

    async def get_records(self, user_id: int, record_type: str, page: int, page_size: int) -> TasteTwinRecordsResponse:
        return await asyncio.to_thread(self._get_records, user_id, record_type, page, page_size)

    async def delete_record(self, user_id: int, record_id: str) -> TasteTwinRecordMutationResponse:
        return await asyncio.to_thread(self._delete_record, user_id, record_id)

    def _ensure_schema(self) -> None:
        self.paths.auth_db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.paths.auth_db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS auth_users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    recipe_user_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    is_discoverable INTEGER NOT NULL DEFAULT 1,
                    community_alias TEXT,
                    preference_tags TEXT
                )
                """
            )
            self._ensure_column(conn, "auth_users", "is_discoverable", "INTEGER NOT NULL DEFAULT 1")
            self._ensure_column(conn, "auth_users", "community_alias", "TEXT")
            self._ensure_column(conn, "auth_users", "preference_tags", "TEXT")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS taste_twin_collections (
                    user_id INTEGER NOT NULL,
                    movie_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, movie_id)
                )
                """
            )
            conn.commit()

    @staticmethod
    def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        rows = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
        if column not in {str(row[1]) for row in rows}:
            conn.execute(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {definition}')

    def _load_tables(self) -> None:
        missing = [path for path in [self.paths.ratings_path, self.paths.movie_profile_path, self.paths.user_profile_path] if not path.exists()]
        if missing:
            raise FileNotFoundError(f"Taste Twin data files not found: {missing}")

        ratings = pd.read_csv(self.paths.ratings_path, usecols=["userId", "movieId", "rating", "timestamp"])
        ratings["userId"] = pd.to_numeric(ratings["userId"], errors="coerce").astype("Int64")
        ratings["movieId"] = pd.to_numeric(ratings["movieId"], errors="coerce").astype("Int64")
        ratings["rating"] = pd.to_numeric(ratings["rating"], errors="coerce")
        ratings["timestamp"] = pd.to_numeric(ratings["timestamp"], errors="coerce").fillna(0).astype(np.int64)
        ratings = ratings.dropna(subset=["userId", "movieId", "rating"])

        movie_profiles = pd.read_csv(self.paths.movie_profile_path)
        movie_profiles["movieId"] = pd.to_numeric(movie_profiles["movieId"], errors="coerce").astype("Int64")
        movie_profiles = movie_profiles.dropna(subset=["movieId"])

        user_profiles = pd.read_csv(self.paths.user_profile_path)
        user_profiles["userId"] = pd.to_numeric(user_profiles["userId"], errors="coerce").astype("Int64")
        user_profiles = user_profiles.dropna(subset=["userId"])

        with self._lock:
            self._ratings = ratings
            self._movie_by_id = {int(row["movieId"]): self._json_safe(row) for row in movie_profiles.to_dict("records")}
            self._profile_by_user_id = {int(row["userId"]): self._json_safe(row) for row in user_profiles.to_dict("records")}

    def _discoverable_user_ids(self) -> List[int]:
        data_user_ids = self._rating_user_ids()
        with sqlite3.connect(self.paths.auth_db_path) as conn:
            discoverable_rows = conn.execute(
                """
                SELECT DISTINCT recipe_user_id
                FROM auth_users
                WHERE is_discoverable = 1 AND recipe_user_id IS NOT NULL
                  AND username NOT LIKE 'taste_twin_demo_%'
                """
            ).fetchall()
            blocked_rows = conn.execute(
                """
                SELECT DISTINCT recipe_user_id
                FROM auth_users
                WHERE recipe_user_id IS NOT NULL
                  AND (is_discoverable = 0 OR username LIKE 'taste_twin_demo_%')
                """
            ).fetchall()
        discoverable_ids = {int(row[0]) for row in discoverable_rows}
        blocked_ids = {int(row[0]) for row in blocked_rows}
        return sorted((data_user_ids | discoverable_ids) - blocked_ids)

    def _get_settings(self, user_id: int) -> TasteTwinSettingsResponse:
        self._ensure_schema()
        with sqlite3.connect(self.paths.auth_db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT recipe_user_id, is_discoverable, community_alias, preference_tags
                FROM auth_users
                WHERE recipe_user_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (int(user_id),),
            ).fetchone()

        if row is None:
            return TasteTwinSettingsResponse(
                user_id=int(user_id),
                is_discoverable=True,
                community_alias=None,
                preference_tags=[],
            )
        saved_tags = self._split_tags(row["preference_tags"])
        return TasteTwinSettingsResponse(
            user_id=int(row["recipe_user_id"]),
            is_discoverable=bool(row["is_discoverable"]),
            community_alias=row["community_alias"],
            preference_tags=saved_tags,
        )

    def _update_settings(self, user_id: int, payload: TasteTwinSettingsUpdate) -> TasteTwinSettingsResponse:
        current = self._get_settings(user_id)
        alias = (payload.community_alias or current.community_alias or self._generate_alias()).strip()[:48]
        tags = self._join_tags(payload.preference_tags)
        with sqlite3.connect(self.paths.auth_db_path) as conn:
            existing = conn.execute(
                "SELECT id FROM auth_users WHERE recipe_user_id = ? ORDER BY id DESC LIMIT 1",
                (int(user_id),),
            ).fetchone()
            if existing is None:
                raise HTTPException(status_code=404, detail="请先登录或绑定有效的食谱用户 ID")
            conn.execute(
                """
                UPDATE auth_users
                SET is_discoverable = ?, community_alias = ?, preference_tags = ?
                WHERE id = ?
                """,
                (1 if payload.is_discoverable else 0, alias, tags, int(existing[0])),
            )
            conn.commit()
        return self._get_settings(user_id)

    def _create_demo_twins(self, user_id: int, count: int) -> DemoTwinsResponse:
        raise HTTPException(status_code=410, detail="本地演示搭子已关闭，请使用真实用户社区匹配")

    def _match_twins(self, user_id: int, limit: int) -> List[TwinMatchCard]:
        current = self._enriched_public_settings(self._require_discoverable(user_id))
        matches = self._rerank_matches(user_id, self.user_index.search(user_id, max(limit, 10) * 4))
        cards: List[TwinMatchCard] = []
        for twin_user_id, cosine_score in matches:
            twin = self._get_public_user(twin_user_id)
            if twin is None:
                continue
            low_rated_recipes = self._with_collection_state(self._rating_recipes(twin_user_id, high=False, limit=3, offset=0), user_id)
            high_limit = 6 if not low_rated_recipes else 3
            high_rated_recipes = self._with_collection_state(self._rating_recipes(twin_user_id, high=True, limit=high_limit, offset=0), user_id)
            cards.append(
                TwinMatchCard(
                    user_id=twin_user_id,
                    community_alias=twin.community_alias or self._public_alias(twin_user_id),
                    match_score=round(max(0.0, min(1.0, cosine_score)) * 100, 1),
                    shared_tags=self._shared_tags(current.preference_tags, twin.preference_tags),
                    top_preference_tags=twin.preference_tags[:3],
                    high_rated_recipes=high_rated_recipes,
                    low_rated_recipes=low_rated_recipes,
                )
            )
            if len(cards) >= limit:
                break
        return cards

    def _get_profile(self, user_id: int, twin_user_id: int, high_page: int, low_page: int, page_size: int) -> TwinProfileResponse:
        self._require_discoverable(user_id)
        twin = self._get_public_user(twin_user_id)
        if twin is None:
            raise HTTPException(status_code=404, detail="饭搭子主页不存在或对方未开启社区发现")

        high_total = self._rating_count(twin_user_id, high=True)
        low_total = self._rating_count(twin_user_id, high=False)
        high_offset = (high_page - 1) * page_size
        low_offset = (low_page - 1) * page_size
        high_rated = self._with_collection_state(self._rating_recipes(twin_user_id, high=True, limit=page_size, offset=high_offset), user_id)
        low_rated = self._with_collection_state(self._rating_recipes(twin_user_id, high=False, limit=page_size, offset=low_offset), user_id)
        recommended = self._with_collection_state(self._unseen_high_rated_by_twin(user_id, twin_user_id, limit=5), user_id)
        return TwinProfileResponse(
            user_id=twin_user_id,
            community_alias=twin.community_alias or self._public_alias(twin_user_id),
            match_score=self._match_score_for(user_id, twin_user_id),
            top_preference_tags=twin.preference_tags[:3],
            recommended_recipes=recommended,
            high_rated_recipes=high_rated,
            low_rated_recipes=low_rated,
            high_page=high_page,
            low_page=low_page,
            page_size=page_size,
            high_total=high_total,
            low_total=low_total,
            high_has_more=high_offset + len(high_rated) < high_total,
            low_has_more=low_offset + len(low_rated) < low_total,
        )

    def _copy_recipe(self, user_id: int, movie_id: int) -> CopyRecipeResponse:
        created_at = datetime.now(timezone.utc).isoformat()
        self._ensure_schema()
        with sqlite3.connect(self.paths.auth_db_path) as conn:
            existing = conn.execute(
                """
                SELECT created_at
                FROM taste_twin_collections
                WHERE user_id = ? AND movie_id = ?
                """,
                (int(user_id), int(movie_id)),
            ).fetchone()
            if existing is not None:
                conn.execute(
                    "DELETE FROM taste_twin_collections WHERE user_id = ? AND movie_id = ?",
                    (int(user_id), int(movie_id)),
                )
                conn.commit()
                self._delete_collection_feedback(user_id, movie_id)
                return CopyRecipeResponse(user_id=user_id, movie_id=movie_id, copied=False, message="已取消收藏")

            conn.execute(
                """
                INSERT INTO taste_twin_collections (user_id, movie_id, created_at)
                VALUES (?, ?, ?)
                """,
                (int(user_id), int(movie_id), created_at),
            )
            conn.commit()
        self._record_collection_feedback(user_id, movie_id, created_at)
        return CopyRecipeResponse(user_id=user_id, movie_id=movie_id, copied=True, message="已收藏")

    def _record_collection_feedback(self, user_id: int, movie_id: int, created_at: str) -> None:
        self.paths.recommendation_db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.paths.recommendation_db_path) as conn:
            conn.execute("INSERT INTO users (user_id) VALUES (?) ON CONFLICT(user_id) DO NOTHING", (int(user_id),))
            conn.execute(
                """
                INSERT INTO movies (movie_id, title)
                VALUES (?, ?)
                ON CONFLICT(movie_id) DO NOTHING
                """,
                (int(movie_id), self._recipe_from_profile(movie_id, 0).title),
            )
            conn.execute(
                """
                INSERT INTO feedback_logs (user_id, movie_id, feedback_type, feedback_value, request_id, run_id, created_at)
                VALUES (?, ?, 'like', NULL, 'taste-twin-copy', 'taste_twin_collection', ?)
                """,
                (int(user_id), int(movie_id), created_at),
            )
            conn.execute(
                """
                INSERT INTO recommendation_logs (request_id, user_id, movie_id, score, reason, model_name, run_id, event_type, created_at)
                VALUES ('taste-twin-copy', ?, ?, NULL, 'copied_from_taste_twin', 'taste_twin', 'taste_twin_collection', 'like', ?)
                """,
                (int(user_id), int(movie_id), created_at),
            )
            conn.commit()

    def _delete_collection_feedback(self, user_id: int, movie_id: int) -> None:
        if not self.paths.recommendation_db_path.exists():
            return
        with sqlite3.connect(self.paths.recommendation_db_path) as conn:
            conn.execute(
                """
                DELETE FROM feedback_logs
                WHERE user_id = ? AND movie_id = ?
                  AND request_id = 'taste-twin-copy'
                  AND run_id = 'taste_twin_collection'
                """,
                (int(user_id), int(movie_id)),
            )
            conn.execute(
                """
                DELETE FROM recommendation_logs
                WHERE user_id = ? AND movie_id = ?
                  AND request_id = 'taste-twin-copy'
                  AND run_id = 'taste_twin_collection'
                """,
                (int(user_id), int(movie_id)),
            )
            conn.commit()

    def _joint_menu(self, user_id: int, twin_user_id: int, offset: int) -> JointMenuResponse:
        self._require_discoverable(user_id)
        if self._get_public_user(twin_user_id) is None:
            raise HTTPException(status_code=404, detail="饭搭子主页不存在或对方未开启社区发现")
        candidates = self._joint_candidates(user_id, twin_user_id)
        if not candidates:
            return JointMenuResponse(twin_user_id=twin_user_id, offset=0, next_offset=0, total_candidates=0, recipes=[])
        start = offset % len(candidates)
        recipes = [candidates[(start + index) % len(candidates)] for index in range(min(5, len(candidates)))]
        return JointMenuResponse(twin_user_id=twin_user_id, offset=start, next_offset=(start + len(recipes)) % len(candidates), total_candidates=len(candidates), recipes=recipes)

    def _get_records(self, user_id: int, record_type: str, page: int, page_size: int) -> TasteTwinRecordsResponse:
        normalized = record_type.strip().lower()
        rows: List[dict] = []
        if normalized in {"all", "collection"}:
            rows.extend(self._collection_rows(user_id))
        if normalized in {"all", "like", "dislike", "not_interested", "rating"}:
            rows.extend(self._feedback_rows(user_id, normalized))
        rows.sort(key=lambda row: row["created_at"], reverse=True)
        total = len(rows)
        start = (page - 1) * page_size
        selected = rows[start : start + page_size]
        records = [self._record_from_row(row) for row in selected]
        return TasteTwinRecordsResponse(user_id=user_id, records=records, page=page, page_size=page_size, total=total, has_more=start + len(records) < total)

    def _delete_record(self, user_id: int, record_id: str) -> TasteTwinRecordMutationResponse:
        if record_id.startswith("collection-"):
            rest = record_id[len("collection-") :]
            movie_text, _, created_at = rest.partition("-")
            if not movie_text.isdigit() or not created_at:
                raise HTTPException(status_code=400, detail="无效的收藏记录 ID")
            movie_id = int(movie_text)
            with sqlite3.connect(self.paths.auth_db_path) as conn:
                cursor = conn.execute(
                    """
                    DELETE FROM taste_twin_collections
                    WHERE user_id = ? AND movie_id = ? AND created_at = ?
                    """,
                    (int(user_id), movie_id, created_at),
                )
                conn.commit()
            self._delete_collection_feedback(user_id, movie_id)
            return TasteTwinRecordMutationResponse(user_id=user_id, record_id=record_id, deleted=cursor.rowcount > 0, message="记录已删除")

        if record_id.startswith("feedback-"):
            feedback_id = record_id[len("feedback-") :]
            if not feedback_id.isdigit():
                raise HTTPException(status_code=400, detail="无效的反馈记录 ID")
            if not self.paths.recommendation_db_path.exists():
                return TasteTwinRecordMutationResponse(user_id=user_id, record_id=record_id, deleted=False, message="记录不存在")
            with sqlite3.connect(self.paths.recommendation_db_path) as conn:
                cursor = conn.execute(
                    "DELETE FROM feedback_logs WHERE id = ? AND user_id = ?",
                    (int(feedback_id), int(user_id)),
                )
                conn.commit()
            return TasteTwinRecordMutationResponse(user_id=user_id, record_id=record_id, deleted=cursor.rowcount > 0, message="记录已删除")

        raise HTTPException(status_code=400, detail="无效的记录 ID")

    def _collected_ids(self, user_id: int) -> set[int]:
        self._ensure_schema()
        with sqlite3.connect(self.paths.auth_db_path) as conn:
            rows = conn.execute(
                "SELECT movie_id FROM taste_twin_collections WHERE user_id = ?",
                (int(user_id),),
            ).fetchall()
        return {int(row[0]) for row in rows}

    def _with_collection_state(self, recipes: List[TasteTwinRecipe], user_id: int) -> List[TasteTwinRecipe]:
        collected = self._collected_ids(user_id)
        for recipe in recipes:
            recipe.is_collected = recipe.movie_id in collected
        return recipes

    def _feedback_sets(self, user_id: int) -> tuple[set[int], set[int]]:
        positive: set[int] = set(self._collected_ids(user_id))
        negative: set[int] = set()
        if self.paths.recommendation_db_path.exists():
            with sqlite3.connect(self.paths.recommendation_db_path) as conn:
                rows = conn.execute(
                    """
                    SELECT movie_id, feedback_type, feedback_value
                    FROM feedback_logs
                    WHERE user_id = ?
                    """,
                    (int(user_id),),
                ).fetchall()
            for movie_id, feedback_type, value in rows:
                if feedback_type == "like" or (feedback_type == "rating" and value is not None and float(value) >= 4):
                    positive.add(int(movie_id))
                if feedback_type in {"dislike", "not_interested"} or (feedback_type == "rating" and value is not None and float(value) <= 2):
                    negative.add(int(movie_id))
        return positive, negative

    def _rerank_matches(self, user_id: int, matches: List[Tuple[int, float]]) -> List[Tuple[int, float]]:
        positive, negative = self._feedback_sets(user_id)
        ranked: List[Tuple[int, float]] = []
        for twin_user_id, score in matches:
            twin_ratings = self._ratings_for_user(twin_user_id)
            twin_high = set(twin_ratings[twin_ratings["rating"] >= 4.0]["movieId"].astype(int).tolist())
            twin_low = set(twin_ratings[twin_ratings["rating"] <= 2.0]["movieId"].astype(int).tolist())
            bonus = len(positive & twin_high) * 0.015 + len(negative & twin_low) * 0.01
            penalty = len(negative & twin_high) * 0.02
            ranked.append((twin_user_id, score + bonus - penalty))
        return sorted(ranked, key=lambda item: item[1], reverse=True)

    def _collection_rows(self, user_id: int) -> List[dict]:
        with sqlite3.connect(self.paths.auth_db_path) as conn:
            rows = conn.execute(
                """
                SELECT user_id, movie_id, created_at
                FROM taste_twin_collections
                WHERE user_id = ?
                """,
                (int(user_id),),
            ).fetchall()
        return [{"id": f"collection-{movie_id}-{created_at}", "user_id": int(uid), "movie_id": int(movie_id), "record_type": "collection", "label": "收藏", "feedback_value": None, "created_at": str(created_at)} for uid, movie_id, created_at in rows]

    def _feedback_rows(self, user_id: int, record_type: str) -> List[dict]:
        if not self.paths.recommendation_db_path.exists():
            return []
        params: List[object] = [int(user_id)]
        where = "user_id = ?"
        if record_type != "all":
            where += " AND feedback_type = ?"
            params.append(record_type)
        else:
            where += " AND feedback_type IN ('like', 'dislike', 'not_interested', 'rating')"
        with sqlite3.connect(self.paths.recommendation_db_path) as conn:
            rows = conn.execute(
                f"""
                SELECT id, user_id, movie_id, feedback_type, feedback_value, created_at
                FROM feedback_logs
                WHERE {where}
                """,
                tuple(params),
            ).fetchall()
        label_map = {"like": "喜欢", "dislike": "不喜欢", "not_interested": "避雷", "rating": "评分"}
        return [{"id": f"feedback-{fid}", "user_id": int(uid), "movie_id": int(movie_id), "record_type": str(ftype), "label": label_map.get(str(ftype), str(ftype)), "feedback_value": value, "created_at": str(created_at)} for fid, uid, movie_id, ftype, value, created_at in rows]

    def _record_from_row(self, row: dict) -> TasteTwinRecord:
        return TasteTwinRecord(**row, recipe=self._recipe_from_profile(int(row["movie_id"]), score=0.0))

    def _require_discoverable(self, user_id: int) -> TasteTwinSettingsResponse:
        settings = self._get_settings(user_id)
        if not settings.is_discoverable:
            raise HTTPException(status_code=403, detail="请先开启允许在社区中被发现，再使用饭搭子功能")
        return settings

    def _get_public_user(self, user_id: int) -> Optional[TasteTwinSettingsResponse]:
        settings = self._get_settings(user_id)
        if not settings.is_discoverable:
            return None
        return self._enriched_public_settings(settings)

    def _enriched_public_settings(self, settings: TasteTwinSettingsResponse) -> TasteTwinSettingsResponse:
        tags = settings.preference_tags or self._default_tags(settings.user_id)
        alias = settings.community_alias or self._public_alias(settings.user_id)
        return TasteTwinSettingsResponse(
            user_id=settings.user_id,
            is_discoverable=settings.is_discoverable,
            community_alias=alias,
            preference_tags=tags[:12],
        )

    def _rating_count(self, user_id: int, high: bool) -> int:
        ratings = self._ratings_for_user(user_id)
        if ratings.empty:
            return 0
        if high:
            return int((ratings["rating"] >= 4.0).sum())
        return int((ratings["rating"] <= 2.0).sum())

    def _rating_recipes(self, user_id: int, high: bool, limit: int, offset: int) -> List[TasteTwinRecipe]:
        ratings = self._ratings_for_user(user_id)
        if ratings.empty:
            return []
        if high:
            selected = ratings[ratings["rating"] >= 4.0].sort_values(["rating", "timestamp"], ascending=[False, False])
        else:
            selected = ratings[ratings["rating"] <= 2.0].sort_values(["rating", "timestamp"], ascending=[True, False])
        return self._recipes_from_rating_rows(selected.iloc[offset : offset + limit])

    def _unseen_high_rated_by_twin(self, user_id: int, twin_user_id: int, limit: int) -> List[TasteTwinRecipe]:
        current_seen = set(self._ratings_for_user(user_id)["movieId"].astype(int).tolist())
        twin_ratings = self._ratings_for_user(twin_user_id)
        selected = twin_ratings[(twin_ratings["rating"] >= 4.0) & (~twin_ratings["movieId"].astype(int).isin(current_seen))]
        selected = selected.sort_values(["rating", "timestamp"], ascending=[False, False]).head(limit)
        return self._recipes_from_rating_rows(selected)

    def _joint_candidates(self, user_id: int, twin_user_id: int) -> List[TasteTwinRecipe]:
        ratings = self._ratings
        if ratings is None:
            return []
        both = ratings[(ratings["userId"].astype(int).isin([int(user_id), int(twin_user_id)])) & (ratings["rating"] >= 4.0)]
        shared = both.groupby("movieId").agg(user_count=("userId", "nunique"), avg_user_rating=("rating", "mean"), latest=("timestamp", "max"))
        shared = shared[shared["user_count"] == 2].sort_values(["avg_user_rating", "latest"], ascending=[False, False]).head(30)
        if not shared.empty:
            rows = [self._rating_row(int(movie_id), float(row["avg_user_rating"]), int(row["latest"])) for movie_id, row in shared.iterrows()]
            return self._recipes_from_rating_rows(pd.DataFrame(rows))
        tags = set(self._default_tags(user_id) + self._default_tags(twin_user_id))
        seen = set(self._ratings_for_user(user_id)["movieId"].astype(int).tolist())
        scored: List[Tuple[float, int]] = []
        for movie_id, profile in self._movie_by_id.items():
            if movie_id in seen:
                continue
            recipe_tags = set(self._split_pipe(profile.get("genres")) + self._split_pipe(profile.get("tag_text")))
            overlap = len(tags & recipe_tags)
            rating = float(profile.get("movie_avg_rating") or profile.get("rating_value") or 0.0)
            count = float(profile.get("movie_rating_count") or profile.get("review_count") or 0.0)
            score = overlap * 2.0 + rating + min(count, 50.0) / 50.0
            if score > 0:
                scored.append((score, movie_id))
        scored.sort(reverse=True)
        return [self._recipe_from_profile(movie_id, score=score) for score, movie_id in scored[:30]]

    def _recipes_from_rating_rows(self, rows: pd.DataFrame) -> List[TasteTwinRecipe]:
        recipes: List[TasteTwinRecipe] = []
        for row in rows.to_dict("records"):
            movie_id = int(row["movieId"])
            rating = float(row.get("rating") or row.get("avg_user_rating") or 0.0)
            recipes.append(self._recipe_from_profile(movie_id, score=rating, user_rating=rating, rated_at=int(row.get("timestamp") or row.get("latest") or 0)))
        return recipes

    def _recipe_from_profile(self, movie_id: int, score: float, user_rating: Optional[float] = None, rated_at: Optional[int] = None) -> TasteTwinRecipe:
        profile = self._movie_by_id.get(int(movie_id), {})
        return TasteTwinRecipe(
            movie_id=int(movie_id),
            title=str(profile.get("title") or profile.get("clean_title") or f"菜谱 {movie_id}"),
            score=float(score),
            genres=str(profile.get("genres") or ""),
            avg_rating=self._optional_float(profile.get("movie_avg_rating") or profile.get("rating_value")),
            rating_count=self._optional_int(profile.get("movie_rating_count") or profile.get("review_count")),
            image_url=str(profile.get("image_url") or ""),
            ready_in_display=str(profile.get("ready_in_display") or ""),
            recipe_yield_raw=str(profile.get("recipe_yield_raw") or ""),
            author_name=str(profile.get("author_name") or ""),
            user_rating=user_rating,
            rated_at=rated_at,
            is_collected=False,
        )

    def _ratings_for_user(self, user_id: int) -> pd.DataFrame:
        ratings = self._ratings
        if ratings is None:
            return pd.DataFrame(columns=["userId", "movieId", "rating", "timestamp"])
        return ratings[ratings["userId"].astype(int) == int(user_id)]

    def _rating_user_ids(self) -> set[int]:
        ratings = self._ratings
        if ratings is None or ratings.empty:
            return set()
        return {int(user_id) for user_id in ratings["userId"].dropna().astype(int).unique().tolist()}

    def _match_score_for(self, user_id: int, twin_user_id: int) -> Optional[float]:
        for matched_user_id, score in self.user_index.search(user_id, 50):
            if matched_user_id == twin_user_id:
                return round(max(0.0, min(1.0, score)) * 100, 1)
        return None

    def _default_tags(self, user_id: int) -> List[str]:
        profile = self._profile_by_user_id.get(int(user_id), {})
        return self._split_pipe(profile.get("favorite_genres"))[:5]

    def _public_alias(self, user_id: int) -> str:
        tags = self._default_tags(user_id)
        tag_set = set(tags)
        generic_tags = {"course", "preparation", "time-to-make", "dietary", "main-ingredient"}
        if {"desserts", "sweet", "chocolate"} & tag_set:
            prefix = "甜品收藏家"
        elif {"healthy", "low-fat", "low-calorie", "vegetarian", "vegan"} & tag_set:
            prefix = "清爽轻食派"
        elif {"spicy", "mexican", "thai", "indian"} & tag_set:
            prefix = "香辣探索家"
        elif {"breakfast", "brunch", "15-minutes-or-less", "30-minutes-or-less"} & tag_set:
            prefix = "快手早餐党"
        elif {"main-dish", "dinner-party", "comfort-food"} & tag_set:
            prefix = "正餐研究员"
        elif {"chicken", "beef", "pork", "seafood", "fish"} & tag_set:
            prefix = "蛋白质猎手"
        elif tag_set <= generic_tags:
            prefix = "全能食谱党"
        elif tags:
            label_map = {
                "easy": "简单菜",
                "quick-and-easy": "快手菜",
                "american": "美式菜",
                "asian": "亚洲菜",
                "italian": "意式菜",
                "mexican": "墨西哥菜",
                "salads": "沙拉",
                "soups-stews": "汤羹",
                "appetizers": "前菜",
                "snacks": "小食",
                "lunch": "午餐",
                "side-dishes": "配菜",
            }
            signal_tag = next((tag for tag in tags if tag not in generic_tags), tags[0])
            prefix = f"{label_map.get(signal_tag, signal_tag)}同好"
        else:
            prefix = "口味探索者"
        return f"{prefix}_{int(user_id)}"

    @staticmethod
    def _shared_tags(left: Sequence[str], right: Sequence[str]) -> List[str]:
        right_set = set(right)
        return [tag for tag in left if tag in right_set][:3]

    @staticmethod
    def _split_tags(raw: object) -> List[str]:
        if raw is None:
            return []
        return [tag.strip() for tag in str(raw).split(",") if tag.strip()][:12]

    @staticmethod
    def _split_pipe(raw: object) -> List[str]:
        if raw is None or (isinstance(raw, float) and pd.isna(raw)):
            return []
        return [tag.strip() for tag in str(raw).split("|") if tag.strip()]

    @staticmethod
    def _join_tags(tags: Iterable[str]) -> str:
        cleaned: List[str] = []
        for tag in tags:
            value = str(tag).strip()
            if value and value not in cleaned:
                cleaned.append(value)
        return ",".join(cleaned[:12])

    @staticmethod
    def _generate_alias() -> str:
        prefixes = ["重度芝士控", "香菜观察员", "夜宵研究员", "清爽低脂派", "高蛋白猎手", "辣味收藏家"]
        return f"{secrets.choice(prefixes)}_{secrets.randbelow(9000) + 1000}"

    @staticmethod
    def _rating_row(movie_id: int, rating: float, timestamp: int) -> dict:
        return {"movieId": movie_id, "rating": rating, "timestamp": timestamp}

    @staticmethod
    def _json_safe(row: dict) -> dict:
        result = {}
        for key, value in row.items():
            if value is None or (isinstance(value, float) and pd.isna(value)):
                result[key] = None
            elif hasattr(value, "item"):
                result[key] = value.item()
            elif isinstance(value, str) and value.strip().startswith(("[", "{")):
                try:
                    result[key] = json.loads(value)
                except json.JSONDecodeError:
                    result[key] = value
            else:
                result[key] = value
        return result

    @staticmethod
    def _optional_float(value: object) -> Optional[float]:
        if value is None or pd.isna(value):
            return None
        return float(value)

    @staticmethod
    def _optional_int(value: object) -> Optional[int]:
        if value is None or pd.isna(value):
            return None
        return int(float(value))
