from __future__ import annotations

import sqlite3


SCHEMA = """
CREATE TABLE users (
    user_id INTEGER PRIMARY KEY
);
CREATE TABLE movies (
    movie_id INTEGER PRIMARY KEY,
    title TEXT NOT NULL
);
CREATE TABLE feedback_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    movie_id INTEGER NOT NULL,
    feedback_type TEXT NOT NULL,
    feedback_value REAL,
    request_id TEXT,
    run_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE recommendation_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT,
    user_id INTEGER,
    movie_id INTEGER,
    rank_position INTEGER,
    score REAL,
    reason TEXT,
    model_name TEXT,
    run_id TEXT,
    event_type TEXT NOT NULL DEFAULT 'offline_import',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


class MemoryCache:
    def __init__(self):
        self.store = {}

    def get_json(self, key):
        return self.store.get(key)

    def set_json(self, key, value, ttl=600):
        self.store[key] = value
        return True

    def delete_pattern(self, pattern):
        return 0

    def delete(self, key):
        self.store.pop(key, None)
        return True


class NoopKafkaProducer:
    def send_event(self, event):
        return False


def test_feedback_service_records_and_updates_profile(tmp_path):
    from feedback.feedback_service import FeedbackService
    from monitor.metrics import build_prometheus_metrics

    db_path = tmp_path / "recommendations.db"
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA)

    cache = MemoryCache()
    service = FeedbackService(db_path=db_path, cache=cache, kafka_producer=NoopKafkaProducer())
    result = service.record_feedback(
        user_id=1,
        movie_id=10,
        feedback_type="like",
        request_id="req-1",
        rank_position=1,
        score=0.9,
    )

    assert result["feedback_id"] == 1
    profile = service.get_realtime_profile(1)
    assert profile["positive_movie_ids"] == [10]
    assert profile["recent_feedback"][0]["feedback_type"] == "like"
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM feedback_logs").fetchone()[0] == 1
        assert conn.execute("SELECT event_type FROM recommendation_logs").fetchone()[0] == "like"
    metrics = build_prometheus_metrics(db_path=db_path)
    assert "# TYPE feedback_events_total counter" in metrics
    assert 'feedback_event_type_total{event_type="like"}' in metrics
    assert "# TYPE recommend_collect_total counter" in metrics


def test_feedback_service_records_exposure_metric(tmp_path):
    from feedback.feedback_service import FeedbackService
    from monitor.metrics import build_prometheus_metrics

    db_path = tmp_path / "recommendations.db"
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA)

    service = FeedbackService(db_path=db_path, kafka_producer=NoopKafkaProducer())
    result = service.record_exposure(user_id=1, movie_id=10, request_id="req-1")

    assert result["event_type"] == "exposure"
    metrics = build_prometheus_metrics(db_path=db_path)
    assert "# TYPE recommend_exposure_total counter" in metrics


def test_feedback_service_rejects_unknown_type(tmp_path):
    from feedback.feedback_service import FeedbackService

    db_path = tmp_path / "recommendations.db"
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA)

    service = FeedbackService(db_path=db_path, kafka_producer=NoopKafkaProducer())
    try:
        service.record_feedback(1, 10, "unknown")
    except ValueError as exc:
        assert "feedback_type" in str(exc)
    else:
        raise AssertionError("expected ValueError")
