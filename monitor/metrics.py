from __future__ import annotations

import sqlite3
import time
from collections import defaultdict
from pathlib import Path
from threading import Lock

from app.config import get_settings


START_TIME = time.time()
_RUNTIME_LOCK = Lock()
_MODEL_REQUESTS: dict[tuple[str, str], int] = defaultdict(int)
_MODEL_DURATION_SUM: dict[str, float] = defaultdict(float)
_MODEL_DURATION_COUNT: dict[str, int] = defaultdict(int)
_MODEL_RESULT_COUNT: dict[str, int] = defaultdict(int)
_REDUCE_DURATION_SUM = 0.0
_REDUCE_DURATION_COUNT = 0
_REDUCE_INPUT_COUNT = 0
_REDUCE_OUTPUT_COUNT = 0
_RECOMMEND_SOURCE_TOTAL: dict[str, int] = defaultdict(int)


def record_model_inference(model_name: str, status: str, duration_ms: float, result_count: int) -> None:
    safe_model = _label_value(model_name)
    safe_status = _label_value(status)
    with _RUNTIME_LOCK:
        _MODEL_REQUESTS[(safe_model, safe_status)] += 1
        _MODEL_DURATION_SUM[safe_model] += max(float(duration_ms), 0.0) / 1000.0
        _MODEL_DURATION_COUNT[safe_model] += 1
        _MODEL_RESULT_COUNT[safe_model] += max(int(result_count), 0)


def record_reduce(duration_ms: float, input_count: int, output_count: int) -> None:
    global _REDUCE_DURATION_SUM, _REDUCE_DURATION_COUNT, _REDUCE_INPUT_COUNT, _REDUCE_OUTPUT_COUNT
    with _RUNTIME_LOCK:
        _REDUCE_DURATION_SUM += max(float(duration_ms), 0.0) / 1000.0
        _REDUCE_DURATION_COUNT += 1
        _REDUCE_INPUT_COUNT += max(int(input_count), 0)
        _REDUCE_OUTPUT_COUNT += max(int(output_count), 0)


def record_recommend_source(source: str) -> None:
    with _RUNTIME_LOCK:
        _RECOMMEND_SOURCE_TOTAL[_label_value(source)] += 1


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
    lines.extend(_runtime_metric_lines())
    return "\n".join(lines) + "\n"


def _runtime_metric_lines() -> list[str]:
    with _RUNTIME_LOCK:
        model_requests = dict(_MODEL_REQUESTS)
        duration_sum = dict(_MODEL_DURATION_SUM)
        duration_count = dict(_MODEL_DURATION_COUNT)
        result_count = dict(_MODEL_RESULT_COUNT)
        source_total = dict(_RECOMMEND_SOURCE_TOTAL)
        reduce_duration_sum = _REDUCE_DURATION_SUM
        reduce_duration_count = _REDUCE_DURATION_COUNT
        reduce_input_count = _REDUCE_INPUT_COUNT
        reduce_output_count = _REDUCE_OUTPUT_COUNT

    lines = [
        "# HELP model_inference_requests_total Number of model inference attempts.",
        "# TYPE model_inference_requests_total counter",
    ]
    for (model_name, status), count in sorted(model_requests.items()):
        lines.append(f'model_inference_requests_total{{model_name="{model_name}",status="{status}"}} {count}')

    lines.extend(
        [
            "# HELP model_inference_duration_seconds_total Total model inference duration.",
            "# TYPE model_inference_duration_seconds_total counter",
        ]
    )
    for model_name, value in sorted(duration_sum.items()):
        lines.append(f'model_inference_duration_seconds_total{{model_name="{model_name}"}} {value:.6f}')
    lines.extend(
        [
            "# HELP model_inference_duration_seconds_count Number of model inference duration observations.",
            "# TYPE model_inference_duration_seconds_count counter",
        ]
    )
    for model_name, value in sorted(duration_count.items()):
        lines.append(f'model_inference_duration_seconds_count{{model_name="{model_name}"}} {value}')

    lines.extend(
        [
            "# HELP model_inference_result_count Total candidates returned by each model.",
            "# TYPE model_inference_result_count counter",
        ]
    )
    for model_name, value in sorted(result_count.items()):
        lines.append(f'model_inference_result_count{{model_name="{model_name}"}} {value}')

    lines.extend(
        [
            "# HELP recommend_reduce_duration_seconds_total Total Reduce merge duration.",
            "# TYPE recommend_reduce_duration_seconds_total counter",
            f"recommend_reduce_duration_seconds_total {reduce_duration_sum:.6f}",
            "# HELP recommend_reduce_duration_seconds_count Number of Reduce merge observations.",
            "# TYPE recommend_reduce_duration_seconds_count counter",
            f"recommend_reduce_duration_seconds_count {reduce_duration_count}",
            "# HELP recommend_reduce_input_count Total candidates entering Reduce.",
            "# TYPE recommend_reduce_input_count counter",
            f"recommend_reduce_input_count {reduce_input_count}",
            "# HELP recommend_reduce_output_count Total recommendations emitted by Reduce.",
            "# TYPE recommend_reduce_output_count counter",
            f"recommend_reduce_output_count {reduce_output_count}",
            "# HELP recommend_source_total Recommendation responses by selected source.",
            "# TYPE recommend_source_total counter",
        ]
    )
    for source, value in sorted(source_total.items()):
        lines.append(f'recommend_source_total{{source="{source}"}} {value}')
    return lines


def _label_value(value: str) -> str:
    return str(value or "unknown").replace("\\", "\\\\").replace('"', '\\"')


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _column_exists(conn: sqlite3.Connection, table_name: str, column_name: str) -> bool:
    return any(row[1] == column_name for row in conn.execute(f"PRAGMA table_info({table_name})"))
