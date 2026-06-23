from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from prometheus_client import Counter, Histogram

from monitor.metrics import METRICS_REGISTRY


logger = logging.getLogger(__name__)

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests handled by the FastAPI app.",
    labelnames=("method", "path"),
    registry=METRICS_REGISTRY,
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds.",
    labelnames=("method", "path"),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    registry=METRICS_REGISTRY,
)
HTTP_RESPONSE_STATUS_TOTAL = Counter(
    "http_response_status_total",
    "HTTP response status counts.",
    labelnames=("method", "path", "status_code"),
    registry=METRICS_REGISTRY,
)
HTTP_EXCEPTIONS_TOTAL = Counter(
    "http_exceptions_total",
    "Unhandled HTTP exceptions observed by the metrics middleware.",
    labelnames=("method", "path", "exception_type"),
    registry=METRICS_REGISTRY,
)


class HTTPMetricsMiddleware:
    """ASGI middleware that records HTTP request metrics without changing responses."""

    def __init__(self, app: Callable[..., Awaitable[None]]) -> None:
        self.app = app

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[[], Awaitable[dict[str, Any]]],
        send: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        method = str(scope.get("method") or "UNKNOWN").upper()
        started_at = time.perf_counter()
        status_code: int | None = None

        async def send_wrapper(message: dict[str, Any]) -> None:
            nonlocal status_code
            if message.get("type") == "http.response.start":
                status_code = int(message.get("status") or 0)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as exc:
            elapsed = time.perf_counter() - started_at
            _record_http_metrics(
                method=method,
                path=_route_path(scope),
                elapsed_seconds=elapsed,
                status_code=status_code,
                exception_type=exc.__class__.__name__,
            )
            raise

        elapsed = time.perf_counter() - started_at
        _record_http_metrics(
            method=method,
            path=_route_path(scope),
            elapsed_seconds=elapsed,
            status_code=status_code,
            exception_type=None,
        )


def _record_http_metrics(
    method: str,
    path: str,
    elapsed_seconds: float,
    status_code: int | None,
    exception_type: str | None,
) -> None:
    try:
        HTTP_REQUESTS_TOTAL.labels(method=method, path=path).inc()
        HTTP_REQUEST_DURATION_SECONDS.labels(method=method, path=path).observe(max(elapsed_seconds, 0.0))
        if status_code is not None:
            HTTP_RESPONSE_STATUS_TOTAL.labels(
                method=method,
                path=path,
                status_code=str(status_code),
            ).inc()
        if exception_type:
            HTTP_EXCEPTIONS_TOTAL.labels(
                method=method,
                path=path,
                exception_type=exception_type,
            ).inc()
    except Exception:
        logger.debug("Failed to record HTTP metrics", exc_info=True)


def _route_path(scope: dict[str, Any]) -> str:
    route = scope.get("route")
    route_path = getattr(route, "path", None)
    if route_path:
        return str(route_path)
    return "__unmatched__"
