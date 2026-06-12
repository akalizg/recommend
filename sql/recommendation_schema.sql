-- MovieRec offline recommendation database schema.
-- SQLite-compatible DDL. It stores offline profiles, recommendation results,
-- evaluation metrics, ablation experiments, and future online feedback logs.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS movies (
    movie_id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    clean_title TEXT,
    year INTEGER,
    decade TEXT,
    genres TEXT,
    genre_count INTEGER,
    avg_rating REAL,
    rating_count INTEGER,
    rating_std REAL,
    popularity REAL,
    tag_text TEXT,
    tag_count INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    rating_count INTEGER,
    avg_rating REAL,
    active_level TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ratings (
    user_id INTEGER NOT NULL,
    movie_id INTEGER NOT NULL,
    rating REAL NOT NULL,
    rating_timestamp INTEGER,
    rated_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, movie_id, rating_timestamp),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (movie_id) REFERENCES movies(movie_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS user_profiles (
    user_id INTEGER PRIMARY KEY,
    rating_count INTEGER,
    avg_rating REAL,
    rating_std REAL,
    min_rating REAL,
    max_rating REAL,
    favorite_genres TEXT,
    favorite_decades TEXT,
    active_level TEXT,
    high_rating_movie_ids TEXT,
    recent_movie_ids TEXT,
    feature_source TEXT NOT NULL DEFAULT 'data/features/user_profile.csv',
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS movie_profiles (
    movie_id INTEGER PRIMARY KEY,
    title TEXT,
    clean_title TEXT,
    year INTEGER,
    decade TEXT,
    genres TEXT,
    genre_count INTEGER,
    avg_rating REAL,
    rating_count INTEGER,
    rating_std REAL,
    popularity REAL,
    tag_text TEXT,
    tag_count INTEGER,
    feature_source TEXT NOT NULL DEFAULT 'data/features/movie_profile.csv',
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (movie_id) REFERENCES movies(movie_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS recommendations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    movie_id INTEGER NOT NULL,
    rank_position INTEGER NOT NULL,
    rank_score REAL,
    mmr_score REAL,
    label INTEGER,
    als_score REAL,
    itemcf_score REAL,
    merged_recall_score REAL,
    recall_source_count REAL,
    genre_match_score REAL,
    movie_avg_rating REAL,
    movie_rating_count INTEGER,
    movie_popularity REAL,
    source_file TEXT NOT NULL,
    generated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (movie_id) REFERENCES movies(movie_id) ON DELETE CASCADE,
    UNIQUE (run_id, user_id, movie_id),
    UNIQUE (run_id, user_id, rank_position)
);

CREATE TABLE IF NOT EXISTS recommendation_logs (
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
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL,
    FOREIGN KEY (movie_id) REFERENCES movies(movie_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS model_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    model_name TEXT NOT NULL,
    k INTEGER NOT NULL,
    precision REAL,
    recall REAL,
    ndcg REAL,
    hit_rate REAL,
    coverage REAL,
    diversity REAL,
    evaluated_users INTEGER,
    recommended_items INTEGER,
    source_file TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (run_id, model_name, k)
);

CREATE TABLE IF NOT EXISTS ablation_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    variant TEXT NOT NULL,
    removed_module TEXT,
    k INTEGER NOT NULL,
    precision REAL,
    recall REAL,
    ndcg REAL,
    hit_rate REAL,
    coverage REAL,
    diversity REAL,
    main_observation TEXT,
    source_file TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (run_id, variant, k)
);

CREATE TABLE IF NOT EXISTS feedback_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    movie_id INTEGER NOT NULL,
    feedback_type TEXT NOT NULL,
    feedback_value REAL,
    request_id TEXT,
    run_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (movie_id) REFERENCES movies(movie_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_ratings_movie_id ON ratings(movie_id);
CREATE INDEX IF NOT EXISTS idx_ratings_user_id ON ratings(user_id);
CREATE INDEX IF NOT EXISTS idx_recommendations_user_rank ON recommendations(run_id, user_id, rank_position);
CREATE INDEX IF NOT EXISTS idx_recommendations_movie_id ON recommendations(movie_id);
CREATE INDEX IF NOT EXISTS idx_model_metrics_model_k ON model_metrics(model_name, k);
CREATE INDEX IF NOT EXISTS idx_ablation_metrics_variant_k ON ablation_metrics(variant, k);
CREATE INDEX IF NOT EXISTS idx_feedback_logs_user_time ON feedback_logs(user_id, created_at);
