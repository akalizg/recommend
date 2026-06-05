"""
User profile builder: aggregates user behavior into a structured profile
including rating stats, genre affinities, and activity metrics.
"""
import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class UserProfileBuilder:
    """
    Builds structured user profiles from rating history and feature pipeline data.
    """

    def __init__(self, pipeline):
        self.pipeline = pipeline
        self.ratings = pipeline.ratings
        self.movies = pipeline.movies
        self.user_features = pipeline.user_features

    def build_profile(self, user_id: int) -> dict:
        """
        Construct a comprehensive user profile.

        Returns:
            dict with keys: user_id, avg_rating, rating_count, rating_std,
            activity_level, top_genres, genre_preference, rated_movies, recent_ratings
        """
        user_row = self.user_features[self.user_features["userId"] == user_id]

        if user_row.empty:
            return self._empty_profile(user_id)

        row = user_row.iloc[0]
        user_ratings = self.ratings[self.ratings["userId"] == user_id].merge(
            self.movies[["movieId", "title", "genres"]], on="movieId", how="left"
        )

        # Top rated movies
        top_rated = user_ratings.nlargest(10, "rating")[
            ["movieId", "title", "rating", "genres"]
        ].to_dict("records")

        # Recent ratings
        recent = user_ratings.nlargest(10, "timestamp")[
            ["movieId", "title", "rating", "timestamp"]
        ].to_dict("records")

        # Favorite genres
        genre_prefs = row.get("genre_preference")
        if genre_prefs is not None and len(genre_prefs) > 0:
            genres_list = self.pipeline.parse_genres()
            genre_scores = sorted(
                zip(genres_list, genre_prefs), key=lambda x: x[1], reverse=True
            )
            top_genres = [{"genre": g, "score": round(float(s), 4)} for g, s in genre_scores[:10]]
        else:
            top_genres = []

        return {
            "user_id": int(user_id),
            "avg_rating": round(float(row["avg_rating"]), 2),
            "rating_count": int(row["rating_count"]),
            "rating_std": round(float(row.get("rating_std", 0)), 2),
            "activity_level": str(row.get("activity_level", "cold")),
            "top_genres": top_genres,
            "top_rated_movies": top_rated,
            "recent_ratings": recent,
        }

    def _empty_profile(self, user_id: int) -> dict:
        return {
            "user_id": int(user_id),
            "avg_rating": 0.0,
            "rating_count": 0,
            "rating_std": 0.0,
            "activity_level": "cold",
            "top_genres": [],
            "top_rated_movies": [],
            "recent_ratings": [],
        }
