from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol

import pandas as pd


class BaseInferenceModel(Protocol):
    name: str

    def recommend(self, user_id: int, context: "InferenceContext", top_k: int) -> list["InferenceCandidate"]:
        ...


@dataclass
class InferenceCandidate:
    recipe_id: int
    score: float
    source: str
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelInferenceResult:
    model_name: str
    candidates: list[InferenceCandidate] = field(default_factory=list)
    status: str = "success"
    duration_ms: float = 0.0
    error: str = ""


@dataclass
class ReducedRecommendation:
    recipe_id: int
    final_score: float
    sources: list[str]
    source_count: int
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParallelInferenceResponse:
    recommendations: list[ReducedRecommendation]
    model_results: list[ModelInferenceResult]
    reduce_duration_ms: float
    took_ms: float
    source: str = "parallel_inference"


@dataclass
class InferenceContext:
    recall_service: Any = None
    ranking_service: Any = None
    pipeline: Any = None
    read_cached_csv: Callable[[Path, Path | None], tuple[pd.DataFrame, Path]] | None = None
    popular_recipe_records: Callable[[int], tuple[list[dict], Path]] | None = None
    offline_recommendations_path: Path | None = None
    offline_movie_profile_path: Path | None = None
    offline_user_profile_path: Path | None = None
