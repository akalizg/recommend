"""
Tests for Redis cache layer (requires a running Redis instance,
or uses fakeredis/mock for offline testing).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest


class TestCacheAsideLogic:
    """Test the cache-aside helper without requiring Redis."""

    def test_cache_aside_loader_called(self, monkeypatch):
        """Verify the loader is called and result returned."""
        import json
        from cache.redis_cache import RedisCache, NULL_MARKER

        cache = RedisCache.__new__(RedisCache)
        # Manually set attributes
        cache.settings = None

        # Track calls
        calls = []

        class FakeClient:
            def __init__(self):
                self.store = {}

            def get(self, key):
                return self.store.get(key)

            def setex(self, key, ttl, value):
                self.store[key] = value

            def exists(self, key):
                return key in self.store

            def ping(self):
                return True

        fake_client = FakeClient()
        cache.client = fake_client

        def health_check():
            return True
        cache.health_check = health_check

        def my_loader():
            calls.append("loaded")
            return {"data": "test_value"}

        # First call: cache miss, should call loader
        result = cache.cache_aside("test_key", my_loader, ttl=60)
        assert result == {"data": "test_value"}
        assert "loaded" in calls

        # Second call: cache hit, should NOT call loader
        calls.clear()
        result2 = cache.cache_aside("test_key", my_loader, ttl=60)
        assert result2 == {"data": "test_value"}
        assert "loaded" not in calls  # loader not called again

    def test_null_marker_protection(self):
        """Test that null results are cached to prevent penetration."""
        from cache.redis_cache import RedisCache, NULL_MARKER

        cache = RedisCache.__new__(RedisCache)

        class FakeClient:
            def __init__(self):
                self.store = {}

            def get(self, key):
                return self.store.get(key)

            def setex(self, key, ttl, value):
                self.store[key] = value

            def ping(self):
                return True

        fake_client = FakeClient()
        cache.client = fake_client
        cache.health_check = lambda: True

        # Loader returns None
        calls = []
        def none_loader():
            calls.append("called")
            return None

        result = cache.cache_aside("null_key", none_loader, ttl=60, null_marker=True)
        assert result is None
        assert "null_key" in fake_client.store
        assert fake_client.store["null_key"] == NULL_MARKER

        # Second call: should see null marker and return None without calling loader
        calls.clear()
        result2 = cache.cache_aside("null_key", none_loader, ttl=60, null_marker=True)
        assert result2 is None
        assert "called" not in calls  # loader skipped due to null marker

    def test_jitter_ttl(self):
        """Verify TTL jitter is within expected range."""
        from cache.redis_cache import RedisCache

        cache = RedisCache.__new__(RedisCache)
        cache.settings = None

        # Run many times to check jitter range
        base = 100
        for _ in range(100):
            jittered = cache._jitter_ttl(base, jitter_pct=0.15)
            assert 85 <= jittered <= 115
