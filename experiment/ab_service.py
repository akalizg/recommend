from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path
from typing import Any

from app.config import get_settings


DEFAULT_EXPERIMENT = "recall_rank_v1"
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
            rows = conn.execute(
                """
                SELECT
                    COALESCE(run_id, ?) AS group_name,
                    COUNT(*) AS events,
                    SUM(CASE WHEN feedback_type = 'click' THEN 1 ELSE 0 END) AS clicks,
                    SUM(CASE WHEN feedback_type = 'like' THEN 1 ELSE 0 END) AS likes,
                    SUM(CASE WHEN feedback_type IN ('dislike', 'not_interested') THEN 1 ELSE 0 END) AS negatives
                FROM feedback_logs
                GROUP BY COALESCE(run_id, ?)
                ORDER BY group_name
                """,
                ("unknown", "unknown"),
            ).fetchall()
        groups = []
        for group_name, events, clicks, likes, negatives in rows:
            events = int(events or 0)
            groups.append(
                {
                    "group_name": group_name,
                    "events": events,
                    "clicks": int(clicks or 0),
                    "likes": int(likes or 0),
                    "negatives": int(negatives or 0),
                    "ctr": float(clicks or 0) / events if events else 0.0,
                    "like_rate": float(likes or 0) / events if events else 0.0,
                }
            )
        return {"experiment_name": experiment_name, "groups": groups}
