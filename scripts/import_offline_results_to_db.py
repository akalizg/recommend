"""
Import offline recommendation artifacts into a local SQLite database.

This script only persists offline data. It does not change the FastAPI
recommendation flow or read from the database at serving time.
"""
from __future__ import annotations

import argparse
import csv
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "recommendations.db"
DEFAULT_SCHEMA_PATH = PROJECT_ROOT / "sql" / "recommendation_schema.sql"

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def none_if_blank(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value if value else None


def to_int(value: str | None) -> int | None:
    value = none_if_blank(value)
    return int(float(value)) if value is not None else None


def to_float(value: str | None) -> float | None:
    value = none_if_blank(value)
    return float(value) if value is not None else None


def to_iso_timestamp(value: str | None) -> str | None:
    timestamp = to_int(value)
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


def open_csv(path: Path) -> Iterable[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            yield row


def require_file(path: Path) -> Path:
    if not path.exists():
        raise FileNotFoundError(f"Required input file not found: {path}")
    return path


def execute_schema(conn: sqlite3.Connection, schema_path: Path) -> None:
    logger.info("Applying schema: %s", schema_path)
    with schema_path.open("r", encoding="utf-8") as file:
        conn.executescript(file.read())


def import_movies(conn: sqlite3.Connection, movies_path: Path) -> int:
    rows = []
    for row in open_csv(movies_path):
        rows.append(
            (
                to_int(row.get("movieId")),
                none_if_blank(row.get("title")),
                none_if_blank(row.get("genres")),
            )
        )

    conn.executemany(
        """
        INSERT INTO movies (movie_id, title, genres)
        VALUES (?, ?, ?)
        ON CONFLICT(movie_id) DO UPDATE SET
            title = COALESCE(excluded.title, movies.title),
            genres = COALESCE(excluded.genres, movies.genres),
            updated_at = CURRENT_TIMESTAMP
        """,
        rows,
    )
    logger.info("Imported movies: %s", len(rows))
    return len(rows)


def import_ratings(conn: sqlite3.Connection, ratings_path: Path) -> int:
    user_rows: dict[int, tuple[int]] = {}
    rating_rows = []
    for row in open_csv(ratings_path):
        user_id = to_int(row.get("userId"))
        movie_id = to_int(row.get("movieId"))
        timestamp = to_int(row.get("timestamp"))
        if user_id is None or movie_id is None:
            continue
        user_rows[user_id] = (user_id,)
        rating_rows.append(
            (
                user_id,
                movie_id,
                to_float(row.get("rating")),
                timestamp,
                to_iso_timestamp(row.get("timestamp")),
            )
        )

    conn.executemany(
        """
        INSERT INTO users (user_id)
        VALUES (?)
        ON CONFLICT(user_id) DO NOTHING
        """,
        user_rows.values(),
    )
    conn.executemany(
        """
        INSERT INTO ratings (user_id, movie_id, rating, rating_timestamp, rated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id, movie_id, rating_timestamp) DO UPDATE SET
            rating = excluded.rating,
            rated_at = excluded.rated_at
        """,
        rating_rows,
    )
    logger.info("Imported ratings: %s", len(rating_rows))
    return len(rating_rows)


def import_user_profiles(conn: sqlite3.Connection, user_profile_path: Path) -> int:
    rows = []
    user_rows = []
    for row in open_csv(user_profile_path):
        user_id = to_int(row.get("userId"))
        if user_id is None:
            continue
        rating_count = to_int(row.get("user_rating_count"))
        avg_rating = to_float(row.get("user_avg_rating"))
        active_level = none_if_blank(row.get("active_level"))
        user_rows.append((user_id, rating_count, avg_rating, active_level))
        rows.append(
            (
                user_id,
                rating_count,
                avg_rating,
                to_float(row.get("user_rating_std")),
                to_float(row.get("user_min_rating")),
                to_float(row.get("user_max_rating")),
                none_if_blank(row.get("favorite_genres")),
                none_if_blank(row.get("favorite_decades")),
                active_level,
                none_if_blank(row.get("high_rating_movie_ids")),
                none_if_blank(row.get("recent_movie_ids")),
                str(user_profile_path.relative_to(PROJECT_ROOT)),
            )
        )

    conn.executemany(
        """
        INSERT INTO users (user_id, rating_count, avg_rating, active_level)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            rating_count = COALESCE(excluded.rating_count, users.rating_count),
            avg_rating = COALESCE(excluded.avg_rating, users.avg_rating),
            active_level = COALESCE(excluded.active_level, users.active_level),
            updated_at = CURRENT_TIMESTAMP
        """,
        user_rows,
    )
    conn.executemany(
        """
        INSERT INTO user_profiles (
            user_id, rating_count, avg_rating, rating_std, min_rating, max_rating,
            favorite_genres, favorite_decades, active_level, high_rating_movie_ids,
            recent_movie_ids, feature_source
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            rating_count = excluded.rating_count,
            avg_rating = excluded.avg_rating,
            rating_std = excluded.rating_std,
            min_rating = excluded.min_rating,
            max_rating = excluded.max_rating,
            favorite_genres = excluded.favorite_genres,
            favorite_decades = excluded.favorite_decades,
            active_level = excluded.active_level,
            high_rating_movie_ids = excluded.high_rating_movie_ids,
            recent_movie_ids = excluded.recent_movie_ids,
            feature_source = excluded.feature_source,
            updated_at = CURRENT_TIMESTAMP
        """,
        rows,
    )
    logger.info("Imported user profiles: %s", len(rows))
    return len(rows)


def import_movie_profiles(conn: sqlite3.Connection, movie_profile_path: Path) -> int:
    rows = []
    movie_rows = []
    for row in open_csv(movie_profile_path):
        movie_id = to_int(row.get("movieId"))
        if movie_id is None:
            continue
        title = none_if_blank(row.get("title")) or f"Movie {movie_id}"
        clean_title = none_if_blank(row.get("clean_title"))
        year = to_int(row.get("year"))
        decade = none_if_blank(row.get("decade"))
        genres = none_if_blank(row.get("genres"))
        genre_count = to_int(row.get("genre_count"))
        avg_rating = to_float(row.get("movie_avg_rating"))
        rating_count = to_int(row.get("movie_rating_count"))
        rating_std = to_float(row.get("movie_rating_std"))
        popularity = to_float(row.get("movie_popularity"))
        tag_text = none_if_blank(row.get("tag_text"))
        tag_count = to_int(row.get("tag_count"))

        movie_rows.append(
            (
                movie_id,
                title,
                clean_title,
                year,
                decade,
                genres,
                genre_count,
                avg_rating,
                rating_count,
                rating_std,
                popularity,
                tag_text,
                tag_count,
            )
        )
        rows.append(
            (
                movie_id,
                title,
                clean_title,
                year,
                decade,
                genres,
                genre_count,
                avg_rating,
                rating_count,
                rating_std,
                popularity,
                tag_text,
                tag_count,
                str(movie_profile_path.relative_to(PROJECT_ROOT)),
            )
        )

    conn.executemany(
        """
        INSERT INTO movies (
            movie_id, title, clean_title, year, decade, genres, genre_count,
            avg_rating, rating_count, rating_std, popularity, tag_text, tag_count
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(movie_id) DO UPDATE SET
            title = COALESCE(excluded.title, movies.title),
            clean_title = excluded.clean_title,
            year = excluded.year,
            decade = excluded.decade,
            genres = COALESCE(excluded.genres, movies.genres),
            genre_count = excluded.genre_count,
            avg_rating = excluded.avg_rating,
            rating_count = excluded.rating_count,
            rating_std = excluded.rating_std,
            popularity = excluded.popularity,
            tag_text = excluded.tag_text,
            tag_count = excluded.tag_count,
            updated_at = CURRENT_TIMESTAMP
        """,
        movie_rows,
    )
    conn.executemany(
        """
        INSERT INTO movie_profiles (
            movie_id, title, clean_title, year, decade, genres, genre_count,
            avg_rating, rating_count, rating_std, popularity, tag_text, tag_count,
            feature_source
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(movie_id) DO UPDATE SET
            title = excluded.title,
            clean_title = excluded.clean_title,
            year = excluded.year,
            decade = excluded.decade,
            genres = excluded.genres,
            genre_count = excluded.genre_count,
            avg_rating = excluded.avg_rating,
            rating_count = excluded.rating_count,
            rating_std = excluded.rating_std,
            popularity = excluded.popularity,
            tag_text = excluded.tag_text,
            tag_count = excluded.tag_count,
            feature_source = excluded.feature_source,
            updated_at = CURRENT_TIMESTAMP
        """,
        rows,
    )
    logger.info("Imported movie profiles: %s", len(rows))
    return len(rows)


def import_recommendations(conn: sqlite3.Connection, ranked_path: Path, run_id: str) -> int:
    source_file = str(ranked_path.relative_to(PROJECT_ROOT))
    rows = []
    log_rows = []
    user_rows = set()
    for row in open_csv(ranked_path):
        user_id = to_int(row.get("userId"))
        movie_id = to_int(row.get("movieId"))
        if user_id is None or movie_id is None:
            continue
        user_rows.add((user_id,))
        rows.append(
            (
                run_id,
                user_id,
                movie_id,
                to_int(row.get("rank_position")),
                to_float(row.get("rank_score")),
                to_float(row.get("mmr_score")),
                to_int(row.get("label")),
                to_float(row.get("als_score")),
                to_float(row.get("itemcf_score")),
                to_float(row.get("merged_recall_score")),
                to_float(row.get("recall_source_count")),
                to_float(row.get("genre_match_score")),
                to_float(row.get("movie_avg_rating")),
                to_int(row.get("movie_rating_count")),
                to_float(row.get("movie_popularity")),
                source_file,
            )
        )
        log_rows.append(
            (
                user_id,
                movie_id,
                to_int(row.get("rank_position")),
                to_float(row.get("mmr_score")) or to_float(row.get("rank_score")),
                "XGBoost_MMR_Top10",
                run_id,
            )
        )

    conn.execute("DELETE FROM recommendations WHERE run_id = ?", (run_id,))
    conn.execute(
        "DELETE FROM recommendation_logs WHERE run_id = ? AND event_type = 'offline_import'",
        (run_id,),
    )
    conn.executemany(
        """
        INSERT INTO users (user_id)
        VALUES (?)
        ON CONFLICT(user_id) DO NOTHING
        """,
        user_rows,
    )
    conn.executemany(
        """
        INSERT INTO recommendations (
            run_id, user_id, movie_id, rank_position, rank_score, mmr_score, label,
            als_score, itemcf_score, merged_recall_score, recall_source_count,
            genre_match_score, movie_avg_rating, movie_rating_count,
            movie_popularity, source_file
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.executemany(
        """
        INSERT INTO recommendation_logs (
            user_id, movie_id, rank_position, score, model_name, run_id, event_type
        )
        VALUES (?, ?, ?, ?, ?, ?, 'offline_import')
        """,
        log_rows,
    )
    logger.info("Imported recommendations: %s", len(rows))
    return len(rows)


def import_model_metrics(conn: sqlite3.Connection, metrics_path: Path, run_id: str) -> int:
    source_file = str(metrics_path.relative_to(PROJECT_ROOT))
    rows = []
    for row in open_csv(metrics_path):
        rows.append(
            (
                run_id,
                none_if_blank(row.get("model_name")),
                to_int(row.get("k")),
                to_float(row.get("precision")),
                to_float(row.get("recall")),
                to_float(row.get("ndcg")),
                to_float(row.get("hit_rate")),
                to_float(row.get("coverage")),
                to_float(row.get("diversity")),
                to_int(row.get("evaluated_users")),
                to_int(row.get("recommended_items")),
                source_file,
            )
        )

    conn.executemany(
        """
        INSERT INTO model_metrics (
            run_id, model_name, k, precision, recall, ndcg, hit_rate, coverage,
            diversity, evaluated_users, recommended_items, source_file
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(run_id, model_name, k) DO UPDATE SET
            precision = excluded.precision,
            recall = excluded.recall,
            ndcg = excluded.ndcg,
            hit_rate = excluded.hit_rate,
            coverage = excluded.coverage,
            diversity = excluded.diversity,
            evaluated_users = excluded.evaluated_users,
            recommended_items = excluded.recommended_items,
            source_file = excluded.source_file,
            created_at = CURRENT_TIMESTAMP
        """,
        rows,
    )
    logger.info("Imported model metrics: %s", len(rows))
    return len(rows)


def import_ablation_metrics(conn: sqlite3.Connection, ablation_path: Path, run_id: str) -> int:
    source_file = str(ablation_path.relative_to(PROJECT_ROOT))
    rows = []
    for row in open_csv(ablation_path):
        rows.append(
            (
                run_id,
                none_if_blank(row.get("variant")),
                none_if_blank(row.get("removed_module")),
                to_int(row.get("k")),
                to_float(row.get("precision")),
                to_float(row.get("recall")),
                to_float(row.get("ndcg")),
                to_float(row.get("hit_rate")),
                to_float(row.get("coverage")),
                to_float(row.get("diversity")),
                none_if_blank(row.get("main_observation")),
                source_file,
            )
        )

    conn.executemany(
        """
        INSERT INTO ablation_metrics (
            run_id, variant, removed_module, k, precision, recall, ndcg, hit_rate,
            coverage, diversity, main_observation, source_file
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(run_id, variant, k) DO UPDATE SET
            removed_module = excluded.removed_module,
            precision = excluded.precision,
            recall = excluded.recall,
            ndcg = excluded.ndcg,
            hit_rate = excluded.hit_rate,
            coverage = excluded.coverage,
            diversity = excluded.diversity,
            main_observation = excluded.main_observation,
            source_file = excluded.source_file,
            created_at = CURRENT_TIMESTAMP
        """,
        rows,
    )
    logger.info("Imported ablation metrics: %s", len(rows))
    return len(rows)


def summarize_tables(conn: sqlite3.Connection) -> dict[str, int]:
    tables = [
        "movies",
        "users",
        "ratings",
        "user_profiles",
        "movie_profiles",
        "recommendations",
        "recommendation_logs",
        "model_metrics",
        "ablation_metrics",
        "feedback_logs",
    ]
    return {
        table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in tables
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite database path.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA_PATH), help="Schema SQL path.")
    parser.add_argument("--run-id", default="offline_xgboost_mmr_top10", help="Offline import run id.")
    parser.add_argument("--movies", default=str(PROJECT_ROOT / "movies.csv"))
    parser.add_argument("--ratings", default=str(PROJECT_ROOT / "ratings.csv"))
    parser.add_argument("--user-profile", default=str(PROJECT_ROOT / "data" / "features" / "user_profile.csv"))
    parser.add_argument("--movie-profile", default=str(PROJECT_ROOT / "data" / "features" / "movie_profile.csv"))
    parser.add_argument("--ranked", default=str(PROJECT_ROOT / "data" / "rank" / "ranked_top10_mmr.csv"))
    parser.add_argument("--offline-metrics", default=str(PROJECT_ROOT / "data" / "eval" / "offline_metrics.csv"))
    parser.add_argument("--ablation-metrics", default=str(PROJECT_ROOT / "data" / "eval" / "ablation_metrics.csv"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    db_path = Path(args.db).resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    paths = {
        "schema": require_file(Path(args.schema).resolve()),
        "movies": require_file(Path(args.movies).resolve()),
        "ratings": require_file(Path(args.ratings).resolve()),
        "user_profile": require_file(Path(args.user_profile).resolve()),
        "movie_profile": require_file(Path(args.movie_profile).resolve()),
        "ranked": require_file(Path(args.ranked).resolve()),
        "offline_metrics": require_file(Path(args.offline_metrics).resolve()),
        "ablation_metrics": require_file(Path(args.ablation_metrics).resolve()),
    }

    logger.info("Opening database: %s", db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        execute_schema(conn, paths["schema"])
        import_movies(conn, paths["movies"])
        import_movie_profiles(conn, paths["movie_profile"])
        import_ratings(conn, paths["ratings"])
        import_user_profiles(conn, paths["user_profile"])
        import_recommendations(conn, paths["ranked"], args.run_id)
        import_model_metrics(conn, paths["offline_metrics"], args.run_id)
        import_ablation_metrics(conn, paths["ablation_metrics"], args.run_id)
        conn.commit()

        logger.info("Table counts:")
        for table, count in summarize_tables(conn).items():
            logger.info(" - %s: %s", table, count)


if __name__ == "__main__":
    main()
