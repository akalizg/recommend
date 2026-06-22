from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from recommendation.inference_schemas import InferenceCandidate, InferenceContext


def default_model_adapters(include_ranker: bool = True) -> list:
    adapters = [
        ALSModelAdapter(),
        ItemCFModelAdapter(),
        ContentModelAdapter(),
        HotModelAdapter(),
    ]
    if include_ranker:
        adapters.append(RankerModelAdapter())
    return adapters


class ALSModelAdapter:
    name = "als"

    def recommend(self, user_id: int, context: InferenceContext, top_k: int) -> list[InferenceCandidate]:
        if context.recall_service is None:
            return []
        rows = context.recall_service.recall(user_id, k=top_k)
        return [_candidate_from_mapping(row, self.name, "ALS collaborative recall") for row in rows]


class RankerModelAdapter:
    name = "ranker"

    def recommend(self, user_id: int, context: InferenceContext, top_k: int) -> list[InferenceCandidate]:
        if context.recall_service is None or context.ranking_service is None:
            return []
        recall_k = max(top_k * 5, top_k)
        candidates = context.recall_service.recall(user_id, k=recall_k)
        ranked = context.ranking_service.rank(user_id, candidates, top_k=top_k)
        return [_candidate_from_mapping(row, self.name, "ranker rerank score") for row in ranked]


class ItemCFModelAdapter:
    name = "itemcf"

    def recommend(self, user_id: int, context: InferenceContext, top_k: int) -> list[InferenceCandidate]:
        path = context.offline_recommendations_path
        if path is None or context.read_cached_csv is None:
            return []
        df, _ = context.read_cached_csv(path, None)
        if not {"userId", "movieId"}.issubset(set(df.columns)):
            return []
        working = df.copy()
        working["userId"] = pd.to_numeric(working["userId"], errors="coerce")
        working["movieId"] = pd.to_numeric(working["movieId"], errors="coerce")
        user_rows = working[working["userId"] == user_id].dropna(subset=["movieId"]).copy()
        if user_rows.empty:
            return []
        score_col = _first_existing_column(user_rows, ["rank_score", "mmr_score", "recall_score"])
        if "rank_position" in user_rows.columns:
            user_rows["_rank_position"] = pd.to_numeric(user_rows["rank_position"], errors="coerce").fillna(10**9)
            sort_cols = ["_rank_position", "movieId"]
            ascending = [True, True]
        elif score_col:
            user_rows[score_col] = pd.to_numeric(user_rows[score_col], errors="coerce").fillna(0.0)
            sort_cols = [score_col, "movieId"]
            ascending = [False, True]
        else:
            sort_cols = ["movieId"]
            ascending = [True]
        records = user_rows.sort_values(sort_cols, ascending=ascending).head(top_k).to_dict(orient="records")
        return [
            InferenceCandidate(
                recipe_id=int(record["movieId"]),
                score=_float_from_record(record, ["rank_score", "mmr_score", "recall_score"], default=1.0),
                source=self.name,
                reason="offline item collaborative signal",
                metadata=_jsonish_record(record),
            )
            for record in records
        ]


class ContentModelAdapter:
    name = "content"

    def recommend(self, user_id: int, context: InferenceContext, top_k: int) -> list[InferenceCandidate]:
        if context.read_cached_csv is None or context.offline_movie_profile_path is None:
            return []
        profiles, _ = context.read_cached_csv(context.offline_movie_profile_path, None)
        if "movieId" not in profiles.columns:
            return []
        favorite_terms = _favorite_terms(user_id, context)
        working = profiles.copy()
        working["movieId"] = pd.to_numeric(working["movieId"], errors="coerce")
        working = working.dropna(subset=["movieId"]).copy()
        if working.empty:
            return []

        text_columns = [col for col in ["title", "clean_title", "genres", "tag_text", "ingredients"] if col in working.columns]
        if text_columns and favorite_terms:
            texts = working[text_columns].fillna("").astype(str).agg(" ".join, axis=1)
            content_scores = texts.map(lambda value: _term_overlap_score(value, favorite_terms)).to_numpy(dtype=float)
        else:
            content_scores = np.zeros(len(working), dtype=float)

        rating = _normalized_numeric(working, ["rating_value", "movie_avg_rating", "avg_rating"])
        popularity = _normalized_numeric(working, ["movie_popularity", "popularity", "movie_rating_count"])
        image = _has_image_score(working)
        if favorite_terms:
            score = 0.55 * content_scores + 0.25 * rating + 0.15 * popularity + 0.05 * image
        else:
            score = 0.45 * rating + 0.40 * popularity + 0.15 * image
        working["_content_score"] = score
        records = working.sort_values(["_content_score", "movieId"], ascending=[False, True]).head(top_k).to_dict(orient="records")
        return [
            InferenceCandidate(
                recipe_id=int(record["movieId"]),
                score=float(record.get("_content_score") or 0.0),
                source=self.name,
                reason="content profile match",
                metadata=_jsonish_record(record),
            )
            for record in records
        ]


