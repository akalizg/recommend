from __future__ import annotations

import logging

from prometheus_client import Counter, Gauge, Histogram

from monitor.metrics import METRICS_REGISTRY


logger = logging.getLogger(__name__)

RECOMMEND_REQUESTS_TOTAL = Counter(
    "recommend_requests_total",
    "Total recommendation endpoint requests.",
    registry=METRICS_REGISTRY,
)
RECOMMEND_RESULT_COUNT = Histogram(
    "recommend_result_count",
    "Recommendation result count per request.",
    labelnames=("source",),
    buckets=(0, 1, 5, 10, 20, 50, 100),
    registry=METRICS_REGISTRY,
)
RECOMMEND_EMPTY_TOTAL = Counter(
    "recommend_empty_total",
    "Total recommendation requests that returned no results.",
    labelnames=("source",),
    registry=METRICS_REGISTRY,
)
RECOMMEND_CACHE_HIT_TOTAL = Counter(
    "recommend_cache_hit_total",
    "Total recommendation cache hits.",
    labelnames=("cache_type",),
    registry=METRICS_REGISTRY,
)
RECOMMEND_FALLBACK_TOTAL = Counter(
    "recommend_fallback_total",
    "Total recommendation fallback usages.",
    labelnames=("fallback_type",),
    registry=METRICS_REGISTRY,
)
RECOMMEND_SOURCE_TOTAL = Counter(
    "recommend_source_total",
    "Total recommendation responses by source.",
    labelnames=("source",),
    registry=METRICS_REGISTRY,
)
FEEDBACK_EVENTS_TOTAL = Counter(
    "feedback_events_total",
    "Total persisted feedback events.",
    registry=METRICS_REGISTRY,
)
FEEDBACK_EVENT_TYPE_TOTAL = Counter(
    "feedback_event_type_total",
    "Total persisted feedback events by type.",
    labelnames=("event_type",),
    registry=METRICS_REGISTRY,
)
RECOMMEND_EXPOSURE_TOTAL = Counter(
    "recommend_exposure_total",
    "Total persisted recommendation exposure events.",
    registry=METRICS_REGISTRY,
)
RECOMMEND_CLICK_TOTAL = Counter(
    "recommend_click_total",
    "Total persisted recommendation click events.",
    registry=METRICS_REGISTRY,
)
RECOMMEND_COLLECT_TOTAL = Counter(
    "recommend_collect_total",
    "Total persisted recommendation collect or like events.",
    registry=METRICS_REGISTRY,
)
RECOMMEND_RATING_TOTAL = Counter(
    "recommend_rating_total",
    "Total persisted recommendation rating events.",
    registry=METRICS_REGISTRY,
)
MODEL_INFERENCE_REQUESTS_TOTAL = Counter(
    "model_inference_requests_total",
    "Total model inference attempts by model and status.",
    labelnames=("model_name", "status"),
    registry=METRICS_REGISTRY,
)
MODEL_INFERENCE_DURATION_SECONDS_TOTAL = Gauge(
    "model_inference_duration_seconds_total",
    "Cumulative model inference duration in seconds.",
    labelnames=("model_name",),
    registry=METRICS_REGISTRY,
)
MODEL_INFERENCE_DURATION_SECONDS_COUNT = Gauge(
    "model_inference_duration_seconds_count",
    "Number of model inference duration observations.",
    labelnames=("model_name",),
    registry=METRICS_REGISTRY,
)
MODEL_INFERENCE_RESULT_COUNT = Gauge(
    "model_inference_result_count",
    "Cumulative candidates returned by each model.",
    labelnames=("model_name",),
    registry=METRICS_REGISTRY,
)
MODEL_INFERENCE_SUCCESS_TOTAL = Counter(
    "model_inference_success_total",
    "Total successful model inference attempts.",
    labelnames=("model_name",),
    registry=METRICS_REGISTRY,
)
MODEL_INFERENCE_ERROR_TOTAL = Counter(
    "model_inference_error_total",
    "Total failed model inference attempts.",
    labelnames=("model_name",),
    registry=METRICS_REGISTRY,
)
MODEL_INFERENCE_TIMEOUT_TOTAL = Counter(
    "model_inference_timeout_total",
    "Total timed out model inference attempts.",
    labelnames=("model_name",),
    registry=METRICS_REGISTRY,
)
RECOMMEND_REDUCE_DURATION_SECONDS_TOTAL = Gauge(
    "recommend_reduce_duration_seconds_total",
    "Cumulative Reduce merge duration in seconds.",
    registry=METRICS_REGISTRY,
)
RECOMMEND_REDUCE_DURATION_SECONDS_COUNT = Gauge(
    "recommend_reduce_duration_seconds_count",
    "Number of Reduce merge observations.",
    registry=METRICS_REGISTRY,
)
RECOMMEND_REDUCE_INPUT_COUNT = Gauge(
    "recommend_reduce_input_count",
    "Cumulative candidates entering Reduce.",
    registry=METRICS_REGISTRY,
)
RECOMMEND_REDUCE_OUTPUT_COUNT = Gauge(
    "recommend_reduce_output_count",
    "Cumulative recommendations emitted by Reduce.",
    registry=METRICS_REGISTRY,
)


