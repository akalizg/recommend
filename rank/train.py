"""
Training script for the XGBoost ranking model.

Constructs training features from user-item pairs and trains an XGBoost
ranker to predict rating/relevance scores.

Features used:
- User avg rating, rating count, rating std
- Movie avg rating, rating count, popularity score
- User-movie embedding cosine similarity
- Genre match score between user preferences and movie genres
- Movie year
"""
import logging
import pickle
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error

from app.config import get_settings

logger = logging.getLogger(__name__)


class RankingDataBuilder:
    """
    Builds training data for the ranking model.
    """

    def __init__(self, pipeline, embedding_service):
        self.pipeline = pipeline
        self.embedding = embedding_service
        self.settings = get_settings()

    def build_training_data(self, sample_frac: float = 1.0) -> tuple:
        """
        Build feature matrix X and target y from all ratings.

        Returns:
            X (np.ndarray), y (np.ndarray), feature_names (list)
        """
        logger.info("Building ranking training data...")
        ratings = self.pipeline.ratings.copy()

        if sample_frac < 1.0:
            ratings = ratings.sample(frac=sample_frac, random_state=42)

        features_list = []
        targets = []

        user_stats = self.pipeline.user_features.set_index("userId")
        movie_stats = self.pipeline.movie_features.set_index("movieId")

        genre_list = self.pipeline.parse_genres()

        for _, row in ratings.iterrows():
            uid = row["userId"]
            mid = row["movieId"]
            rating = row["rating"]

            feats = self._build_pair_features(uid, mid, user_stats, movie_stats, genre_list)
            if feats is not None:
                features_list.append(feats)
                targets.append(rating)

        X = np.array(features_list, dtype=np.float32)
        y = np.array(targets, dtype=np.float32)

        self.feature_names = [
            "user_avg_rating", "user_rating_count", "user_rating_std",
            "movie_avg_rating", "movie_rating_count", "movie_popularity",
            "embedding_similarity", "genre_match_score", "movie_year",
        ]

        logger.info(f"Training data: X={X.shape}, y={y.shape}")
        return X, y, self.feature_names

    def _build_pair_features(self, uid, mid, user_stats, movie_stats, genre_list):
        if uid not in user_stats.index or mid not in movie_stats.index:
            return None

        u = user_stats.loc[uid]
        m = movie_stats.loc[mid]

        # User features
        user_avg_rating = float(u["avg_rating"])
        user_rating_count = float(u["rating_count"])
        user_rating_std = float(u.get("rating_std", 0)) if pd.notna(u.get("rating_std", 0)) else 0.0

        # Movie features
        movie_avg_rating = float(m["avg_rating"]) if pd.notna(m.get("avg_rating")) else 0.0
        movie_rating_count = float(m["rating_count"]) if pd.notna(m.get("rating_count")) else 0.0
        movie_popularity = float(m["popularity_score"]) if pd.notna(m.get("popularity_score")) else 0.0
        movie_year = float(m["year"]) if pd.notna(m.get("year")) else 1990.0

        # Embedding similarity
        user_vec = self.embedding.get_user_embedding(uid)
        movie_vec = self.embedding.get_item_embedding(mid)
        if user_vec is not None and movie_vec is not None:
            sim = float(np.dot(user_vec, movie_vec))
        else:
            sim = 0.0

        # Genre match
        user_genre = u.get("genre_preference")
        movie_genre_vec = m.get("genre_vector")
        if user_genre is not None and movie_genre_vec is not None:
            genre_match = float(np.dot(np.array(user_genre), np.array(movie_genre_vec)))
        else:
            genre_match = 0.0

        return [
            user_avg_rating, user_rating_count, user_rating_std,
            movie_avg_rating, movie_rating_count, movie_popularity,
            sim, genre_match, movie_year,
        ]


def train_rank_model(
    pipeline,
    embedding_service,
    output_path: Optional[str] = None,
) -> xgb.XGBRegressor:
    """
    Train XGBoost ranking model.

    Args:
        pipeline: FeaturePipeline instance.
        embedding_service: EmbeddingService instance.
        output_path: Path to save the trained model.

    Returns:
        Trained XGBRegressor model.
    """
    settings = get_settings()
    output_path = output_path or settings.rank_model_path

    builder = RankingDataBuilder(pipeline, embedding_service)
    X, y, feature_names = builder.build_training_data(sample_frac=1.0)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    logger.info(f"Training XGBoost ranker: train={X_train.shape}, test={X_test.shape}")

    model = xgb.XGBRegressor(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=0.1,
        reg_lambda=1.0,
        random_state=42,
        n_jobs=-1,
        verbosity=1,
    )

    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=False,
    )

    y_pred = model.predict(X_test)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    mae = mean_absolute_error(y_test, y_pred)
    logger.info(f"Rank model trained: RMSE={rmse:.4f}, MAE={mae:.4f}")

    # Save model
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    model.save_model(output_path)
    logger.info(f"Rank model saved to {output_path}")

    # Save feature builder metadata
    meta_path = output_path + ".meta"
    with open(meta_path, "wb") as f:
        pickle.dump({"feature_names": feature_names}, f)

    return model


def load_rank_model(path: Optional[str] = None) -> xgb.XGBRegressor:
    """Load a trained XGBoost ranking model."""
    settings = get_settings()
    path = path or settings.rank_model_path

    model = xgb.XGBRegressor()
    model.load_model(path)
    logger.info(f"Rank model loaded from {path}")
    return model
