"""
FastAPI route definitions for the recommendation system.
"""
import logging
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends

from api.schemas import (
    RecommendationResponse,
    MovieItem,
    MovieDetail,
    PopularResponse,
    UserProfileResponse,
    SearchResponse,
    RebuildResponse,
    HealthResponse,
    ErrorResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------- Application state dependency ----------

class AppState:
    """Holds references to all service layer components."""
    def __init__(self):
        self.pipeline = None
        self.embedding_service = None
        self.faiss_index = None
        self.recall_service = None
        self.ranking_service = None
        self.cache = None
        self.user_profile_builder = None


_app_state = AppState()


def get_state() -> AppState:
    return _app_state


# ---------- Health ----------

@router.get("/health", response_model=HealthResponse)
async def health(state: AppState = Depends(get_state)):
    from app.config import get_settings
    settings = get_settings()

    redis_ok = False
    faiss_size = 0
    if state.cache:
        redis_ok = state.cache.health_check()
    if state.faiss_index:
        faiss_size = state.faiss_index.ntotal

    return HealthResponse(
        status="ok",
        version=settings.app_version,
        redis=redis_ok,
        faiss_index_size=faiss_size,
    )


# ---------- Recommendation ----------

@router.get("/recommend/{user_id}", response_model=RecommendationResponse)
async def recommend(
    user_id: int,
    top_k: int = Query(default=20, ge=1, le=100, description="Number of recommendations"),
    use_cache: bool = Query(default=True, description="Use Redis cache"),
    state: AppState = Depends(get_state),
):
    """
    Get personalized movie recommendations for a user.

    Flow: Cache Check → Recall (FAISS HNSW) → Rank (XGBoost) → Response
    """
    if state.recall_service is None or state.ranking_service is None:
        raise HTTPException(status_code=503, detail="Services not initialized")

    t0 = time.perf_counter()
    cached = False

    # 1. Check cache
    cache_key = f"rec:user:{user_id}:k:{top_k}"
    if use_cache and state.cache:
        cached_result = state.cache.get_json(cache_key)
        if cached_result is not None:
            elapsed = (time.perf_counter() - t0) * 1000
            cached_result["cached"] = True
            cached_result["took_ms"] = round(elapsed, 2)
            return cached_result

    # 2. Recall
    candidates = state.recall_service.recall(user_id)
    if not candidates:
        # Fallback to popular
        popular = state.pipeline.get_popular_movies(top_k)
        items = [MovieItem(movie_id=m["movie_id"], title=m["title"], score=m.get("popularity_score", 0.0))
                  for m in popular[:top_k]]
        elapsed = (time.perf_counter() - t0) * 1000
        return RecommendationResponse(user_id=user_id, recommendations=items, took_ms=round(elapsed, 2))

    # 3. Rank
    ranked = state.ranking_service.rank(user_id, candidates, top_k)

    # 4. Build response with movie titles
    items = []
    for r in ranked:
        info = state.pipeline.get_movie_info(r["movie_id"])
        items.append(MovieItem(
            movie_id=r["movie_id"],
            title=info.get("title", f"Movie {r['movie_id']}"),
            score=r["score"],
        ))

    elapsed = (time.perf_counter() - t0) * 1000
    result = RecommendationResponse(
        user_id=user_id,
        recommendations=items,
        cached=False,
        took_ms=round(elapsed, 2),
    )

    # 5. Write cache
    if use_cache and state.cache:
        state.cache.set_json(cache_key, result.model_dump(), ttl=state.cache.settings.redis_ttl_recommend)

    return result


# ---------- Popular Movies ----------

@router.get("/popular", response_model=PopularResponse)
async def popular(
    limit: int = Query(default=50, ge=1, le=200),
    state: AppState = Depends(get_state),
):
    """Get global popular movies list."""
    if state.pipeline is None:
        raise HTTPException(status_code=503, detail="Services not initialized")

    t0 = time.perf_counter()

    cache_key = f"popular:{limit}"
    if state.cache:
        cached = state.cache.get_json(cache_key)
        if cached:
            elapsed = (time.perf_counter() - t0) * 1000
            return PopularResponse(popular=cached, took_ms=round(elapsed, 2))

    movies = state.pipeline.get_popular_movies(limit)
    items = [MovieDetail(**m) for m in movies]

    elapsed = (time.perf_counter() - t0) * 1000

    if state.cache:
        state.cache.set_json(cache_key, [m.model_dump() for m in items],
                             ttl=state.cache.settings.redis_ttl_popular)

    return PopularResponse(popular=items, took_ms=round(elapsed, 2))


# ---------- Movie Detail ----------

@router.get("/movie/{movie_id}", response_model=MovieDetail)
async def movie_detail(
    movie_id: int,
    state: AppState = Depends(get_state),
):
    """Get detailed information about a specific movie."""
    if state.pipeline is None:
        raise HTTPException(status_code=503, detail="Services not initialized")

    cache_key = f"movie:{movie_id}"
    if state.cache:
        cached = state.cache.get_json(cache_key)
        if cached:
            return MovieDetail(**cached)

    info = state.pipeline.get_movie_info(movie_id)
    if not info:
        raise HTTPException(status_code=404, detail=f"Movie {movie_id} not found")

    if state.cache:
        state.cache.set_json(cache_key, info, ttl=3600)

    return MovieDetail(**info)


# ---------- User Profile ----------

@router.get("/user/{user_id}/profile", response_model=UserProfileResponse)
async def user_profile(
    user_id: int,
    state: AppState = Depends(get_state),
):
    """Get user profile: rating stats, genre preferences, history."""
    if state.user_profile_builder is None:
        raise HTTPException(status_code=503, detail="Services not initialized")

    cache_key = f"profile:{user_id}"
    if state.cache:
        cached = state.cache.get_json(cache_key)
        if cached:
            return UserProfileResponse(**cached)

    profile = state.user_profile_builder.build_profile(user_id)

    if state.cache:
        state.cache.set_json(cache_key, profile, ttl=state.cache.settings.redis_ttl_user_profile)

    return UserProfileResponse(**profile)


# ---------- Search ----------

@router.get("/search", response_model=SearchResponse)
async def search(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(default=20, ge=1, le=100),
    state: AppState = Depends(get_state),
):
    """Search movies by title (simple substring match)."""
    if state.pipeline is None:
        raise HTTPException(status_code=503, detail="Services not initialized")

    query = q.lower()
    movies = state.pipeline.movies
    mask = movies["title"].str.lower().str.contains(query, na=False)
    matched = movies[mask].head(limit)

    results = []
    for _, row in matched.iterrows():
        results.append(MovieDetail(
            movie_id=int(row["movieId"]),
            title=str(row["title"]),
            genres=str(row.get("genres", "")),
            avg_rating=float(row.get("avg_rating", 0)) if pd.notna(row.get("avg_rating")) else 0.0,
            rating_count=int(row.get("rating_count", 0)) if pd.notna(row.get("rating_count")) else 0,
            popularity_score=float(row.get("popularity_score", 0)) if pd.notna(row.get("popularity_score")) else 0.0,
            year=float(row.get("year")) if pd.notna(row.get("year")) else None,
        ))

    return SearchResponse(results=results, total=len(results))


import pandas as pd


# ---------- Rebuild Index ----------

@router.post("/rebuild-index", response_model=RebuildResponse)
async def rebuild_index(
    state: AppState = Depends(get_state),
):
    """
    Rebuild the FAISS HNSW index and retrain embeddings.

    This is a long-running operation that reloads data, retrains MF,
    rebuilds the FAISS index, and clears relevant caches.
    """
    if state.pipeline is None:
        raise HTTPException(status_code=503, detail="Services not initialized")

    try:
        t0 = time.perf_counter()

        # Clear caches
        if state.cache:
            state.cache.delete_pattern("rec:*")
            state.cache.delete_pattern("topk:*")
            logger.info("Cleared recommendation caches")

        # Rebuild embeddings
        state.embedding_service.train(state.pipeline)
        state.embedding_service.save()

        # Rebuild FAISS index
        state.faiss_index.build(
            state.embedding_service.item_embeddings,
            state.pipeline.movie_ids,
        )

        elapsed = time.perf_counter() - t0
        logger.info(f"Index rebuild complete in {elapsed:.1f}s")

        return RebuildResponse(
            status="success",
            message=f"Index rebuilt: {state.faiss_index.ntotal} vectors",
            took_seconds=round(elapsed, 2),
        )

    except Exception as e:
        logger.error(f"Rebuild failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
