import sqlite3
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from monitor.metrics import build_prometheus_metrics
from monitor.business_metrics import (
    record_feedback_event,
    record_model_inference,
    record_recommend_exposure,
    record_recommend_outcome,
    record_recommend_request,
    record_reduce,
)
from monitor.http_metrics import HTTPMetricsMiddleware
from monitor.system_metrics import collect_system_metrics


def test_build_prometheus_metrics_exports_legacy_names(tmp_path):
    db_path = tmp_path / "recommendation.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE feedback_logs (id INTEGER PRIMARY KEY)")
        conn.execute("CREATE TABLE recommendation_logs (id INTEGER PRIMARY KEY, event_type TEXT)")
        conn.executemany("INSERT INTO feedback_logs DEFAULT VALUES", [(), ()])
        conn.executemany(
            "INSERT INTO recommendation_logs (event_type) VALUES (?)",
            [("exposure",), ("exposure",), ("click",), ("like",), ("dislike",)],
        )
        conn.commit()

    metrics = build_prometheus_metrics(db_path=db_path, redis_ok=True, faiss_size=42)

    assert "# TYPE reciperec_up gauge" in metrics
    assert "reciperec_up 1" in metrics
    assert "# TYPE reciperec_feedback_total counter" in metrics
    assert "reciperec_feedback_total 2.0" in metrics
    assert "reciperec_recommendation_events_total 5.0" in metrics
    assert "reciperec_exposures_total 2.0" in metrics
    assert "reciperec_clicks_total 1.0" in metrics
    assert "reciperec_likes_total 1.0" in metrics
    assert "reciperec_negative_feedback_total 1.0" in metrics
    assert "reciperec_redis_up 1.0" in metrics
    assert "reciperec_faiss_index_size 42.0" in metrics
    assert "movierec_up 1" in metrics


def test_build_prometheus_metrics_exports_system_metrics(tmp_path):
    collect_system_metrics(project_root=tmp_path)

    metrics = build_prometheus_metrics()

    assert "# TYPE system_cpu_usage_percent gauge" in metrics
    assert "# TYPE system_cpu_count gauge" in metrics
    assert "# TYPE process_cpu_usage_percent gauge" in metrics
    assert "# TYPE system_memory_usage_percent gauge" in metrics
    assert "# TYPE system_memory_available_bytes gauge" in metrics
    assert "# TYPE process_memory_rss_bytes gauge" in metrics
    assert "# TYPE system_disk_usage_percent gauge" in metrics
    assert "# TYPE system_disk_free_bytes gauge" in metrics
    assert "# TYPE system_disk_read_bytes_total counter" in metrics
    assert "# TYPE system_disk_write_bytes_total counter" in metrics
    assert "# TYPE system_network_sent_bytes_total counter" in metrics
    assert "# TYPE system_network_recv_bytes_total counter" in metrics


def test_http_metrics_middleware_exports_request_metrics():
    app = FastAPI()
    app.add_middleware(HTTPMetricsMiddleware)

    @app.get("/items/{item_id}")
    async def item_detail(item_id: int):
        return {"item_id": item_id}

    @app.get("/boom")
    async def boom():
        raise RuntimeError("boom")

    client = TestClient(app, raise_server_exceptions=False)

    assert client.get("/items/123").status_code == 200
    assert client.get("/missing").status_code == 404
    assert client.get("/boom").status_code == 500

    metrics = build_prometheus_metrics()

    assert "# TYPE http_requests_total counter" in metrics
    assert "# TYPE http_request_duration_seconds histogram" in metrics
    assert "# TYPE http_response_status_total counter" in metrics
    assert "# TYPE http_exceptions_total counter" in metrics
    assert 'http_requests_total{method="GET",path="/items/{item_id}"}' in metrics
    assert 'http_response_status_total{method="GET",path="/items/{item_id}",status_code="200"}' in metrics
    assert 'http_response_status_total{method="GET",path="__unmatched__",status_code="404"}' in metrics
    assert 'exception_type="RuntimeError"' in metrics


