"""
FastAPI route definitions for the recommendation system.
"""
import json
import logging
import time
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Query, Depends, Response

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
    OfflineRecommendationItem,
    OfflineRecommendationsResponse,
    OfflineMetricsResponse,
    OfflineAblationResponse,
    OfflineUserProfileResponse,
    OfflineMovieProfileResponse,
    FeedbackRequest,
    FeedbackResponse,
    RealtimeProfileResponse,
    ABGroupResponse,
    ABMetricsResponse,
)
from app.config import PROJECT_ROOT

logger = logging.getLogger(__name__)

router = APIRouter()

OFFLINE_RECOMMENDATIONS_PATH = PROJECT_ROOT / "data" / "final" / "recommendations_with_reasons.csv"
OFFLINE_METRICS_PATH = PROJECT_ROOT / "data" / "eval" / "optimized_offline_metrics.csv"
OFFLINE_METRICS_FALLBACK_PATH = PROJECT_ROOT / "data" / "eval" / "offline_metrics.csv"
OFFLINE_METRICS_SUMMARY_PATH = PROJECT_ROOT / "data" / "eval" / "optimized_eval_summary.json"
OFFLINE_METRICS_SUMMARY_FALLBACK_PATH = PROJECT_ROOT / "data" / "eval" / "eval_summary.json"
OFFLINE_ABLATION_PATH = PROJECT_ROOT / "data" / "eval" / "optimized_ablation_metrics.csv"
OFFLINE_ABLATION_FALLBACK_PATH = PROJECT_ROOT / "data" / "eval" / "ablation_metrics.csv"
OFFLINE_USER_PROFILE_PATH = PROJECT_ROOT / "data" / "features" / "user_profile.csv"
OFFLINE_MOVIE_PROFILE_PATH = PROJECT_ROOT / "data" / "features" / "movie_profile.csv"


def _existing_offline_file(primary: Path, fallback: Optional[Path] = None) -> Path:
    """Resolve the preferred offline artifact without generating or mutating it."""
    if primary.exists():
        return primary
    if fallback and fallback.exists():
        return fallback
    raise HTTPException(status_code=404, detail=f"Offline artifact not found: {primary}")


