from __future__ import annotations

import json
import logging
from typing import Any

from app.config import get_settings


logger = logging.getLogger(__name__)


class FeedbackKafkaProducer:
    """Small optional Kafka producer for feedback events.

    Kafka is treated as an enhancement path. If the client library is missing or
    the broker is unavailable, API feedback persistence still succeeds.
    """

    def __init__(
        self,
        bootstrap_servers: str | None = None,
        topic: str | None = None,
        enabled: bool | None = None,
    ) -> None:
        settings = get_settings()
        self.enabled = settings.kafka_enabled if enabled is None else enabled
        self.bootstrap_servers = bootstrap_servers or settings.kafka_bootstrap_servers
        self.topic = topic or settings.kafka_feedback_topic
        self.client_id = settings.kafka_client_id
        self.request_timeout_ms = settings.kafka_request_timeout_ms
        self._producer: Any = None
        self._disabled_reason: str | None = None

    def send_event(self, event: dict[str, Any]) -> bool:
        if not self.enabled:
            return False
        producer = self._get_producer()
        if producer is None:
            return False

        payload = dict(event)
        try:
            future = producer.send(self.topic, payload)
            future.add_errback(self._on_send_error)
            producer.flush(timeout=0.2)
            return True
        except Exception as exc:
            logger.warning("Kafka feedback send failed: %s", exc)
            return False

    def close(self) -> None:
        if self._producer is not None:
            try:
                self._producer.flush(timeout=1.0)
                self._producer.close(timeout=1.0)
            except Exception:
                logger.debug("Kafka producer close failed", exc_info=True)
            finally:
                self._producer = None

    def _get_producer(self):
        if self._producer is not None:
            return self._producer
        if self._disabled_reason is not None:
            return None
        try:
            from kafka import KafkaProducer
        except Exception as exc:
            self._disabled_reason = f"kafka-python unavailable: {exc}"
            logger.warning("Kafka feedback producer disabled: %s", self._disabled_reason)
            return None

        try:
            self._producer = KafkaProducer(
                bootstrap_servers=[server.strip() for server in self.bootstrap_servers.split(",") if server.strip()],
                client_id=self.client_id,
                value_serializer=lambda value: json.dumps(value, ensure_ascii=False).encode("utf-8"),
                key_serializer=lambda value: str(value).encode("utf-8") if value is not None else None,
                acks=1,
                retries=1,
                linger_ms=20,
                request_timeout_ms=self.request_timeout_ms,
            )
            logger.info("Kafka feedback producer connected: %s topic=%s", self.bootstrap_servers, self.topic)
            return self._producer
        except Exception as exc:
            self._disabled_reason = str(exc)
            logger.warning("Kafka feedback producer disabled: %s", exc)
            return None

    @staticmethod
    def _on_send_error(exc: BaseException) -> None:
        logger.warning("Kafka feedback async send failed: %s", exc)
