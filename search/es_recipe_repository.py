from __future__ import annotations

import logging
from typing import Any

import requests

from app.config import get_settings


logger = logging.getLogger(__name__)
_SESSION = requests.Session()


class ESRecipeRepository:
    def __init__(self, base_url: str | None = None, index_name: str | None = None, timeout: float | None = None) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.elasticsearch_url).rstrip("/")
        self.index_name = index_name or settings.elasticsearch_index_recipes
        self.timeout = timeout if timeout is not None else settings.elasticsearch_timeout_seconds

    @property
    def enabled(self) -> bool:
        return bool(get_settings().elasticsearch_enabled and self.base_url and self.index_name)

    def get_recipe(self, recipe_id: int) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        try:
            response = _SESSION.get(
                f"{self.base_url}/{self.index_name}/_doc/{recipe_id}",
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            logger.warning("Elasticsearch recipe lookup failed: %s", exc)
            return None
        if response.status_code == 404:
            return None
        if response.status_code >= 400:
            logger.warning("Elasticsearch recipe lookup returned %s: %s", response.status_code, response.text[:300])
            return None
        source = response.json().get("_source")
        return source if isinstance(source, dict) else None

    def get_recipes(self, recipe_ids: list[int]) -> dict[int, dict[str, Any]]:
        if not self.enabled or not recipe_ids:
            return {}
        body = {"ids": [str(recipe_id) for recipe_id in recipe_ids]}
        try:
            response = _SESSION.post(
                f"{self.base_url}/{self.index_name}/_mget",
                json=body,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            logger.warning("Elasticsearch recipe multi-get failed: %s", exc)
            return {}
        if response.status_code >= 400:
            logger.warning("Elasticsearch recipe multi-get returned %s: %s", response.status_code, response.text[:300])
            return {}
        records: dict[int, dict[str, Any]] = {}
        for doc in response.json().get("docs", []):
            if not doc.get("found"):
                continue
            source = doc.get("_source")
            if isinstance(source, dict):
                try:
                    recipe_id = int(source.get("recipe_id") or source.get("movieId") or doc.get("_id"))
                except (TypeError, ValueError):
                    continue
                records[recipe_id] = source
        return records

    def search_recipes(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        if not self.enabled:
            return []
        body = {
            "size": limit,
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": [
                        "title^4",
                        "clean_title^3",
                        "description^2",
                        "ingredients_text^2",
                        "tags_text",
                        "author_name",
                    ],
                    "type": "best_fields",
                    "fuzziness": "AUTO",
                }
            },
        }
        try:
            response = _SESSION.post(
                f"{self.base_url}/{self.index_name}/_search",
                json=body,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            logger.warning("Elasticsearch recipe search failed: %s", exc)
            return []
        if response.status_code >= 400:
            logger.warning("Elasticsearch recipe search returned %s: %s", response.status_code, response.text[:300])
            return []
        hits = response.json().get("hits", {}).get("hits", [])
        records = []
        for hit in hits:
            source = hit.get("_source")
            if isinstance(source, dict):
                source["_search_score"] = hit.get("_score")
                records.append(source)
        return records
