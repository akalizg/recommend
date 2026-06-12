from __future__ import annotations

import sqlite3

import pandas as pd


def test_ab_service_stable_group_and_metrics(tmp_path):
    from experiment.ab_service import ABService

    db = tmp_path / "rec.db"
    with sqlite3.connect(db) as conn:
        conn.executescript(
            """
            CREATE TABLE feedback_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                movie_id INTEGER,
                feedback_type TEXT,
                feedback_value REAL,
                request_id TEXT,
                run_id TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            INSERT INTO feedback_logs (user_id, movie_id, feedback_type, run_id) VALUES
            (1, 10, 'click', 'A'),
            (1, 11, 'like', 'A'),
            (2, 20, 'dislike', 'B');
            """
        )
    service = ABService(db_path=db)
    assert service.assign_group(1) == service.assign_group(1)
    metrics = service.metrics()
    assert metrics["groups"]
    assert {row["group_name"] for row in metrics["groups"]} == {"A", "B"}


def test_prometheus_metrics_text(tmp_path):
    from monitor.metrics import build_prometheus_metrics

    db = tmp_path / "rec.db"
    with sqlite3.connect(db) as conn:
        conn.executescript(
            """
            CREATE TABLE feedback_logs (id INTEGER PRIMARY KEY);
            CREATE TABLE recommendation_logs (id INTEGER PRIMARY KEY);
            INSERT INTO feedback_logs DEFAULT VALUES;
            INSERT INTO recommendation_logs DEFAULT VALUES;
            """
        )
    text = build_prometheus_metrics(db, redis_ok=True, faiss_size=123)
    assert "movierec_up 1" in text
    assert "movierec_redis_up 1" in text
    assert "movierec_faiss_index_size 123" in text
    assert "movierec_feedback_total 1" in text


def test_lightgcn_graph_and_recall_outputs(tmp_path):
    from spark_jobs.spark_lightgcn_graph_export import export_lightgcn_graph
    from spark_jobs.spark_lightgcn_recall import build_lightgcn_recall

    train = pd.DataFrame(
        [
            {"userId": 1, "movieId": 10, "rating": 5.0},
            {"userId": 2, "movieId": 20, "rating": 4.5},
        ]
    )
    users = pd.DataFrame(
        [
            {"userId": 1, "favorite_genres": "Action|Adventure"},
            {"userId": 2, "favorite_genres": "Comedy|Drama"},
        ]
    )
    movies = pd.DataFrame(
        [
            {"movieId": 10, "genres": "Action|Adventure", "movie_avg_rating": 4.5, "movie_popularity": 10},
            {"movieId": 11, "genres": "Action|Adventure", "movie_avg_rating": 4.0, "movie_popularity": 8},
            {"movieId": 20, "genres": "Comedy|Drama", "movie_avg_rating": 4.2, "movie_popularity": 9},
            {"movieId": 21, "genres": "Comedy|Drama", "movie_avg_rating": 4.1, "movie_popularity": 7},
        ]
    )
    train_path = tmp_path / "train.csv"
    user_path = tmp_path / "users.csv"
    movie_path = tmp_path / "movies.csv"
    graph_path = tmp_path / "graph.csv"
    recall_path = tmp_path / "lightgcn.csv"
    train.to_csv(train_path, index=False)
    users.to_csv(user_path, index=False)
    movies.to_csv(movie_path, index=False)

    graph_summary = export_lightgcn_graph(train_path, movie_path, graph_path)
    assert graph_summary["output_rows"] > 0
    recall_summary = build_lightgcn_recall(user_path, movie_path, train_path, recall_path, top_n=2)
    assert recall_summary["output_rows"] > 0
    recall = pd.read_csv(recall_path)
    assert set(recall["recall_type"]) == {"lightgcn"}
    assert recall.groupby("userId").size().max() <= 2
