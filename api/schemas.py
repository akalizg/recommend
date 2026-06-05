"""
Pydantic schemas for API request/response models.
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class MovieItem(BaseModel):
    movie_id: int
    title: str
    score: float


class RecommendationResponse(BaseModel):
    user_id: int
    recommendations: List[MovieItem]
    cached: bool = False
    took_ms: float = 0.0


class MovieDetail(BaseModel):
    movie_id: int
    title: str
    genres: str
    avg_rating: float
    rating_count: int
    popularity_score: float
    year: Optional[int] = None


class PopularResponse(BaseModel):
    popular: List[MovieDetail]
    took_ms: float = 0.0


class UserProfileResponse(BaseModel):
    user_id: int
    avg_rating: float
    rating_count: int
    rating_std: float
    activity_level: str
    top_genres: List[dict]
    top_rated_movies: List[dict]
    recent_ratings: List[dict]


class SearchRequest(BaseModel):
    query: str
    limit: int = Field(default=20, ge=1, le=100)


class SearchResponse(BaseModel):
    results: List[MovieDetail]
    total: int


class RebuildResponse(BaseModel):
    status: str
    message: str
    took_seconds: float


class HealthResponse(BaseModel):
    status: str
    version: str
    redis: bool
    faiss_index_size: int


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
