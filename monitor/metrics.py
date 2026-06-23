from __future__ import annotations

import logging
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from prometheus_client import CollectorRegistry, generate_latest
from prometheus_client.core import CounterMetricFamily, GaugeMetricFamily
from prometheus_client.exposition import CONTENT_TYPE_LATEST

from app.config import get_settings


logger = logging.getLogger(__name__)
START_TIME = time.time()
METRICS_REGISTRY = CollectorRegistry(auto_describe=False)
PROMETHEUS_CONTENT_TYPE = CONTENT_TYPE_LATEST


@dataclass(frozen=True)
class CompatibilityMetricsSnapshot:
    redis_ok: bool = False
    faiss_size: int = 0
    feedback_total: int = 0
    recommendation_events: int = 0
    exposures_total: int = 0
    clicks_total: int = 0
    likes_total: int = 0
    negatives_total: int = 0
    ctr: float = 0.0


_compatibility_snapshot = CompatibilityMetricsSnapshot()
_compatibility_lock = threading.Lock()


class RecipeRecCompatibilityCollector:
    """Expose existing dashboard metrics through the Prometheus client registry."""

    def collect(self):
        snapshot = _get_compatibility_snapshot()
        uptime = max(time.time() - START_TIME, 0.0)

        yield GaugeMetricFamily(
            "reciperec_up",
            "Whether the RecipeRec API process is up.",
            value=1,
        )
        yield GaugeMetricFamily(
            "reciperec_uptime_seconds",
            "API process uptime in seconds.",
            value=uptime,
        )
        yield GaugeMetricFamily(
            "reciperec_redis_up",
            "Whether Redis is reachable.",
            value=1 if snapshot.redis_ok else 0,
        )
        yield GaugeMetricFamily(
            "reciperec_faiss_index_size",
            "Legacy FAISS vector count if the compatibility service is loaded.",
            value=int(snapshot.faiss_size),
        )
        yield CounterMetricFamily(
            "reciperec_feedback_total",
            "Number of explicit feedback events stored.",
            value=int(snapshot.feedback_total),
        )
        yield CounterMetricFamily(
            "reciperec_recommendation_events_total",
            "Number of recommendation log events stored.",
            value=int(snapshot.recommendation_events),
        )
        yield CounterMetricFamily(
            "reciperec_exposures_total",
            "Number of recommendation exposure events stored.",
            value=int(snapshot.exposures_total),
        )
        yield CounterMetricFamily(
            "reciperec_clicks_total",
            "Number of click events stored.",
            value=int(snapshot.clicks_total),
        )
        yield CounterMetricFamily(
            "reciperec_likes_total",
            "Number of like events stored.",
            value=int(snapshot.likes_total),
        )
        yield CounterMetricFamily(
            "reciperec_negative_feedback_total",
            "Number of negative feedback events stored.",
            value=int(snapshot.negatives_total),
        )
        yield GaugeMetricFamily(
            "reciperec_ctr",
            "Click-through rate based on exposure and click logs.",
            value=float(snapshot.ctr),
        )

        yield GaugeMetricFamily(
            "movierec_up",
            "Legacy alias for dashboards that have not been renamed.",
            value=1,
        )
        yield GaugeMetricFamily(
            "movierec_redis_up",
            "Legacy alias for Redis health.",
            value=1 if snapshot.redis_ok else 0,
        )
        yield GaugeMetricFamily(
            "movierec_faiss_index_size",
            "Legacy alias for FAISS vector count.",
            value=int(snapshot.faiss_size),
        )
        yield CounterMetricFamily(
            "movierec_feedback_total",
            "Legacy alias for feedback event count.",
            value=int(snapshot.feedback_total),
        )


METRICS_REGISTRY.register(RecipeRecCompatibilityCollector())


def build_prometheus_metrics(db_path: str | Path | None = None, redis_ok: bool = False, faiss_size: int = 0) -> str:
    """Build Prometheus exposition text for the current process.

    The public function name is kept for compatibility with the existing
    /metrics route while the implementation now uses prometheus-client.
    """
    update_compatibility_metrics(db_path=db_path, redis_ok=redis_ok, faiss_size=faiss_size)
    return generate_latest(METRICS_REGISTRY).decode("utf-8")


def update_compatibility_metrics(
    db_path: str | Path | None = None,
    redis_ok: bool = False,
    faiss_size: int = 0,
) -> None:
    """Refresh legacy metrics that are still read from service state or SQLite."""
    db = Path(db_path or get_settings().recommendation_db_path)
    counts = _read_sqlite_counts(db)
    snapshot = CompatibilityMetricsSnapshot(
        redis_ok=bool(redis_ok),
        faiss_size=int(faiss_size or 0),
        feedback_total=counts["feedback_total"],
        recommendation_events=counts["recommendation_events"],
        exposures_total=counts["exposures_total"],
        clicks_total=counts["clicks_total"],
        likes_total=counts["likes_total"],
        negatives_total=counts["negatives_total"],
        ctr=counts["ctr"],
    )
    _set_compatibility_snapshot(snapshot)


def _read_sqlite_counts(db: Path) -> dict[str, int | float]:
    counts: dict[str, int | float] = {
        "feedback_total": 0,
        "recommendation_events": 0,
        "exposures_total": 0,
        "clicks_total": 0,
        "likes_total": 0,
        "negatives_total": 0,
        "ctr": 0.0,
    }
    if db.exists():
        try:
            with sqlite3.connect(db, timeout=1.0) as conn:
                if _table_exists(conn, "feedback_logs"):
                    counts["feedback_total"] = conn.execute("SELECT COUNT(*) FROM feedback_logs").fetchone()[0]
                if _table_exists(conn, "recommendation_logs"):
                    counts["recommendation_events"] = conn.execute(
                        "SELECT COUNT(*) FROM recommendation_logs"
                    ).fetchone()[0]
                    if _column_exists(conn, "recommendation_logs", "event_type"):
                        counts["exposures_total"] = conn.execute(
                            "SELECT COUNT(*) FROM recommendation_logs WHERE event_type = 'exposure'"
                        ).fetchone()[0]
                        counts["clicks_total"] = conn.execute(
                            "SELECT COUNT(*) FROM recommendation_logs WHERE event_type = 'click'"
                        ).fetchone()[0]
                        counts["likes_total"] = conn.execute(
                            "SELECT COUNT(*) FROM recommendation_logs WHERE event_type = 'like'"
                        ).fetchone()[0]
                        counts["negatives_total"] = conn.execute(
                            "SELECT COUNT(*) FROM recommendation_logs WHERE event_type IN ('dislike', 'not_interested')"
                        ).fetchone()[0]
                    exposures_total = int(counts["exposures_total"])
                    counts["ctr"] = float(counts["clicks_total"]) / exposures_total if exposures_total else 0.0
        except sqlite3.Error:
            logger.debug("Failed to read metrics from SQLite database %s", db, exc_info=True)
    return counts


def _set_compatibility_snapshot(snapshot: CompatibilityMetricsSnapshot) -> None:
    global _compatibility_snapshot
    with _compatibility_lock:
        _compatibility_snapshot = snapshot


def _get_compatibility_snapshot() -> CompatibilityMetricsSnapshot:
    with _compatibility_lock:
        return _compatibility_snapshot


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _column_exists(conn: sqlite3.Connection, table_name: str, column_name: str) -> bool:
    return any(row[1] == column_name for row in conn.execute(f"PRAGMA table_info({table_name})"))
