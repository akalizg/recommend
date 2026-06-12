"""Index RecipeRec profile/detail documents into Elasticsearch."""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd
import requests


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PROFILE = PROJECT_ROOT / "data" / "features" / "movie_profile.csv"
DEFAULT_DETAIL = PROJECT_ROOT / "data" / "recipe-canonical" / "recipe_detail_metadata.csv"

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


MAPPING = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "analysis": {
            "analyzer": {
                "recipe_text": {
                    "type": "standard",
                    "stopwords": "_english_",
                }
            }
        },
    },
    "mappings": {
        "properties": {
            "recipe_id": {"type": "integer"},
            "movieId": {"type": "integer"},
            "title": {"type": "text", "analyzer": "recipe_text", "fields": {"keyword": {"type": "keyword"}}},
            "clean_title": {"type": "text", "analyzer": "recipe_text"},
            "description": {"type": "text", "analyzer": "recipe_text"},
            "genres": {"type": "keyword"},
            "tags_text": {"type": "text", "analyzer": "recipe_text"},
            "ingredients_text": {"type": "text", "analyzer": "recipe_text"},
            "author_name": {"type": "keyword"},
            "image_url": {"type": "keyword", "index": False},
            "source_url": {"type": "keyword", "index": False},
            "movie_avg_rating": {"type": "float"},
            "movie_rating_count": {"type": "integer"},
            "movie_popularity": {"type": "float"},
            "rating_value": {"type": "float"},
            "review_count": {"type": "integer"},
            "minutes": {"type": "float"},
            "ready_in_display": {"type": "keyword"},
            "recipe_yield_raw": {"type": "keyword"},
            "serves_best_guess": {"type": "float"},
            "n_steps": {"type": "integer"},
            "n_ingredients": {"type": "integer"},
        }
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Index recipes into Elasticsearch.")
    parser.add_argument("--es-url", default="http://localhost:9200")
    parser.add_argument("--index", default="recipes")
    parser.add_argument("--profile", default=str(DEFAULT_PROFILE))
    parser.add_argument("--detail", default=str(DEFAULT_DETAIL))
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--recreate", action="store_true")
    parser.add_argument("--timeout", type=float, default=30.0)
    return parser.parse_args()


def _json_value(value: Any) -> Any:
    if value is None or pd.isna(value):
        return None
    if hasattr(value, "item"):
        value = value.item()
    return value


def _json_list_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    if isinstance(value, list):
        return " ".join(str(item) for item in value)
    text = str(value)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return text
    if isinstance(parsed, list):
        return " ".join(str(item) for item in parsed)
    return text


def _doc_from_row(row: dict[str, Any]) -> dict[str, Any]:
    recipe_id = int(_json_value(row.get("movieId") or row.get("recipe_id")))
    title = _json_value(row.get("title")) or _json_value(row.get("name")) or _json_value(row.get("clean_title")) or f"Recipe {recipe_id}"
    ingredients_text = _json_list_text(row.get("ingredients_json"))
    tags_text = _json_list_text(row.get("tags_json")) or str(_json_value(row.get("tag_text")) or "")
    doc = {
        "recipe_id": recipe_id,
        "movieId": recipe_id,
        "title": title,
        "clean_title": _json_value(row.get("clean_title")) or title,
        "description": _json_value(row.get("description")) or "",
        "genres": _json_value(row.get("genres")) or "",
        "tags_text": tags_text,
        "ingredients_text": ingredients_text,
        "ingredients_json": _json_value(row.get("ingredients_json")),
        "quantities_json": _json_value(row.get("quantities_json")),
        "steps_json": _json_value(row.get("steps_json")),
        "nutrition_json": _json_value(row.get("nutrition_json")),
        "image_url": _json_value(row.get("image_url")) or "",
        "source_url": _json_value(row.get("source_url")) or "",
        "ready_in_display": _json_value(row.get("ready_in_display")) or "",
        "recipe_yield_raw": _json_value(row.get("recipe_yield_raw")) or "",
        "author_name": _json_value(row.get("author_name")) or "",
    }
    for column in [
        "year",
        "minutes",
        "movie_avg_rating",
        "movie_rating_count",
        "movie_popularity",
        "rating_value",
        "review_count",
        "serves_best_guess",
        "n_steps",
        "n_ingredients",
        "photo_count",
    ]:
        value = _json_value(row.get(column))
        if value is not None:
            doc[column] = value
    return doc


def _request(method: str, url: str, timeout: float, **kwargs) -> requests.Response:
    response = requests.request(method, url, timeout=timeout, **kwargs)
    if response.status_code >= 400:
        raise RuntimeError(f"{method} {url} failed: {response.status_code} {response.text[:500]}")
    return response


def _bulk_index(es_url: str, index: str, docs: list[dict[str, Any]], timeout: float) -> int:
    if not docs:
        return 0
    lines = []
    for doc in docs:
        lines.append(json.dumps({"index": {"_index": index, "_id": str(doc["recipe_id"])}}, ensure_ascii=False))
        lines.append(json.dumps(doc, ensure_ascii=False, default=str))
    payload = "\n".join(lines) + "\n"
    response = _request(
        "POST",
        f"{es_url}/_bulk",
        timeout,
        data=payload.encode("utf-8"),
        headers={"Content-Type": "application/x-ndjson"},
    )
    result = response.json()
    if result.get("errors"):
        first_error = next((item for item in result.get("items", []) if item.get("index", {}).get("error")), None)
        raise RuntimeError(f"Bulk index reported errors: {first_error}")
    return len(docs)


def index_recipes(
    es_url: str,
    index: str,
    profile_path: str | Path,
    detail_path: str | Path,
    batch_size: int = 1000,
    recreate: bool = False,
    timeout: float = 30.0,
) -> dict[str, Any]:
    es_url = es_url.rstrip("/")
    profile_file = Path(profile_path)
    detail_file = Path(detail_path)
    _request("GET", es_url, timeout)

    if recreate:
        requests.delete(f"{es_url}/{index}", timeout=timeout)
    exists = requests.head(f"{es_url}/{index}", timeout=timeout).status_code == 200
    if not exists:
        _request("PUT", f"{es_url}/{index}", timeout, json=MAPPING)

    profile = pd.read_csv(profile_file)
    profile["movieId"] = pd.to_numeric(profile["movieId"], errors="coerce").astype("Int64")
    wanted_ids = set(profile["movieId"].dropna().astype(int).tolist())
    profile = profile.dropna(subset=["movieId"]).copy()
    profile["movieId"] = profile["movieId"].astype(int)
    profile_by_id = {int(row["movieId"]): row for row in profile.to_dict(orient="records")}

    indexed = 0
    docs: list[dict[str, Any]] = []
    seen_detail_ids: set[int] = set()
    detail_columns = pd.read_csv(detail_file, nrows=0).columns.tolist()
    start = time.perf_counter()
    for chunk in pd.read_csv(detail_file, chunksize=20_000, usecols=detail_columns):
        chunk["recipe_id"] = pd.to_numeric(chunk["recipe_id"], errors="coerce").astype("Int64")
        chunk = chunk[chunk["recipe_id"].isin(wanted_ids)].copy()
        for row in chunk.to_dict(orient="records"):
            recipe_id = int(row["recipe_id"])
            merged = {**profile_by_id.get(recipe_id, {}), **row, "movieId": recipe_id}
            docs.append(_doc_from_row(merged))
            seen_detail_ids.add(recipe_id)
            if len(docs) >= batch_size:
                indexed += _bulk_index(es_url, index, docs, timeout)
                docs.clear()
                logger.info("Indexed %s recipes...", indexed)

    for recipe_id, row in profile_by_id.items():
        if recipe_id not in seen_detail_ids:
            docs.append(_doc_from_row(row))
            if len(docs) >= batch_size:
                indexed += _bulk_index(es_url, index, docs, timeout)
                docs.clear()
                logger.info("Indexed %s recipes...", indexed)
    indexed += _bulk_index(es_url, index, docs, timeout)
    _request("POST", f"{es_url}/{index}/_refresh", timeout)

    elapsed = time.perf_counter() - start
    summary = {
        "es_url": es_url,
        "index": index,
        "profile_rows": len(profile),
        "indexed": indexed,
        "elapsed_seconds": round(elapsed, 2),
    }
    logger.info("Index summary: %s", summary)
    return summary


def main() -> None:
    args = parse_args()
    try:
        index_recipes(args.es_url, args.index, args.profile, args.detail, args.batch_size, args.recreate, args.timeout)
    except Exception as exc:
        logger.error("%s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
