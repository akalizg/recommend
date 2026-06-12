from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import get_settings
from cache.redis_cache import get_cache
from feedback.feedback_service import NEGATIVE_FEEDBACK, POSITIVE_FEEDBACK
from feedback.realtime_recommender import RealtimeRecipeRecommender


logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)
logging.getLogger("kafka").setLevel(logging.WARNING)


def parse_args() -> argparse.Namespace:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Consume recipe feedback events from Kafka and update Redis.")
    parser.add_argument("--bootstrap-servers", default=settings.kafka_bootstrap_servers)
    parser.add_argument("--topic", default=settings.kafka_feedback_topic)
    parser.add_argument("--group-id", default=settings.kafka_consumer_group)
    parser.add_argument("--max-events", type=int, default=0, help="Stop after N events; 0 means run forever.")
    parser.add_argument("--from-beginning", action="store_true", help="Start from earliest offsets for validation.")
    parser.add_argument("--realtime-top-k", type=int, default=settings.final_top_k)
    parser.add_argument(
        "--disable-realtime-recommend",
        action="store_true",
        help="Only update Redis realtime profile; do not build realtime recommendation cache.",
    )
    return parser.parse_args()


def _load_event(raw_value: bytes | str | dict[str, Any]) -> dict[str, Any] | None:
    if isinstance(raw_value, dict):
        return raw_value
    try:
        text = raw_value.decode("utf-8") if isinstance(raw_value, bytes) else str(raw_value)
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except Exception:
        logger.warning("Invalid Kafka feedback message: %r", raw_value)
        return None


def _append_unique(values: list[int], value: int, max_len: int) -> list[int]:
    result = list(values or [])
    if value in result:
        result.remove(value)
    result.insert(0, value)
    return result[:max_len]


def apply_event_to_redis(
    cache,
    event: dict[str, Any],
    recommender: RealtimeRecipeRecommender | None = None,
    realtime_top_k: int = 20,
) -> dict[str, Any] | None:
    user_id = event.get("user_id")
    recipe_id = event.get("recipe_id", event.get("movie_id"))
    feedback_type = str(event.get("feedback_type") or event.get("event_type") or "").strip().lower()
    if user_id is None or recipe_id is None:
        return None
    try:
        user_id = int(user_id)
        recipe_id = int(recipe_id)
    except (TypeError, ValueError):
        return None

    created_at = str(event.get("created_at") or datetime.now(timezone.utc).isoformat())
    recent_key = f"user:recent_feedback:{user_id}"
    profile_key = f"user:realtime_profile:{user_id}"

    recent = cache.get_json(recent_key)
    if not isinstance(recent, list):
        recent = []
    normalized_event = {
        "user_id": user_id,
        "movie_id": recipe_id,
        "recipe_id": recipe_id,
        "feedback_type": feedback_type,
        "feedback_value": event.get("feedback_value"),
        "rank_position": event.get("rank_position"),
        "score": event.get("score"),
        "created_at": created_at,
        "source": "kafka_feedback_consumer",
    }
    recent = [normalized_event, *recent][:50]
    cache.set_json(recent_key, recent, ttl=get_settings().redis_ttl_user_profile)

    profile = cache.get_json(profile_key)
    if not isinstance(profile, dict):
        profile = {
            "user_id": user_id,
            "positive_movie_ids": [],
            "negative_movie_ids": [],
            "positive_recipe_ids": [],
            "negative_recipe_ids": [],
            "recent_feedback": [],
        }

    if feedback_type in POSITIVE_FEEDBACK:
        profile["positive_movie_ids"] = _append_unique(profile.get("positive_movie_ids", []), recipe_id, 100)
        profile["positive_recipe_ids"] = _append_unique(profile.get("positive_recipe_ids", []), recipe_id, 100)
    if feedback_type in NEGATIVE_FEEDBACK:
        profile["negative_movie_ids"] = _append_unique(profile.get("negative_movie_ids", []), recipe_id, 100)
        profile["negative_recipe_ids"] = _append_unique(profile.get("negative_recipe_ids", []), recipe_id, 100)

    profile["recent_feedback"] = recent
    profile["updated_at"] = created_at
    cache.set_json(profile_key, profile, ttl=get_settings().redis_ttl_user_profile)
    cache.delete_pattern(f"rec:user:{user_id}:*")
    cache.delete(f"profile:{user_id}")
    if recommender is not None:
        try:
            realtime_result = recommender.build_and_cache(cache, profile, top_k=realtime_top_k)
            profile["realtime_recommendation_count"] = (
                len(realtime_result.get("recommendations", [])) if realtime_result else 0
            )
        except Exception as exc:
            logger.warning("Realtime recommendation cache update failed for user=%s: %s", user_id, exc)
    return profile


def main() -> None:
    args = parse_args()
    try:
        from kafka import KafkaConsumer
    except Exception as exc:
        raise RuntimeError("kafka-python is not installed. Run `pip install -r requirements.txt`.") from exc

    cache = get_cache()
    recommender = None if args.disable_realtime_recommend else RealtimeRecipeRecommender()
    consumer = KafkaConsumer(
        args.topic,
        bootstrap_servers=[server.strip() for server in args.bootstrap_servers.split(",") if server.strip()],
        group_id=args.group_id,
        auto_offset_reset="earliest" if args.from_beginning else "latest",
        enable_auto_commit=True,
        value_deserializer=lambda value: value,
        consumer_timeout_ms=1000 if args.max_events else 1000,
    )
    logger.info("Kafka feedback consumer started: topic=%s bootstrap=%s", args.topic, args.bootstrap_servers)

    consumed = 0
    try:
        while True:
            batch = consumer.poll(timeout_ms=1000, max_records=50)
            if not batch:
                if args.max_events and consumed >= args.max_events:
                    break
                continue
            for messages in batch.values():
                for message in messages:
                    event = _load_event(message.value)
                    if not event:
                        continue
                    profile = apply_event_to_redis(
                        cache,
                        event,
                        recommender=recommender,
                        realtime_top_k=args.realtime_top_k,
                    )
                    consumed += 1
                    logger.info(
                        "Consumed feedback event user=%s recipe=%s profile_updated=%s realtime_recs=%s",
                        event.get("user_id"),
                        event.get("recipe_id", event.get("movie_id")),
                        bool(profile),
                        profile.get("realtime_recommendation_count") if isinstance(profile, dict) else None,
                    )
                    if args.max_events and consumed >= args.max_events:
                        return
    finally:
        consumer.close()
        logger.info("Kafka feedback consumer stopped after %s events", consumed)


if __name__ == "__main__":
    main()
