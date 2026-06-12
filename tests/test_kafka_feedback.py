from __future__ import annotations


class FakeCache:
    def __init__(self):
        self.values = {}
        self.deleted_patterns = []
        self.deleted = []

    def get_json(self, key):
        return self.values.get(key)

    def set_json(self, key, value, ttl=600):
        self.values[key] = value
        return True

    def delete_pattern(self, pattern):
        self.deleted_patterns.append(pattern)
        return 0

    def delete(self, key):
        self.deleted.append(key)
        return True


class FakeRealtimeRecommender:
    def __init__(self):
        self.calls = []

    def build_and_cache(self, cache, profile, top_k=20):
        self.calls.append((profile["user_id"], top_k))
        result = {
            "user_id": profile["user_id"],
            "recommendations": [
                {
                    "movie_id": 99,
                    "title": "Realtime Recipe",
                    "score": 1.0,
                    "genres": "Dinner",
                }
            ],
            "cached": False,
            "took_ms": 0.0,
            "source": "test",
        }
        cache.set_json(f"recipe:realtime_rec:user:{profile['user_id']}:k:{top_k}", result, ttl=600)
        return result


def test_apply_kafka_feedback_event_to_realtime_profile():
    from scripts.kafka_feedback_consumer import apply_event_to_redis

    cache = FakeCache()
    event = {
        "user_id": 1,
        "recipe_id": 10,
        "feedback_type": "like",
        "feedback_value": 5,
        "created_at": "2026-06-12T00:00:00+00:00",
    }

    profile = apply_event_to_redis(cache, event)

    assert profile is not None
    assert profile["positive_recipe_ids"] == [10]
    assert profile["positive_movie_ids"] == [10]
    assert cache.values["user:recent_feedback:1"][0]["recipe_id"] == 10
    assert cache.deleted_patterns == ["rec:user:1:*"]
    assert cache.deleted == ["profile:1"]


def test_apply_kafka_feedback_event_builds_realtime_recommendations():
    from scripts.kafka_feedback_consumer import apply_event_to_redis

    cache = FakeCache()
    recommender = FakeRealtimeRecommender()
    event = {
        "user_id": 1,
        "recipe_id": 10,
        "feedback_type": "like",
        "feedback_value": 5,
        "created_at": "2026-06-12T00:00:00+00:00",
    }

    profile = apply_event_to_redis(cache, event, recommender=recommender, realtime_top_k=5)

    assert profile["realtime_recommendation_count"] == 1
    assert recommender.calls == [(1, 5)]
    assert cache.values["recipe:realtime_rec:user:1:k:5"]["recommendations"][0]["movie_id"] == 99