def test_recommend_business_metrics_export_labels():
    record_recommend_request()
    record_recommend_outcome(
        source="popular_fallback",
        result_count=0,
        fallback_type="popular_fallback",
    )
    record_recommend_outcome(
        source="redis_offline",
        result_count=2,
        cache_type="redis_offline",
    )

    metrics = build_prometheus_metrics()

    assert "# TYPE recommend_requests_total counter" in metrics
    assert "# TYPE recommend_result_count histogram" in metrics
    assert "# TYPE recommend_empty_total counter" in metrics
    assert "# TYPE recommend_cache_hit_total counter" in metrics
    assert "# TYPE recommend_fallback_total counter" in metrics
    assert "# TYPE recommend_source_total counter" in metrics
    assert 'recommend_source_total{source="popular_fallback"}' in metrics
    assert 'recommend_empty_total{source="popular_fallback"}' in metrics
    assert 'recommend_fallback_total{fallback_type="popular_fallback"}' in metrics
    assert 'recommend_cache_hit_total{cache_type="redis_offline"}' in metrics


def test_recommend_route_records_business_metrics():
    source = (Path(__file__).resolve().parent.parent / "api" / "routes.py").read_text(encoding="utf-8")

    assert "record_recommend_request()" in source
    assert "redis_realtime" in source
    assert "redis_offline" in source
    assert "record_recommend_outcome" in source
    assert "_offline_recommendation_items_with_source" in source
    assert "ParallelInferenceService" in source
    assert "_record_parallel_metrics(response)" in source
    assert "record_model_inference(result.model_name, result.status, result.duration_ms, count)" in source
    assert "record_reduce(response.reduce_duration_ms, input_count, len(response.recommendations))" in source
    assert "source = parallel_response.source" in source


def test_model_inference_business_metrics_export_labels():
    record_model_inference("als", "success", 12.5, 3)
    record_model_inference("itemcf", "timeout", 800, 0)
    record_model_inference("ranker", "error", 5, 0)
    record_reduce(6.0, 12, 5)
    record_recommend_outcome(source="parallel_inference", result_count=5)

    metrics = build_prometheus_metrics()

    assert "# TYPE model_inference_requests_total counter" in metrics
    assert "# TYPE model_inference_success_total counter" in metrics
    assert "# TYPE model_inference_error_total counter" in metrics
    assert "# TYPE model_inference_timeout_total counter" in metrics
    assert "# TYPE model_inference_duration_seconds_total gauge" in metrics
    assert "# TYPE model_inference_duration_seconds_count gauge" in metrics
    assert "# TYPE model_inference_result_count gauge" in metrics
    assert "# TYPE recommend_reduce_duration_seconds_total gauge" in metrics
    assert "# TYPE recommend_reduce_duration_seconds_count gauge" in metrics
    assert "# TYPE recommend_reduce_input_count gauge" in metrics
    assert "# TYPE recommend_reduce_output_count gauge" in metrics
    assert 'model_inference_requests_total{model_name="als",status="success"}' in metrics
    assert 'model_inference_success_total{model_name="als"}' in metrics
    assert 'model_inference_timeout_total{model_name="itemcf"}' in metrics
    assert 'model_inference_error_total{model_name="ranker"}' in metrics
    assert 'model_inference_duration_seconds_total{model_name="als"}' in metrics
    assert 'model_inference_duration_seconds_count{model_name="als"}' in metrics
    assert 'model_inference_result_count{model_name="als"}' in metrics
    assert 'recommend_source_total{source="parallel_inference"}' in metrics


def test_feedback_business_metrics_export_labels():
    record_feedback_event("click")
    record_feedback_event("like")
    record_feedback_event("rating")
    record_recommend_exposure()

    metrics = build_prometheus_metrics()

    assert "# TYPE feedback_events_total counter" in metrics
    assert "# TYPE feedback_event_type_total counter" in metrics
    assert "# TYPE recommend_exposure_total counter" in metrics
    assert "# TYPE recommend_click_total counter" in metrics
    assert "# TYPE recommend_collect_total counter" in metrics
    assert "# TYPE recommend_rating_total counter" in metrics
    assert 'feedback_event_type_total{event_type="click"}' in metrics
    assert 'feedback_event_type_total{event_type="like"}' in metrics
    assert 'feedback_event_type_total{event_type="rating"}' in metrics