def _read_offline_csv(primary: Path, fallback: Optional[Path] = None) -> tuple[pd.DataFrame, Path]:
    path = _existing_offline_file(primary, fallback)
    try:
        return pd.read_csv(path), path
    except Exception as exc:
        logger.error("Failed to read offline CSV %s: %s", path, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to read offline artifact: {path.name}")


def _read_offline_json(primary: Path, fallback: Optional[Path] = None) -> tuple[Optional[dict], Optional[Path]]:
    try:
        path = _existing_offline_file(primary, fallback)
    except HTTPException:
        return None, None
    try:
        return json.loads(path.read_text(encoding="utf-8")), path
    except Exception as exc:
        logger.error("Failed to read offline JSON %s: %s", path, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to read offline summary: {path.name}")


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def _json_safe_value(value):
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("{") or text.startswith("["):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return value
    return value


def _json_safe_records(df: pd.DataFrame) -> list[dict]:
    return [{key: _json_safe_value(value) for key, value in row.items()} for row in df.to_dict(orient="records")]


def _require_columns(df: pd.DataFrame, required: set[str], artifact_name: str) -> None:
    missing = sorted(required - set(df.columns))
    if missing:
        raise HTTPException(status_code=500, detail=f"{artifact_name} missing required columns: {missing}")


def _first_profile_row(df: pd.DataFrame, id_column: str, id_value: int, artifact_name: str) -> dict:
    _require_columns(df, {id_column}, artifact_name)
    ids = pd.to_numeric(df[id_column], errors="coerce")
    matched = df[ids == id_value]
    if matched.empty:
        raise HTTPException(status_code=404, detail=f"{artifact_name} not found for {id_column}={id_value}")
    return _json_safe_records(matched.head(1))[0]


def get_metadata_cache_token(state: "AppState") -> str:
    if state.pipeline and hasattr(state.pipeline, "metadata_cache_token"):
        return state.pipeline.metadata_cache_token()
    return "metadata_unknown"


def build_movie_item(movie_id: int, title: str, score: float, info: Optional[dict] = None) -> MovieItem:
    """Build a recommendation item while preserving optional display metadata."""
    info = info or {}
    return MovieItem(
        movie_id=int(movie_id),
        title=info.get("title", title),
        score=float(score),
        genres=info.get("genres", ""),
        poster_url=info.get("poster_url", ""),
        backdrop_url=info.get("backdrop_url", ""),
        overview=info.get("overview", ""),
        release_date=info.get("release_date", ""),
        runtime=info.get("runtime"),
        vote_average=info.get("vote_average"),
        popularity=info.get("popularity"),
        tmdb_id=info.get("tmdb_id"),
        imdb_id=info.get("imdb_id", ""),
    )


def movie_detail_from_search_row(row, info: Optional[dict] = None) -> MovieDetail:
    """Build search result details from the matched row plus optional metadata."""
    info = info or {}
    detail = {
        "movie_id": int(row["movieId"]),
        "title": str(row["title"]),
        "genres": str(row.get("genres", "")),
        "avg_rating": float(row.get("avg_rating", 0)) if pd.notna(row.get("avg_rating")) else 0.0,
        "rating_count": int(row.get("rating_count", 0)) if pd.notna(row.get("rating_count")) else 0,
        "popularity_score": float(row.get("popularity_score", 0)) if pd.notna(row.get("popularity_score")) else 0.0,
        "year": int(row.get("year")) if pd.notna(row.get("year")) else None,
    }

    for field in [
        "poster_url",
        "backdrop_url",
        "overview",
        "release_date",
        "runtime",
        "vote_average",
        "popularity",
        "tmdb_id",
        "imdb_id",
    ]:
        if field in info:
            detail[field] = info[field]

    return MovieDetail(**detail)


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
        self.feedback_service = None
        self.ab_service = None


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
    metadata_token = get_metadata_cache_token(state)
    cache_key = f"rec:user:{user_id}:k:{top_k}:{metadata_token}"
    if use_cache and state.cache:
        cached_result = state.cache.get_json(cache_key)
        if cached_result is not None:
            elapsed = (time.perf_counter() - t0) * 1000
            cached_result["cached"] = True
            cached_result["took_ms"] = round(elapsed, 2)
            if all("poster_url" in item for item in cached_result.get("recommendations", [])):
                return cached_result
            logger.info("Ignoring stale recommendation cache without movie metadata fields")

    # 2. Recall
    candidates = state.recall_service.recall(user_id)
    if not candidates:
        # Fallback to popular
        popular = state.pipeline.get_popular_movies(top_k)
        items = [
            build_movie_item(m["movie_id"], m["title"], m.get("popularity_score", 0.0), m)
            for m in popular[:top_k]
        ]
        elapsed = (time.perf_counter() - t0) * 1000
        return RecommendationResponse(user_id=user_id, recommendations=items, took_ms=round(elapsed, 2))

    # 3. Rank
    ranked = state.ranking_service.rank(user_id, candidates, top_k)

    # 4. Build response with movie titles
    items = []
    for r in ranked[:top_k]:
        info = state.pipeline.get_movie_info(r["movie_id"])
        items.append(build_movie_item(r["movie_id"], f"Movie {r['movie_id']}", r["score"], info))

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


# ---------- Offline Display APIs ----------

@router.get("/offline/recommendations/{user_id}", response_model=OfflineRecommendationsResponse)
async def offline_recommendations(
    user_id: int,
    limit: int = Query(default=20, ge=1, le=100, description="Number of offline recommendations"),
):
    """Read precomputed offline recommendations for display only."""
    df, path = _read_offline_csv(OFFLINE_RECOMMENDATIONS_PATH)
    _require_columns(df, {"userId", "movieId"}, path.name)

    df["userId"] = pd.to_numeric(df["userId"], errors="coerce")
    user_recs = df[df["userId"] == user_id].copy()
    if user_recs.empty:
        raise HTTPException(status_code=404, detail=f"Offline recommendations not found for user {user_id}")

    if "rank_position" in user_recs.columns:
        user_recs["_rank_position"] = pd.to_numeric(user_recs["rank_position"], errors="coerce").fillna(10**9)
        user_recs = user_recs.sort_values(["_rank_position", "movieId"], ascending=[True, True])

    records = _json_safe_records(user_recs.head(limit))
    items = [
        OfflineRecommendationItem(
            user_id=int(record.get("userId")),
            movie_id=int(record.get("movieId")),
            rank_position=record.get("rank_position"),
            rank_score=record.get("rank_score"),
            mmr_score=record.get("mmr_score"),
            movie_title=record.get("movie_title") or "",
            movie_genres=record.get("movie_genres") or "",
            favorite_genres=record.get("favorite_genres") or "",
            final_reason=record.get("final_reason") or "",
            reason_source=record.get("reason_source") or "",
            reason_evidence=record.get("reason_evidence"),
        )
        for record in records
    ]

    return OfflineRecommendationsResponse(
        user_id=user_id,
        recommendations=items,
        total=int(len(user_recs)),
        source=_display_path(path),
    )


@router.get("/offline/metrics", response_model=OfflineMetricsResponse)
async def offline_metrics():
    """Read offline evaluation metrics for dashboard display."""
    metrics, path = _read_offline_csv(OFFLINE_METRICS_PATH, OFFLINE_METRICS_FALLBACK_PATH)
    summary, summary_path = _read_offline_json(OFFLINE_METRICS_SUMMARY_PATH, OFFLINE_METRICS_SUMMARY_FALLBACK_PATH)
    return OfflineMetricsResponse(
        metrics=_json_safe_records(metrics),
        summary=summary,
        source=_display_path(path),
        summary_source=_display_path(summary_path) if summary_path else None,
    )


@router.get("/offline/ablation", response_model=OfflineAblationResponse)
async def offline_ablation():
    """Read offline ablation experiment results for dashboard display."""
    ablation, path = _read_offline_csv(OFFLINE_ABLATION_PATH, OFFLINE_ABLATION_FALLBACK_PATH)
    return OfflineAblationResponse(
        ablation=_json_safe_records(ablation),
        source=_display_path(path),
    )


@router.get("/ab/group/{user_id}", response_model=ABGroupResponse)
async def ab_group(
    user_id: int,
    experiment_name: str = Query(default="recall_rank_v1"),
    state: AppState = Depends(get_state),
):
    """Return the stable A/B group for a user."""
    if state.ab_service is None:
        from experiment.ab_service import ABService

        state.ab_service = ABService(cache=state.cache)
    result = state.ab_service.assign_group(user_id, experiment_name)
    return ABGroupResponse(user_id=user_id, **result)


@router.get("/ab/metrics", response_model=ABMetricsResponse)
async def ab_metrics(
    experiment_name: str = Query(default="recall_rank_v1"),
    state: AppState = Depends(get_state),
):
    """Read lightweight A/B metrics from feedback logs."""
    if state.ab_service is None:
        from experiment.ab_service import ABService

        state.ab_service = ABService(cache=state.cache)
    return ABMetricsResponse(**state.ab_service.metrics(experiment_name))


@router.get("/metrics")
async def prometheus_metrics(state: AppState = Depends(get_state)):
    """Expose Prometheus-compatible process and recommendation counters."""
    from monitor.metrics import build_prometheus_metrics

    redis_ok = bool(state.cache.health_check()) if state.cache else False
    faiss_size = int(state.faiss_index.ntotal) if state.faiss_index else 0
    return Response(
        content=build_prometheus_metrics(redis_ok=redis_ok, faiss_size=faiss_size),
        media_type="text/plain; version=0.0.4",
    )


@router.get("/offline/user-profile/{user_id}", response_model=OfflineUserProfileResponse)
async def offline_user_profile(user_id: int):
    """Read a Spark-built offline user profile for display only."""
    profiles, path = _read_offline_csv(OFFLINE_USER_PROFILE_PATH)
    profile = _first_profile_row(profiles, "userId", user_id, path.name)
    return OfflineUserProfileResponse(
        user_id=user_id,
        profile=profile,
        source=_display_path(path),
    )


@router.get("/offline/movie-profile/{movie_id}", response_model=OfflineMovieProfileResponse)
async def offline_movie_profile(movie_id: int):
    """Read a Spark-built offline movie profile for display only."""
    profiles, path = _read_offline_csv(OFFLINE_MOVIE_PROFILE_PATH)
    profile = _first_profile_row(profiles, "movieId", movie_id, path.name)
    return OfflineMovieProfileResponse(
        movie_id=movie_id,
        profile=profile,
        source=_display_path(path),
    )


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

    metadata_token = get_metadata_cache_token(state)
    cache_key = f"popular:{limit}:{metadata_token}"
    if state.cache:
        cached = state.cache.get_json(cache_key)
        if cached:
            elapsed = (time.perf_counter() - t0) * 1000
            if all("poster_url" in item for item in cached):
                return PopularResponse(popular=cached, took_ms=round(elapsed, 2))
            logger.info("Ignoring stale popular cache without movie metadata fields")

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

    metadata_token = get_metadata_cache_token(state)
    cache_key = f"movie:{movie_id}:{metadata_token}"
    if state.cache:
        cached = state.cache.get_json(cache_key)
        if cached:
            if "poster_url" in cached:
                return MovieDetail(**cached)
            logger.info("Ignoring stale movie cache without movie metadata fields")

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


@router.get("/user/{user_id}/realtime-profile", response_model=RealtimeProfileResponse)
async def realtime_user_profile(user_id: int, state: AppState = Depends(get_state)):
    """Read the realtime feedback profile from Redis or SQLite fallback."""
    if state.feedback_service is None:
        from feedback.feedback_service import FeedbackService

        state.feedback_service = FeedbackService(cache=state.cache)
    profile = state.feedback_service.get_realtime_profile(user_id)
    return RealtimeProfileResponse(user_id=user_id, profile=profile)


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(payload: FeedbackRequest, state: AppState = Depends(get_state)):
    """Persist user feedback and update the realtime profile cache."""
    if state.feedback_service is None:
        from feedback.feedback_service import FeedbackService

        state.feedback_service = FeedbackService(cache=state.cache)
    try:
        result = state.feedback_service.record_feedback(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return FeedbackResponse(status="ok", **result)


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
        info = state.pipeline.get_movie_info(int(row["movieId"]))
        results.append(movie_detail_from_search_row(row, info))

    return SearchResponse(results=results, total=len(results))


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
    if state.embedding_service is None or state.faiss_index is None:
        logger.warning("Index rebuild skipped because embedding or FAISS service is not initialized")
        return RebuildResponse(
            status="success",
            message="Index rebuild skipped: services not initialized",
            took_seconds=0.0,
        )

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
