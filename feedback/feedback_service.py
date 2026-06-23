from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import PROJECT_ROOT, get_settings
from feedback.kafka_producer import FeedbackKafkaProducer
from monitor.business_metrics import record_feedback_event, record_recommend_exposure


VALID_FEEDBACK_TYPES = {"click", "like", "dislike", "not_interested", "seen", "rating"}
POSITIVE_FEEDBACK = {"click", "like", "seen"}
NEGATIVE_FEEDBACK = {"dislike", "not_interested"}


class FeedbackService:
    def __init__(
        self,
        db_path: str | Path | None = None,
        cache: Any = None,
        kafka_producer: FeedbackKafkaProducer | None = None,
    ) -> None:
        self.db_path = Path(db_path or get_settings().recommendation_db_path)
        self.cache = cache
        self.kafka_producer = kafka_producer or FeedbackKafkaProducer()

    def record_feedback(
        self,
        user_id: int,
        movie_id: int,
        feedback_type: str,
        feedback_value: float | None = None,
        request_id: str | None = None,
        run_id: str | None = None,
        experiment_name: str | None = None,
        group_name: str | None = None,
        rank_position: int | None = None,
        score: float | None = None,
        reason: str | None = None,
    ) -> dict[str, Any]:
        feedback_type = feedback_type.strip().lower()
        if feedback_type not in VALID_FEEDBACK_TYPES:
            raise ValueError(f"feedback_type must be one of {sorted(VALID_FEEDBACK_TYPES)}")

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        created_at = datetime.now(timezone.utc).isoformat()
        group = group_name or run_id
        model_name = experiment_name or "recipe_feedback"
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            self._ensure_user_movie(conn, user_id, movie_id)
            cursor = conn.execute(
                """
                INSERT INTO feedback_logs (
                    user_id, movie_id, feedback_type, feedback_value, request_id, run_id, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, movie_id, feedback_type, feedback_value, request_id, run_id, created_at),
            )
            conn.execute(
                """
                INSERT INTO recommendation_logs (
                    request_id, user_id, movie_id, rank_position, score, reason,
                    model_name, run_id, event_type, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    user_id,
                    movie_id,
                    rank_position,
                    score,
                    reason,
                    model_name,
                    group,
                    feedback_type,
                    created_at,
                ),
            )
            conn.commit()
            feedback_id = int(cursor.lastrowid)
        record_feedback_event(feedback_type)

        realtime_profile = self.update_realtime_profile(
            user_id=user_id,
            movie_id=movie_id,
            feedback_type=feedback_type,
            feedback_value=feedback_value,
            created_at=created_at,
        )
        kafka_event = {
            "event_type": "feedback",
            "user_id": user_id,
            "movie_id": movie_id,
            "recipe_id": movie_id,
            "feedback_type": feedback_type,
            "feedback_value": feedback_value,
            "request_id": request_id,
            "run_id": run_id,
            "experiment_name": experiment_name,
            "group_name": group_name,
            "rank_position": rank_position,
            "score": score,
            "reason": reason,
            "created_at": created_at,
            "source": "fastapi_feedback",
        }
        kafka_sent = self.kafka_producer.send_event(kafka_event) if self.kafka_producer else False
        return {
            "feedback_id": feedback_id,
            "user_id": user_id,
            "movie_id": movie_id,
            "feedback_type": feedback_type,
            "created_at": created_at,
            "realtime_profile": realtime_profile,
            "kafka_sent": kafka_sent,
        }

    def record_exposure(
        self,
        user_id: int,
        movie_id: int,
        request_id: str | None = None,
        run_id: str | None = None,
        experiment_name: str | None = None,
        group_name: str | None = None,
        rank_position: int | None = None,
        score: float | None = None,
        reason: str | None = None,
        model_name: str = "recipe_offline",
    ) -> dict[str, Any]:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        created_at = datetime.now(timezone.utc).isoformat()
        group = group_name or run_id
        model = experiment_name or model_name
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            self._ensure_user_movie(conn, user_id, movie_id)
            cursor = conn.execute(
                """
                INSERT INTO recommendation_logs (
                    request_id, user_id, movie_id, rank_position, score, reason,
                    model_name, run_id, event_type, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'exposure', ?)
                """,
                (request_id, user_id, movie_id, rank_position, score, reason, model, group, created_at),
            )
            conn.commit()
            event_id = int(cursor.lastrowid)
        record_recommend_exposure()
        kafka_event = {
            "event_type": "exposure",
            "user_id": user_id,
            "movie_id": movie_id,
            "recipe_id": movie_id,
            "request_id": request_id,
            "run_id": run_id,
            "experiment_name": experiment_name,
            "group_name": group_name,
            "rank_position": rank_position,
            "score": score,
            "reason": reason,
            "model_name": model,
            "created_at": created_at,
            "source": "fastapi_exposure",
        }
        kafka_sent = self.kafka_producer.send_event(kafka_event) if self.kafka_producer else False
        return {
            "event_id": event_id,
            "user_id": user_id,
            "movie_id": movie_id,
            "event_type": "exposure",
            "created_at": created_at,
            "kafka_sent": kafka_sent,
        }

    def update_realtime_profile(
        self,
        user_id: int,
        movie_id: int,
        feedback_type: str,
        feedback_value: float | None,
        created_at: str,
    ) -> dict[str, Any]:
        profile = {
            "user_id": user_id,
            "positive_movie_ids": [],
            "negative_movie_ids": [],
            "positive_recipe_ids": [],
            "negative_recipe_ids": [],
            "recent_feedback": [],
            "updated_at": created_at,
        }
        key = f"user:realtime_profile:{user_id}"
        if self.cache is not None:
            cached = self.cache.get_json(key)
            if isinstance(cached, dict):
                profile.update(cached)

        if feedback_type in POSITIVE_FEEDBACK:
            _append_unique(profile["positive_movie_ids"], movie_id, max_len=100)
            _append_unique(profile["positive_recipe_ids"], movie_id, max_len=100)
        if feedback_type in NEGATIVE_FEEDBACK:
            _append_unique(profile["negative_movie_ids"], movie_id, max_len=100)
            _append_unique(profile["negative_recipe_ids"], movie_id, max_len=100)
        event = {
            "movie_id": movie_id,
            "recipe_id": movie_id,
            "feedback_type": feedback_type,
            "feedback_value": feedback_value,
            "created_at": created_at,
        }
        profile["recent_feedback"] = [event, *profile.get("recent_feedback", [])][:50]
        profile["updated_at"] = created_at

        if self.cache is not None:
            self.cache.set_json(key, profile, ttl=get_settings().redis_ttl_user_profile)
            self.cache.delete_pattern(f"rec:user:{user_id}:*")
            self.cache.delete(f"profile:{user_id}")
        return profile

    def get_realtime_profile(self, user_id: int) -> dict[str, Any] | None:
        if self.cache is not None:
            cached = self.cache.get_json(f"user:realtime_profile:{user_id}")
            if isinstance(cached, dict):
                return cached
        if not self.db_path.exists():
            return None
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT movie_id, feedback_type, feedback_value, created_at
                FROM feedback_logs
                WHERE user_id = ?
                ORDER BY datetime(created_at) DESC, id DESC
                LIMIT 50
                """,
                (user_id,),
            ).fetchall()
        if not rows:
            return None
        profile = {
            "user_id": user_id,
            "positive_movie_ids": [],
            "negative_movie_ids": [],
            "positive_recipe_ids": [],
            "negative_recipe_ids": [],
            "recent_feedback": [],
            "updated_at": rows[0][3],
        }
        for movie_id, feedback_type, feedback_value, created_at in rows:
            if feedback_type in POSITIVE_FEEDBACK:
                _append_unique(profile["positive_movie_ids"], int(movie_id), max_len=100)
                _append_unique(profile["positive_recipe_ids"], int(movie_id), max_len=100)
            if feedback_type in NEGATIVE_FEEDBACK:
                _append_unique(profile["negative_movie_ids"], int(movie_id), max_len=100)
                _append_unique(profile["negative_recipe_ids"], int(movie_id), max_len=100)
            profile["recent_feedback"].append(
                {
                    "movie_id": int(movie_id),
                    "recipe_id": int(movie_id),
                    "feedback_type": feedback_type,
                    "feedback_value": feedback_value,
                    "created_at": created_at,
                }
            )
        return profile

    def _ensure_user_movie(self, conn: sqlite3.Connection, user_id: int, movie_id: int) -> None:
        conn.execute("INSERT INTO users (user_id) VALUES (?) ON CONFLICT(user_id) DO NOTHING", (user_id,))
        conn.execute(
            """
            INSERT INTO movies (movie_id, title)
            VALUES (?, ?)
            ON CONFLICT(movie_id) DO NOTHING
            """,
            (movie_id, f"Recipe {movie_id}"),
        )


def _append_unique(values: list[int], value: int, max_len: int) -> None:
    if value in values:
        values.remove(value)
    values.insert(0, value)
    del values[max_len:]
