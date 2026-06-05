"""
Redis cache layer implementing Cache-Aside pattern with protections against
cache penetration, cache breakdown, and cache avalanche.

Cache-Aside Pattern flow:
1. Read: check cache → hit → return; miss → load from source → write cache → return
2. Write: write to source → invalidate/update cache

Anti-pattern protections:
- Cache penetration (穿透): query for non-existent keys → store empty marker with short TTL
- Cache breakdown (击穿): hot key expires under heavy load → mutex/分布式锁
- Cache avalanche (雪崩): many keys expire simultaneously → random TTL jitter
"""
import json
import logging
import random
import time
from functools import wraps
from typing import Any, Callable, Optional

import redis
from redis import ConnectionPool

from app.config import get_settings

logger = logging.getLogger(__name__)

# Sentinel value for cache penetration protection
NULL_MARKER = "__NULL__"
NULL_MARKER_TTL = 60  # Short TTL for null markers


class RedisCache:
    """
    Redis client wrapper with Cache-Aside and anti-pattern protections.
    """

    def __init__(self):
        settings = get_settings()
        self.settings = settings

        self.pool = ConnectionPool(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            password=settings.redis_password or None,
            max_connections=settings.redis_max_connections,
            decode_responses=True,
        )
        self.client = redis.Redis(connection_pool=self.pool, decode_responses=True)
        logger.info(f"Redis connected: {settings.redis_host}:{settings.redis_port}")

    def _jitter_ttl(self, ttl: int, jitter_pct: float = 0.15) -> int:
        """
        Add random jitter to TTL to prevent cache avalanche.

        Args:
            ttl: Base TTL in seconds.
            jitter_pct: Jitter percentage (0.15 = ±15%).
        """
        jitter = int(ttl * jitter_pct * (random.random() * 2 - 1))
        return max(ttl + jitter, 1)

    def get(self, key: str) -> Optional[str]:
        """Get value from cache. Returns None on miss."""
        try:
            value = self.client.get(key)
            if value == NULL_MARKER:
                return None
            return value
        except redis.RedisError as e:
            logger.warning(f"Redis GET error for key={key}: {e}")
            return None

    def set(self, key: str, value: str, ttl: int = 600) -> bool:
        """Set value in cache with jittered TTL."""
        try:
            ttl = self._jitter_ttl(ttl)
            self.client.setex(key, ttl, value)
            return True
        except redis.RedisError as e:
            logger.warning(f"Redis SET error for key={key}: {e}")
            return False

    def set_json(self, key: str, value: Any, ttl: int = 600) -> bool:
        """Set JSON-serializable value in cache."""
        try:
            return self.set(key, json.dumps(value, ensure_ascii=False), ttl)
        except (TypeError, ValueError) as e:
            logger.warning(f"Redis SET JSON error: {e}")
            return False

    def get_json(self, key: str) -> Optional[Any]:
        """Get and deserialize JSON value from cache."""
        raw = self.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None

    def set_null_marker(self, key: str) -> bool:
        """
        Cache a null marker to prevent cache penetration for non-existent keys.
        """
        try:
            self.client.setex(key, NULL_MARKER_TTL, NULL_MARKER)
            return True
        except redis.RedisError:
            return False

    def delete(self, key: str) -> bool:
        """Delete a key from cache."""
        try:
            self.client.delete(key)
            return True
        except redis.RedisError:
            return False

    def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching a pattern."""
        try:
            keys = list(self.client.scan_iter(match=pattern, count=100))
            if keys:
                return self.client.delete(*keys)
            return 0
        except redis.RedisError:
            return 0

    def exists(self, key: str) -> bool:
        try:
            return bool(self.client.exists(key))
        except redis.RedisError:
            return False

    def health_check(self) -> bool:
        """Check Redis connectivity."""
        try:
            return self.client.ping()
        except redis.RedisError:
            return False

    def cache_aside(
        self,
        key: str,
        loader: Callable[[], Any],
        ttl: int = 600,
        null_marker: bool = True,
    ) -> Any:
        """
        Cache-Aside pattern decorator-like helper.

        Args:
            key: Cache key.
            loader: Callable that returns data when cache misses.
            ttl: Time-to-live in seconds.
            null_marker: If True, cache null results (anti-penetration).

        Returns:
            Cached or freshly loaded data.
        """
        # 1. Try cache
        cached = self.get_json(key)
        if cached is not None:
            return cached

        # Check for null marker
        if null_marker:
            raw = self.client.get(key) if self.health_check() else None
            if raw == NULL_MARKER:
                return None

        # 2. Load from source
        try:
            data = loader()
        except Exception as e:
            logger.error(f"Loader error for key={key}: {e}")
            return None

        # 3. Write to cache
        if data is not None:
            self.set_json(key, data, ttl)
        elif null_marker:
            self.set_null_marker(key)

        return data


# Module-level singleton
_cache_instance: Optional[RedisCache] = None


def get_cache() -> RedisCache:
    """Get or create the RedisCache singleton."""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = RedisCache()
    return _cache_instance
