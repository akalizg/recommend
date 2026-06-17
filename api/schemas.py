"""
Pydantic schemas for API request/response models.
"""
from typing import Any, List, Optional
from pydantic import BaseModel, Field


class MovieItem(BaseModel):
    movie_id: int
    title: str
    score: float
    genres: str = ""
    avg_rating: Optional[float] = None
    rating_count: Optional[int] = None
    review_count: Optional[int] = None
    final_reason: str = ""
    reason_source: str = ""
    image_url: str = ""
    ready_in_display: str = ""
    recipe_yield_raw: str = ""
    author_name: str = ""
    poster_url: str = ""
    backdrop_url: str = ""
    overview: str = ""
    release_date: str = ""
    runtime: Optional[int] = None
    vote_average: Optional[float] = None
    popularity: Optional[float] = None
    tmdb_id: Optional[int] = None
    imdb_id: str = ""


class RecommendationResponse(BaseModel):
    user_id: int
    recommendations: List[MovieItem]
    cached: bool = False
    took_ms: float = 0.0


class OfflineRecommendationItem(BaseModel):
    user_id: int
    movie_id: int
    rank_position: Optional[int] = None
    rank_score: Optional[float] = None
    mmr_score: Optional[float] = None
    movie_title: str = ""
    movie_genres: str = ""
    favorite_genres: str = ""
    final_reason: str = ""
    reason_source: str = ""
    reason_evidence: Optional[Any] = None


class OfflineRecommendationsResponse(BaseModel):
    user_id: int
    recommendations: List[OfflineRecommendationItem]
    total: int
    source: str


class OfflineMetricsResponse(BaseModel):
    metrics: List[dict]
    summary: Optional[dict] = None
    source: str
    summary_source: Optional[str] = None


class OfflineAblationResponse(BaseModel):
    ablation: List[dict]
    source: str


class OfflineUserProfileResponse(BaseModel):
    user_id: int
    profile: dict
    source: str


class OfflineMovieProfileResponse(BaseModel):
    movie_id: int
    profile: dict
    source: str


class OfflinePopularRecipesResponse(BaseModel):
    popular: List[dict]
    total: int
    source: str


class SimilarRecipesResponse(BaseModel):
    movie_id: int
    similar: List[MovieItem]
    total: int
    source: str


class ColdStartRequest(BaseModel):
    preferred_tags: List[str] = Field(default_factory=list)
    preferred_ingredients: List[str] = Field(default_factory=list)
    disliked_ingredients: List[str] = Field(default_factory=list)
    ingredients: List[str] = Field(default_factory=list)
    dietary_goals: List[str] = Field(default_factory=list)
    max_minutes: Optional[int] = Field(default=None, ge=1)
    min_rating: Optional[float] = Field(default=None, ge=0, le=5)
    require_image: bool = False
    limit: int = Field(default=20, ge=1, le=100)
    user_id: Optional[int] = Field(default=None, ge=1)
    source: str = Field(default="onboarding")
    scenario: Optional[str] = None


class ColdStartResponse(BaseModel):
    recommendations: List[MovieItem]
    total: int
    source: str
    preference_profile: dict


class ScenarioRecommendRequest(BaseModel):
    scenario: str = Field(default="personalized")
    user_id: Optional[int] = Field(default=None, ge=1)
    preferred_tags: List[str] = Field(default_factory=list)
    ingredients: List[str] = Field(default_factory=list)
    dietary_goals: List[str] = Field(default_factory=list)
    max_minutes: Optional[int] = Field(default=None, ge=1)
    min_rating: Optional[float] = Field(default=None, ge=0, le=5)
    require_image: bool = True
    exploration: float = Field(default=0.5, ge=0, le=1)
    limit: int = Field(default=20, ge=1, le=100)


class ScenarioRecommendResponse(BaseModel):
    scenario: str
    recommendations: List[MovieItem]
    total: int
    source: str
    context: dict = Field(default_factory=dict)


class IngredientItem(BaseModel):
    name: str
    label: str
    count: int


class IngredientSearchResponse(BaseModel):
    ingredients: List[IngredientItem]
    total: int
    source: str
    query: str = ""


class AuthRegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=32)
    password: str = Field(..., min_length=6, max_length=128)
    display_name: Optional[str] = Field(default=None, max_length=64)
    recipe_user_id: Optional[int] = Field(default=1535, ge=1)


class AuthLoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=32)
    password: str = Field(..., min_length=6, max_length=128)


class AuthUserResponse(BaseModel):
    account_id: int
    username: str
    display_name: str = ""
    user_id: int
    recipe_user_id: int
    created_at: str


class FeedbackRequest(BaseModel):
    user_id: int
    movie_id: int
    feedback_type: str
    feedback_value: Optional[float] = None
    request_id: Optional[str] = None
    run_id: Optional[str] = None
    experiment_name: Optional[str] = None
    group_name: Optional[str] = None
    rank_position: Optional[int] = None
    score: Optional[float] = None
    reason: Optional[str] = None


class ExposureRequest(BaseModel):
    user_id: int
    movie_id: int
    request_id: Optional[str] = None
    run_id: Optional[str] = None
    experiment_name: Optional[str] = None
    group_name: Optional[str] = None
    rank_position: Optional[int] = None
    score: Optional[float] = None
    reason: Optional[str] = None
    model_name: str = "recipe_offline"


class FeedbackResponse(BaseModel):
    status: str
    feedback_id: int
    user_id: int
    movie_id: int
    feedback_type: str
    realtime_profile: dict
    kafka_sent: bool = False


class RealtimeProfileResponse(BaseModel):
    user_id: int
    profile: Optional[dict] = None


class ABGroupResponse(BaseModel):
    user_id: int
    experiment_name: str
    group_name: str


class ABMetricsResponse(BaseModel):
    experiment_name: str
    groups: List[dict]


class MovieDetail(BaseModel):
    movie_id: int
    title: str
    genres: str
    avg_rating: float
    rating_count: int
    popularity_score: float
    year: Optional[int] = None
    image_url: str = ""
    description: str = ""
    minutes: Optional[float] = None
    ready_in_display: str = ""
    recipe_yield_raw: str = ""
    serves_best_guess: Optional[float] = None
    author_name: str = ""
    source_url: str = ""
    ingredients_json: Optional[Any] = None
    quantities_json: Optional[Any] = None
    steps_json: Optional[Any] = None
    nutrition_json: Optional[Any] = None
    n_ingredients: Optional[int] = None
    n_steps: Optional[int] = None
    submitted: str = ""
    photo_count: Optional[int] = None
    review_count: Optional[int] = None
    poster_url: str = ""
    backdrop_url: str = ""
    overview: str = ""
    release_date: str = ""
    runtime: Optional[int] = None
    vote_average: Optional[float] = None
    popularity: Optional[float] = None
    tmdb_id: Optional[int] = None
    imdb_id: str = ""


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
