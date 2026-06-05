"""
Initialize Redis with pre-computed popular movies cache.
"""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings
from app.logging_config import setup_logging
from cache.redis_cache import get_cache

setup_logging()
logger = logging.getLogger(__name__)


def init_redis():
    """Pre-warm Redis with popular movies and other frequently-used data."""
    settings = get_settings()
    cache = get_cache()

    if not cache.health_check():
        logger.error("Redis is not available. Please start Redis first.")
        return

    logger.info("Pre-warming Redis cache...")

    # Load pipeline
    from feature.pipeline import FeaturePipeline
    pipeline = FeaturePipeline.load()

    # Cache popular movies
    popular = pipeline.get_popular_movies(50)
    cache.set_json("popular:50", popular, ttl=settings.redis_ttl_popular)
    logger.info(f"Cached {len(popular)} popular movies")

    # Cache a few user profiles for common users
    from feature.user_profile import UserProfileBuilder
    builder = UserProfileBuilder(pipeline)

    common_users = pipeline.ratings["userId"].value_counts().head(20).index.tolist()
    for uid in common_users:
        profile = builder.build_profile(uid)
        cache.set_json(f"profile:{uid}", profile, ttl=settings.redis_ttl_user_profile)
    logger.info(f"Cached {len(common_users)} user profiles")

    logger.info("Redis initialization complete!")


if __name__ == "__main__":
    init_redis()