def record_recommend_request() -> None:
    try:
        RECOMMEND_REQUESTS_TOTAL.inc()
    except Exception:
        logger.debug("Failed to record recommendation request metric", exc_info=True)


def record_recommend_outcome(
    source: str,
    result_count: int,
    cache_type: str | None = None,
    fallback_type: str | None = None,
) -> None:
    try:
        normalized_source = _safe_label(source, "unknown")
        count = max(int(result_count or 0), 0)
        RECOMMEND_SOURCE_TOTAL.labels(source=normalized_source).inc()
        RECOMMEND_RESULT_COUNT.labels(source=normalized_source).observe(count)
        if count == 0:
            RECOMMEND_EMPTY_TOTAL.labels(source=normalized_source).inc()
        if cache_type:
            RECOMMEND_CACHE_HIT_TOTAL.labels(cache_type=_safe_label(cache_type, "unknown")).inc()
        if fallback_type:
            RECOMMEND_FALLBACK_TOTAL.labels(fallback_type=_safe_label(fallback_type, "unknown")).inc()
    except Exception:
        logger.debug("Failed to record recommendation outcome metrics", exc_info=True)


def record_feedback_event(feedback_type: str) -> None:
    try:
        event_type = _safe_label(feedback_type, "unknown").lower()
        FEEDBACK_EVENTS_TOTAL.inc()
        FEEDBACK_EVENT_TYPE_TOTAL.labels(event_type=event_type).inc()
        if event_type == "click":
            RECOMMEND_CLICK_TOTAL.inc()
        elif event_type in {"like", "collect", "favorite"}:
            RECOMMEND_COLLECT_TOTAL.inc()
        elif event_type == "rating":
            RECOMMEND_RATING_TOTAL.inc()
    except Exception:
        logger.debug("Failed to record feedback event metrics", exc_info=True)


def record_recommend_exposure() -> None:
    try:
        RECOMMEND_EXPOSURE_TOTAL.inc()
    except Exception:
        logger.debug("Failed to record recommendation exposure metric", exc_info=True)


def record_recommend_source(source: str) -> None:
    try:
        RECOMMEND_SOURCE_TOTAL.labels(source=_safe_label(source, "unknown")).inc()
    except Exception:
        logger.debug("Failed to record recommendation source metric", exc_info=True)


def record_model_inference(model_name: str, status: str, duration_ms: float, result_count: int) -> None:
    try:
        model = _safe_label(model_name, "unknown")
        normalized_status = _safe_label(status, "unknown").lower()
        duration_seconds = max(float(duration_ms or 0.0), 0.0) / 1000.0
        count = max(int(result_count or 0), 0)

        MODEL_INFERENCE_REQUESTS_TOTAL.labels(model_name=model, status=normalized_status).inc()
        MODEL_INFERENCE_DURATION_SECONDS_TOTAL.labels(model_name=model).inc(duration_seconds)
        MODEL_INFERENCE_DURATION_SECONDS_COUNT.labels(model_name=model).inc()
        MODEL_INFERENCE_RESULT_COUNT.labels(model_name=model).inc(count)

        if normalized_status == "success":
            MODEL_INFERENCE_SUCCESS_TOTAL.labels(model_name=model).inc()
        elif normalized_status == "timeout":
            MODEL_INFERENCE_TIMEOUT_TOTAL.labels(model_name=model).inc()
        else:
            MODEL_INFERENCE_ERROR_TOTAL.labels(model_name=model).inc()
    except Exception:
        logger.debug("Failed to record model inference metrics", exc_info=True)


def record_reduce(duration_ms: float, input_count: int, output_count: int) -> None:
    try:
        RECOMMEND_REDUCE_DURATION_SECONDS_TOTAL.inc(max(float(duration_ms or 0.0), 0.0) / 1000.0)
        RECOMMEND_REDUCE_DURATION_SECONDS_COUNT.inc()
        RECOMMEND_REDUCE_INPUT_COUNT.inc(max(int(input_count or 0), 0))
        RECOMMEND_REDUCE_OUTPUT_COUNT.inc(max(int(output_count or 0), 0))
    except Exception:
        logger.debug("Failed to record reduce metrics", exc_info=True)


def _safe_label(value: str | None, default: str) -> str:
    text = str(value or "").strip()
    return text if text else default