class HotModelAdapter:
    name = "hot"

    def recommend(self, user_id: int, context: InferenceContext, top_k: int) -> list[InferenceCandidate]:
        if context.popular_recipe_records is not None:
            records, _ = context.popular_recipe_records(top_k)
            return [
                InferenceCandidate(
                    recipe_id=int(record["movie_id"]),
                    score=float(record.get("score") or 0.0),
                    source=self.name,
                    reason="popular recipe fallback",
                    metadata=dict(record),
                )
                for record in records
            ]
        if context.pipeline is None:
            return []
        rows = context.pipeline.get_popular_movies(top_k)
        return [_candidate_from_mapping(row, self.name, "popular recipe fallback") for row in rows]


def _candidate_from_mapping(row: dict, source: str, reason: str) -> InferenceCandidate:
    recipe_id = row.get("recipe_id", row.get("movie_id", row.get("movieId")))
    return InferenceCandidate(
        recipe_id=int(recipe_id),
        score=float(row.get("score", row.get("rank_score", row.get("popularity_score", 0.0))) or 0.0),
        source=source,
        reason=reason,
        metadata=_jsonish_record(row),
    )


def _favorite_terms(user_id: int, context: InferenceContext) -> set[str]:
    if context.read_cached_csv is None or context.offline_user_profile_path is None:
        return set()
    try:
        users, _ = context.read_cached_csv(context.offline_user_profile_path, None)
    except Exception:
        return set()
    if "userId" not in users.columns:
        return set()
    working = users.copy()
    working["userId"] = pd.to_numeric(working["userId"], errors="coerce")
    rows = working[working["userId"] == user_id]
    if rows.empty:
        return set()
    first = rows.iloc[0].to_dict()
    values = [
        first.get("favorite_genres"),
        first.get("preferred_tags"),
        first.get("high_rating_tags"),
    ]
    return _token_set(value for value in values if value is not None)


def _token_set(values: Iterable[object]) -> set[str]:
    tokens: set[str] = set()
    for value in values:
        text = str(value or "").lower()
        tokens.update(part.strip() for part in re.split(r"[|,;/\s]+", text) if part.strip())
    return tokens


def _term_overlap_score(value: object, terms: set[str]) -> float:
    tokens = _token_set([value])
    if not tokens or not terms:
        return 0.0
    return len(tokens & terms) / max(len(terms), 1)


def _normalized_numeric(df: pd.DataFrame, columns: list[str]) -> np.ndarray:
    col = _first_existing_column(df, columns)
    if not col:
        return np.zeros(len(df), dtype=float)
    values = pd.to_numeric(df[col], errors="coerce").fillna(0.0).to_numpy(dtype=float)
    values = np.nan_to_num(values, nan=0.0, posinf=0.0, neginf=0.0)
    low = float(values.min()) if len(values) else 0.0
    high = float(values.max()) if len(values) else 0.0
    if high <= low:
        return np.ones(len(df), dtype=float) if len(df) else values
    return (values - low) / (high - low)


def _has_image_score(df: pd.DataFrame) -> np.ndarray:
    if "image_url" not in df.columns:
        return np.zeros(len(df), dtype=float)
    return (df["image_url"].fillna("").astype(str).str.len() > 0).astype(float).to_numpy(dtype=float)


def _first_existing_column(df: pd.DataFrame, columns: list[str]) -> str | None:
    for column in columns:
        if column in df.columns:
            return column
    return None


def _float_from_record(record: dict, keys: list[str], default: float = 0.0) -> float:
    for key in keys:
        value = record.get(key)
        if value is not None and not pd.isna(value):
            return float(value)
    return default


def _jsonish_record(record: dict) -> dict:
    safe = {}
    for key, value in dict(record).items():
        if value is None:
            safe[key] = None
        elif isinstance(value, float) and math.isnan(value):
            safe[key] = None
        elif hasattr(value, "item"):
            safe[key] = value.item()
        else:
            safe[key] = value
    return safe
