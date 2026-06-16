"""
FastAPI application entry point.

Lifecycle:
1. Startup: load data, load/train embeddings, build/load FAISS index,
   load/train rank model, connect Redis, wire services.
2. Runtime: serve recommendation API.
3. Shutdown: close connections, persist state.
"""
import logging
import os
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

# Ensure project root on path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.logging_config import setup_logging
from api.routes import router, _app_state
from feature.pipeline import FeaturePipeline
from feature.user_profile import UserProfileBuilder
from embedding.embedding_service import EmbeddingService
from embedding.matrix_factorization import MatrixFactorization
from recall.faiss_index import FaissHNSWIndex
from recall.recall_service import RecallService
from rank.train import train_rank_model, load_rank_model
from rank.rank_model import RankingService
from cache.redis_cache import get_cache
from feedback.feedback_service import FeedbackService
from experiment.ab_service import ABService
from taste_twin import router as taste_twin_router
from taste_twin.service import TasteTwinService

logger = logging.getLogger(__name__)


def initialize_services():
    """
    Initialize all service components in the correct dependency order.

    Order:
    1. FeaturePipeline (data loading & processing)
    2. EmbeddingService (MF training or loading)
    3. FaissHNSWIndex (ANN index build or load)
    4. RecallService (wires embedding + FAISS)
    5. RankingService (XGBoost model loading/training)
    6. RedisCache (caching layer)
    7. UserProfileBuilder (profile queries)
    8. FeedbackService (feedback logs and realtime profile)
    """
    settings = get_settings()
    state = _app_state
    models_dir = settings.models_dir
    models_dir.mkdir(parents=True, exist_ok=True)

    # ---- 1. Feature Pipeline ----
    logger.info("[1/7] Loading feature pipeline...")
    feature_cache = Path(settings.feature_cache_path)
    if feature_cache.exists():
        try:
            state.pipeline = FeaturePipeline.load(str(feature_cache))
            logger.info("Feature pipeline loaded from cache")
        except Exception as e:
            logger.warning(f"Failed to load cached pipeline: {e}, rebuilding...")
            state.pipeline = FeaturePipeline().run()
            state.pipeline.save()
    else:
        state.pipeline = FeaturePipeline().run()
        state.pipeline.save()

    # ---- 2. Embedding Service ----
    logger.info("[2/7] Loading/training embeddings...")
    state.embedding_service = EmbeddingService(state.pipeline)
    embed_path = Path(settings.embedding_model_path)
    if embed_path.exists():
        try:
            state.embedding_service.load()
            logger.info("Embeddings loaded from disk")
        except Exception as e:
            logger.warning(f"Failed to load embeddings: {e}, training...")
            state.embedding_service.train(state.pipeline)
            state.embedding_service.save()
    else:
        state.embedding_service.train(state.pipeline)
        state.embedding_service.save()

    # ---- 3. FAISS HNSW Index ----
    logger.info("[3/7] Loading/building FAISS index...")
    state.faiss_index = FaissHNSWIndex(dimension=settings.faiss_dimension)
    index_path = settings.faiss_index_path
    if os.path.exists(index_path):
        try:
            state.faiss_index.load(index_path)
            logger.info(f"FAISS index loaded: {state.faiss_index.ntotal} vectors")
        except Exception as e:
            logger.warning(f"Failed to load FAISS index: {e}, building...")
            state.faiss_index.build(state.embedding_service.item_embeddings, state.pipeline.movie_ids)
    else:
        state.faiss_index.build(state.embedding_service.item_embeddings, state.pipeline.movie_ids)

    # ---- 4. Recall Service ----
    logger.info("[4/7] Initializing recall service...")
    state.recall_service = RecallService(
        state.faiss_index, state.embedding_service, state.pipeline
    )

    # ---- 5. Ranking Service ----
    logger.info("[5/7] Loading/training ranking model...")
    rank_path = settings.rank_model_path
    if os.path.exists(rank_path):
        try:
            rank_model = load_rank_model(rank_path)
            logger.info("Rank model loaded from disk")
        except Exception as e:
            logger.warning(f"Failed to load rank model: {e}, training...")
            rank_model = train_rank_model(state.pipeline, state.embedding_service)
    else:
        rank_model = train_rank_model(state.pipeline, state.embedding_service)

    state.ranking_service = RankingService(state.pipeline, state.embedding_service, rank_model)

    # ---- 6. Redis Cache ----
    logger.info("[6/7] Connecting to Redis...")
    try:
        state.cache = get_cache()
        if state.cache.health_check():
            logger.info("Redis connected successfully")
        else:
            logger.warning("Redis ping failed, continuing without cache")
    except Exception as e:
        logger.warning(f"Redis connection failed: {e}, continuing without cache")
        state.cache = None

    # ---- 7. User Profile Builder ----
    logger.info("[7/7] Initializing user profile builder...")
    state.user_profile_builder = UserProfileBuilder(state.pipeline)
    state.feedback_service = FeedbackService(cache=state.cache)
    state.ab_service = ABService(cache=state.cache)

    # ---- Taste Twin: isolated user-vector matching service ----
    logger.info("Initializing Taste Twin service...")
    state.taste_twin_service = TasteTwinService.create_default()
    state.taste_twin_service.initialize()

    logger.info("=== All services initialized ===")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan: startup and shutdown events."""
    # Startup
    setup_logging()
    logger.info(f"Starting {get_settings().app_name} v{get_settings().app_version}")
    t0 = time.perf_counter()
    initialize_services()
    elapsed = time.perf_counter() - t0
    logger.info(f"Startup complete in {elapsed:.1f}s")
    yield
    # Shutdown
    logger.info("Shutting down...")
    if _app_state.cache:
        try:
            _app_state.cache.pool.disconnect()
        except Exception:
            pass
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Food.com recipe recommendation system with offline recall, ranking, LightGCN, and feedback loops",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # CORS — allow frontend dev server
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)
    app.include_router(taste_twin_router)

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
