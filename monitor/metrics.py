from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from app.config import get_settings


START_TIME = time.time()


def build_prometheus_metrics(db_path: str | Path | None = None, redis_ok: bool = False, faiss_size: int = 0) -> str:
    db = Path(db_path or get_settings().recommendation_db_path)
    feedback_total = 0
    recommendation_events = 0
    if db.exists():
        with sqlite3.connect(db) as conn:
            feedback_total = conn.execute("SELECT COUNT(*) FROM feedback_logs").fetchone()[0]
            recommendation_events = conn.execute("SELECT COUNT(*) FROM recommendation_logs").fetchone()[0]

    lines = [
        "# HELP movierec_up Whether the MovieRec API process is up.",
        "# TYPE movierec_up gauge",
        "movierec_up 1",
        "# HELP movierec_uptime_seconds API process uptime in seconds.",
        "# TYPE movierec_uptime_seconds gauge",
        f"movierec_uptime_seconds {time.time() - START_TIME:.3f}",
        "# HELP movierec_redis_up Whether Redis is reachable.",
        "# TYPE movierec_redis_up gauge",
        f"movierec_redis_up {1 if redis_ok else 0}",
        "# HELP movierec_faiss_index_size Number of vectors in the FAISS index.",
        "# TYPE movierec_faiss_index_size gauge",
        f"movierec_faiss_index_size {int(faiss_size)}",
        "# HELP movierec_feedback_total Number of feedback events stored.",
        "# TYPE movierec_feedback_total counter",
        f"movierec_feedback_total {int(feedback_total)}",
        "# HELP movierec_recommendation_events_total Number of recommendation log events stored.",
        "# TYPE movierec_recommendation_events_total counter",
        f"movierec_recommendation_events_total {int(recommendation_events)}",
    ]
    return "\n".join(lines) + "\n"
