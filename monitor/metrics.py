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
    exposures_total = 0
    clicks_total = 0
    likes_total = 0
    negatives_total = 0
    ctr = 0.0
    if db.exists():
        with sqlite3.connect(db) as conn:
            if _table_exists(conn, "feedback_logs"):
                feedback_total = conn.execute("SELECT COUNT(*) FROM feedback_logs").fetchone()[0]
            if _table_exists(conn, "recommendation_logs"):
                recommendation_events = conn.execute("SELECT COUNT(*) FROM recommendation_logs").fetchone()[0]
                if _column_exists(conn, "recommendation_logs", "event_type"):
                    exposures_total = conn.execute(
                        "SELECT COUNT(*) FROM recommendation_logs WHERE event_type = 'exposure'"
                    ).fetchone()[0]
                    clicks_total = conn.execute(
                        "SELECT COUNT(*) FROM recommendation_logs WHERE event_type = 'click'"
                    ).fetchone()[0]
                    likes_total = conn.execute(
                        "SELECT COUNT(*) FROM recommendation_logs WHERE event_type = 'like'"
                    ).fetchone()[0]
                    negatives_total = conn.execute(
                        "SELECT COUNT(*) FROM recommendation_logs WHERE event_type IN ('dislike', 'not_interested')"
                    ).fetchone()[0]
            ctr = float(clicks_total) / exposures_total if exposures_total else 0.0

    lines = [
        "# HELP reciperec_up Whether the RecipeRec API process is up.",
        "# TYPE reciperec_up gauge",
        "reciperec_up 1",
        "# HELP reciperec_uptime_seconds API process uptime in seconds.",
        "# TYPE reciperec_uptime_seconds gauge",
        f"reciperec_uptime_seconds {time.time() - START_TIME:.3f}",
        "# HELP reciperec_redis_up Whether Redis is reachable.",
        "# TYPE reciperec_redis_up gauge",
        f"reciperec_redis_up {1 if redis_ok else 0}",
        "# HELP reciperec_faiss_index_size Legacy FAISS vector count if the compatibility service is loaded.",
        "# TYPE reciperec_faiss_index_size gauge",
        f"reciperec_faiss_index_size {int(faiss_size)}",
        "# HELP reciperec_feedback_total Number of explicit feedback events stored.",
        "# TYPE reciperec_feedback_total counter",
        f"reciperec_feedback_total {int(feedback_total)}",
        "# HELP reciperec_recommendation_events_total Number of recommendation log events stored.",
        "# TYPE reciperec_recommendation_events_total counter",
        f"reciperec_recommendation_events_total {int(recommendation_events)}",
        "# HELP reciperec_exposures_total Number of recommendation exposure events stored.",
        "# TYPE reciperec_exposures_total counter",
        f"reciperec_exposures_total {int(exposures_total)}",
        "# HELP reciperec_clicks_total Number of click events stored.",
        "# TYPE reciperec_clicks_total counter",
        f"reciperec_clicks_total {int(clicks_total)}",
        "# HELP reciperec_likes_total Number of like events stored.",
        "# TYPE reciperec_likes_total counter",
        f"reciperec_likes_total {int(likes_total)}",
        "# HELP reciperec_negative_feedback_total Number of negative feedback events stored.",
        "# TYPE reciperec_negative_feedback_total counter",
        f"reciperec_negative_feedback_total {int(negatives_total)}",
        "# HELP reciperec_ctr Click-through rate based on exposure and click logs.",
        "# TYPE reciperec_ctr gauge",
        f"reciperec_ctr {ctr:.6f}",
        "# HELP movierec_up Legacy alias for dashboards that have not been renamed.",
        "# TYPE movierec_up gauge",
        "movierec_up 1",
        "# HELP movierec_redis_up Legacy alias for Redis health.",
        "# TYPE movierec_redis_up gauge",
        f"movierec_redis_up {1 if redis_ok else 0}",
        "# HELP movierec_faiss_index_size Legacy alias for FAISS vector count.",
        "# TYPE movierec_faiss_index_size gauge",
        f"movierec_faiss_index_size {int(faiss_size)}",
        "# HELP movierec_feedback_total Legacy alias for feedback event count.",
        "# TYPE movierec_feedback_total counter",
        f"movierec_feedback_total {int(feedback_total)}",
    ]
    return "\n".join(lines) + "\n"


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _column_exists(conn: sqlite3.Connection, table_name: str, column_name: str) -> bool:
    return any(row[1] == column_name for row in conn.execute(f"PRAGMA table_info({table_name})"))
