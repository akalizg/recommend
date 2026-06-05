"""
Ranking service: re-ranks recall candidates using a trained XGBoost model.

Flow:
1. Accept candidate list from RecallService
2. Build feature vectors for each (user, candidate_movie) pair
3. Score with XGBoost model
4. Sort by score and return final Top-K
"""
import logging
from typing import List, Optional

import numpy as np
import pandas as pd
import xgboost as xgb

from app.config import get_settings

logger = logging.getLogger(__name__)


class RankingService:
    """
    Ranking layer: XGBoost-based reranking of recall candidates.

    Features (same as training):
    - user_avg_rating, user_rating_count, user_rating_std
    - movie_avg_rating, movie_rating_count, movie_popularity
    - embedding_similarity (user-movie cosine)
    - genre_match_score
    - movie_year
    """

    def __init__(self, pipeline, embedding_service, model: Optional[xgb.XGBRegressor] = None):
        self.pipeline = pipeline
        self.embedding = embedding_service
        self.settings = get_settings()

        if model is not None:
            self.model = model
        else:
            self.model = self._load_model()

        self.user_stats = self.pipeline.user_features.set_index("userId")
        self.movie_stats = self.pipeline.movie_features.set_index("movieId")

    def _load_model(self) -> xgb.XGBRegressor:
        """Load XGBoost model from disk."""
        from rank.train import load_rank_model
        return load_rank_model()

    def rank(self, user_id: int, candidates: List[dict], top_k: Optional[int] = None) -> List[dict]:
        """
        Re-rank candidates for a user.

        Args:
            user_id: User ID.
            candidates: List of {"movie_id": int, "score": float} from recall.
            top_k: Number of final recommendations.

        Returns:
            List of {"movie_id": int, "title": str, "score": float} sorted by score descending.
        """
        top_k = top_k or self.settings.final_top_k

        if not candidates:
            return []

        user_vec = self.embedding.get_user_embedding(user_id)
        genre_list = self.pipeline.parse_genres()
        user_genre_pref = self._get_user_genre_pref(user_id)

        features_list = []
        valid_candidates = []

        for c in candidates:
            mid = c["movie_id"]
            feats = self._build_features(
                user_id, mid, user_vec, user_genre_pref, genre_list
            )
            if feats is not None:
                features_list.append(feats)
                valid_candidates.append(c)

        if not features_list:
            return []

        X = np.array(features_list, dtype=np.float32)
        scores = self.model.predict(X)

        # Combine with candidate info
        results = []
        for i, c in enumerate(valid_candidates):
            results.append({
                "movie_id": c["movie_id"],
                "score": round(float(scores[i]), 4),
                "recall_score": c.get("score", 0),
            })

        # Sort by predicted score descending
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def _get_user_genre_pref(self, user_id: int) -> Optional[np.ndarray]:
        if user_id not in self.user_stats.index:
            return None
        prefs = self.user_stats.loc[user_id].get("genre_preference")
        if prefs is None:
            return None
        return np.array(prefs)

    def _build_features(
        self,
        user_id: int,
        movie_id: int,
        user_vec: Optional[np.ndarray],
        user_genre_pref: Optional[np.ndarray],
        genre_list: list,
    ) -> Optional[list]:
        if user_id not in self.user_stats.index or movie_id not in self.movie_stats.index:
            return None

        u = self.user_stats.loc[user_id]
        m = self.movie_stats.loc[movie_id]

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
        movie_vec = self.embedding.get_item_embedding(movie_id)
        if user_vec is not None and movie_vec is not None:
            sim = float(np.dot(user_vec, movie_vec))
        else:
            sim = 0.0

        # Genre match
        movie_genre_vec = m.get("genre_vector")
        if user_genre_pref is not None and movie_genre_vec is not None:
            genre_match = float(np.dot(user_genre_pref, np.array(movie_genre_vec)))
        else:
            genre_match = 0.0

        return [
            user_avg_rating, user_rating_count, user_rating_std,
            movie_avg_rating, movie_rating_count, movie_popularity,
            sim, genre_match, movie_year,
        ]
