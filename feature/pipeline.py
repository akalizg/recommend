"""
Feature engineering pipeline for MovieLens data.
Handles data loading, cleaning, feature construction, and user/item profiling.
"""
import logging
import pickle
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from sklearn.preprocessing import LabelEncoder

from app.config import get_settings

logger = logging.getLogger(__name__)


class FeaturePipeline:
    """
    Complete feature engineering pipeline.

    Loads MovieLens CSV files, cleans data, builds user/movie profiles,
    constructs rating matrix, and computes feature vectors.
    """

    def __init__(self, data_dir: Optional[str] = None):
        settings = get_settings()
        self.data_dir = Path(data_dir) if data_dir else Path(settings.movielens_data_dir)
        self.settings = settings

        # DataFrames
        self.ratings: Optional[pd.DataFrame] = None
        self.movies: Optional[pd.DataFrame] = None
        self.tags: Optional[pd.DataFrame] = None
        self.links: Optional[pd.DataFrame] = None

        # Processed data
        self.rating_matrix: Optional[csr_matrix] = None
        self.user_ids: Optional[np.ndarray] = None
        self.movie_ids: Optional[np.ndarray] = None
        self.user_id_to_idx: dict = {}
        self.movie_id_to_idx: dict = {}
        self.idx_to_movie_id: dict = {}

        # Feature stores
        self.user_features: Optional[pd.DataFrame] = None
        self.movie_features: Optional[pd.DataFrame] = None
        self.genre_encoder: Optional[LabelEncoder] = None
        self.all_genres: list = []

    def load_data(self) -> "FeaturePipeline":
        """Load all four CSV files from the MovieLens dataset."""
        logger.info(f"Loading data from {self.data_dir}")

        self.ratings = pd.read_csv(self.data_dir / "ratings.csv")
        self.movies = pd.read_csv(self.data_dir / "movies.csv")
        self.tags = pd.read_csv(self.data_dir / "tags.csv")
        self.links = pd.read_csv(self.data_dir / "links.csv")

        logger.info(
            f"Loaded: ratings={len(self.ratings)}, movies={len(self.movies)}, "
            f"tags={len(self.tags)}, links={len(self.links)}"
        )
        return self

    def clean_data(self) -> "FeaturePipeline":
        """Clean data: drop duplicates, handle missing values, validate integrity."""
        logger.info("Cleaning data")

        self.ratings = self.ratings.drop_duplicates(subset=["userId", "movieId"])
        self.movies = self.movies.drop_duplicates(subset=["movieId"])
        self.tags = self.tags.drop_duplicates()

        # Drop rows with missing critical fields
        self.ratings = self.ratings.dropna(subset=["userId", "movieId", "rating"])
        self.movies = self.movies.dropna(subset=["movieId", "title"])

        # Ensure movieId consistency: only keep ratings for movies that exist in movies.csv
        valid_movie_ids = set(self.movies["movieId"].unique())
        self.ratings = self.ratings[self.ratings["movieId"].isin(valid_movie_ids)]

        logger.info(f"After cleaning: ratings={len(self.ratings)}, movies={len(self.movies)}")
        return self

    def build_rating_matrix(self) -> "FeaturePipeline":
        """Build sparse user-item rating matrix."""
        logger.info("Building rating matrix")

        self.user_ids = self.ratings["userId"].unique()
        self.movie_ids = self.ratings["movieId"].unique()

        self.user_id_to_idx = {uid: i for i, uid in enumerate(self.user_ids)}
        self.movie_id_to_idx = {mid: i for i, mid in enumerate(self.movie_ids)}
        self.idx_to_movie_id = {i: mid for mid, i in self.movie_id_to_idx.items()}

        rows = self.ratings["userId"].map(self.user_id_to_idx).values
        cols = self.ratings["movieId"].map(self.movie_id_to_idx).values
        data = self.ratings["rating"].values.astype(np.float32)

        self.rating_matrix = csr_matrix(
            (data, (rows, cols)),
            shape=(len(self.user_ids), len(self.movie_ids)),
            dtype=np.float32,
        )

        logger.info(
            f"Rating matrix shape: {self.rating_matrix.shape}, "
            f"sparsity: {self.rating_matrix.nnz / (self.rating_matrix.shape[0] * self.rating_matrix.shape[1]):.4f}"
        )
        return self

    def parse_genres(self) -> list:
        """Extract all unique genres from movies."""
        if self.all_genres:
            return self.all_genres
        genre_set = set()
        for g in self.movies["genres"].dropna():
            for genre in g.split("|"):
                if genre != "(no genres listed)":
                    genre_set.add(genre)
        self.all_genres = sorted(genre_set)
        return self.all_genres

    def build_movie_features(self) -> "FeaturePipeline":
        """Build movie feature vectors: genres (multi-hot), year, rating stats."""
        logger.info("Building movie features")

        genres = self.parse_genres()
        movie_stats = self.ratings.groupby("movieId").agg(
            avg_rating=("rating", "mean"),
            rating_count=("rating", "count"),
            rating_std=("rating", "std"),
        ).reset_index()
        movie_stats["rating_std"] = movie_stats["rating_std"].fillna(0)

        self.movies = self.movies.merge(movie_stats, on="movieId", how="left")
        self.movies["avg_rating"] = self.movies["avg_rating"].fillna(self.movies["avg_rating"].mean())
        self.movies["rating_count"] = self.movies["rating_count"].fillna(0).astype(int)
        self.movies["rating_std"] = self.movies["rating_std"].fillna(0)

        # Popularity score: Bayesian average
        C = self.ratings["rating"].mean()
        m = self.movies["rating_count"].quantile(0.9)
        self.movies["popularity_score"] = (
            (self.movies["rating_count"] / (self.movies["rating_count"] + m)) * self.movies["avg_rating"]
            + (m / (self.movies["rating_count"] + m)) * C
        )

        # Extract year from title
        self.movies["year"] = self.movies["title"].str.extract(r"\((\d{4})\)").astype(float)
        self.movies["year"] = self.movies["year"].fillna(self.movies["year"].median())

        # Multi-hot genre encoding
        genre_matrix = np.zeros((len(self.movies), len(genres)), dtype=np.float32)
        for i, g_str in enumerate(self.movies["genres"].fillna("")):
            for g in g_str.split("|"):
                if g in genres:
                    genre_matrix[i, genres.index(g)] = 1.0
        self.movies["genre_vector"] = list(genre_matrix)

        self.movie_features = self.movies.copy()
        logger.info(f"Movie features built: {len(self.movie_features)} movies, {len(genres)} genres")
        return self

    def build_user_features(self) -> "FeaturePipeline":
        """Build user feature vectors: rating behavior, genre preferences, activity."""
        logger.info("Building user features")

        user_stats = self.ratings.groupby("userId").agg(
            avg_rating=("rating", "mean"),
            rating_count=("rating", "count"),
            rating_std=("rating", "std"),
            avg_timestamp=("timestamp", "mean"),
        ).reset_index()
        user_stats["rating_std"] = user_stats["rating_std"].fillna(0)

        user_stats["activity_level"] = pd.cut(
            user_stats["rating_count"],
            bins=[0, 20, 50, 100, 500, 10000],
            labels=["cold", "low", "medium", "high", "power"],
        )

        # Build user genre preference vectors
        genres = self.parse_genres()
        movie_id_to_genre_vec = {}
        for _, row in self.movies.iterrows():
            vec = np.zeros(len(genres), dtype=np.float32)
            for g in str(row["genres"]).split("|"):
                if g in genres:
                    vec[genres.index(g)] = 1.0
            movie_id_to_genre_vec[row["movieId"]] = vec

        user_genre_scores = {}
        for uid in self.user_ids:
            user_ratings = self.ratings[self.ratings["userId"] == uid]
            weighted = np.zeros(len(genres), dtype=np.float32)
            total_weight = 0.0
            for _, r in user_ratings.iterrows():
                mid = r["movieId"]
                if mid in movie_id_to_genre_vec:
                    weighted += movie_id_to_genre_vec[mid] * r["rating"]
                    total_weight += r["rating"]
            if total_weight > 0:
                user_genre_scores[uid] = (weighted / total_weight).tolist()
            else:
                user_genre_scores[uid] = np.zeros(len(genres), dtype=np.float32).tolist()

        self.user_features = user_stats.copy()
        self.user_features["genre_preference"] = self.user_features["userId"].map(user_genre_scores)

        logger.info(f"User features built: {len(self.user_features)} users")
        return self

    def run(self) -> "FeaturePipeline":
        """Execute the full feature engineering pipeline."""
        logger.info("=== Starting feature pipeline ===")
        self.load_data()
        self.clean_data()
        self.build_rating_matrix()
        self.build_movie_features()
        self.build_user_features()
        logger.info("=== Feature pipeline complete ===")
        return self

    def save(self, path: Optional[str] = None) -> None:
        """Persist the pipeline state to disk."""
        path = Path(path) if path else Path(self.settings.feature_cache_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self, f)
        logger.info(f"Pipeline saved to {path}")

    @classmethod
    def load(cls, path: Optional[str] = None) -> "FeaturePipeline":
        """Load a previously saved pipeline state."""
        settings = get_settings()
        path = Path(path) if path else Path(settings.feature_cache_path)
        with open(path, "rb") as f:
            obj = pickle.load(f)
        logger.info(f"Pipeline loaded from {path}")
        return obj

    def get_user_history(self, user_id: int) -> pd.DataFrame:
        """Get rating history for a specific user."""
        return self.ratings[self.ratings["userId"] == user_id]

    def get_movie_info(self, movie_id: int) -> dict:
        """Get detailed info for a specific movie."""
        movie = self.movies[self.movies["movieId"] == movie_id]
        if movie.empty:
            return {}
        row = movie.iloc[0]
        return {
            "movie_id": int(row["movieId"]),
            "title": str(row["title"]),
            "genres": str(row["genres"]),
            "avg_rating": float(row.get("avg_rating", 0)),
            "rating_count": int(row.get("rating_count", 0)),
            "popularity_score": float(row.get("popularity_score", 0)),
            "year": float(row.get("year", 0)) if pd.notna(row.get("year")) else None,
        }

    def get_popular_movies(self, n: int = 50) -> list:
        """Return top-N most popular movies by popularity score."""
        df = self.movie_features.sort_values("popularity_score", ascending=False).head(n)
        return [self.get_movie_info(int(row["movieId"])) for _, row in df.iterrows()]
