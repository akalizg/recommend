from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path
from typing import Any

from app.config import get_settings


DEFAULT_EXPERIMENT = "recipe_recall_rank_v1"
GROUPS = ("A", "B")


class ABService:
    def __init__(self, db_path: str | Path | None = None, cache: Any = None) -> None:
        self.db_path = Path(db_path or get_settings().recommendation_db_path)
        self.cache = cache

    def assign_group(self, user_id: int, experiment_name: str = DEFAULT_EXPERIMENT) -> dict[str, str]:
        key = f"ab_group:{experiment_name}:{user_id}"
        if self.cache is not None:
            cached = self.cache.get(key)
            if cached:
                return {"experiment_name": experiment_name, "group_name": cached}
        digest = hashlib.sha256(f"{experiment_name}:{user_id}".encode("utf-8")).hexdigest()
        group = GROUPS[int(digest[:8], 16) % len(GROUPS)]
        if self.cache is not None:
            self.cache.set(key, group, ttl=86400)
        return {"experiment_name": experiment_name, "group_name": group}

    def metrics(self, experiment_name: str = DEFAULT_EXPERIMENT) -> dict[str, Any]:
        if not self.db_path.exists():
            return {"experiment_name": experiment_name, "groups": []}
        with sqlite3.connect(self.db_path) as conn:
            has_feedback = _table_exists(conn, "feedback_logs")
            has_recommendation = _table_exists(conn, "recommendation_logs")
            parts = []
            params: list[str] = []
            if has_recommendation and _column_exists(conn, "recommendation_logs", "event_type"):
                parts.append(
                    """
                    SELECT
                        COALESCE(run_id, ?) AS group_name,
                        CASE WHEN event_type = 'exposure' THEN 1 ELSE 0 END AS exposure,
                        CASE WHEN event_type = 'click' THEN 1 ELSE 0 END AS click,
                        CASE WHEN event_type = 'like' THEN 1 ELSE 0 END AS like_event,
                        CASE WHEN event_type IN ('dislike', 'not_interested') THEN 1 ELSE 0 END AS negative,
                        0 AS feedback_event
                    FROM recommendation_logs
                    """
                )
                params.append("unknown")
            if has_feedback:
                parts.append(
                    """
                    SELECT
                        COALESCE(run_id, ?) AS group_name,
                        0 AS exposure,
                        CASE WHEN feedback_type = 'click' THEN 1 ELSE 0 END AS click,
                        CASE WHEN feedback_type = 'like' THEN 1 ELSE 0 END AS like_event,
                        CASE WHEN feedback_type IN ('dislike', 'not_interested') THEN 1 ELSE 0 END AS negative,
                        1 AS feedback_event
                    FROM feedback_logs
                    """
                )
                params.append("unknown")
            if not parts:
                return {"experiment_name": experiment_name, "groups": []}
            rows = conn.execute(
                f"""
                WITH all_events AS (
                    {" UNION ALL ".join(parts)}
                )
                SELECT
                    group_name,
                    SUM(exposure) AS exposures,
                    SUM(click) AS clicks,
                    SUM(like_event) AS likes,
                    SUM(negative) AS negatives,
                    SUM(feedback_event) AS feedback_events
                FROM all_events
                GROUP BY group_name
                ORDER BY group_name
                """,
                params,
            ).fetchall()
        groups = []
        for group_name, exposures, clicks, likes, negatives, feedback_events in rows:
            exposures = int(exposures or 0)
            feedback_events = int(feedback_events or 0)
            groups.append(
                {
                    "group_name": group_name,
                    "events": feedback_events,
                    "exposures": exposures,
                    "clicks": int(clicks or 0),
                    "likes": int(likes or 0),
                    "negatives": int(negatives or 0),
                    "ctr": float(clicks or 0) / exposures if exposures else 0.0,
                    "like_rate": float(likes or 0) / exposures if exposures else 0.0,
                    "negative_rate": float(negatives or 0) / exposures if exposures else 0.0,
                }
            )
        return {"experiment_name": experiment_name, "groups": groups}


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _column_exists(conn: sqlite3.Connection, table_name: str, column_name: str) -> bool:
    return any(row[1] == column_name for row in conn.execute(f"PRAGMA table_info({table_name})"))
