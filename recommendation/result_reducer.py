from __future__ import annotations

import time
from collections import defaultdict

from recommendation.inference_schemas import InferenceCandidate, ModelInferenceResult, ReducedRecommendation


DEFAULT_MODEL_WEIGHTS = {
    "als": 0.30,
    "itemcf": 0.25,
    "content": 0.20,
    "ranker": 0.15,
    "hot": 0.10,
    "kg": 0.10,
}


class ResultReducer:
    def __init__(self, model_weights: dict[str, float] | None = None, source_bonus: float = 0.05):
        self.model_weights = dict(model_weights or DEFAULT_MODEL_WEIGHTS)
        self.source_bonus = float(source_bonus)

    def reduce(self, model_results: list[ModelInferenceResult], top_k: int) -> tuple[list[ReducedRecommendation], float]:
        t0 = time.perf_counter()
        successful = [result for result in model_results if result.status == "success" and result.candidates]
        normalized_by_model = {
            result.model_name: self._normalize(result.candidates)
            for result in successful
        }

        merged: dict[int, dict] = defaultdict(lambda: {"score": 0.0, "sources": [], "reasons": [], "metadata": {}})
        for result in successful:
            weight = float(self.model_weights.get(result.model_name, 0.05))
            for candidate, normalized_score in normalized_by_model[result.model_name]:
                bucket = merged[int(candidate.recipe_id)]
                bucket["score"] += normalized_score * weight
                if candidate.source not in bucket["sources"]:
                    bucket["sources"].append(candidate.source)
                if candidate.reason:
                    bucket["reasons"].append(candidate.reason)
                if candidate.metadata and not bucket["metadata"]:
                    bucket["metadata"] = candidate.metadata

        reduced: list[ReducedRecommendation] = []
        for recipe_id, bucket in merged.items():
            source_count = len(bucket["sources"])
            final_score = float(bucket["score"]) + max(0, source_count - 1) * self.source_bonus
            reduced.append(
                ReducedRecommendation(
                    recipe_id=recipe_id,
                    final_score=round(final_score, 6),
                    sources=sorted(bucket["sources"]),
                    source_count=source_count,
                    reason=self._merge_reasons(bucket["reasons"]),
                    metadata=bucket["metadata"],
                )
            )
        reduced.sort(key=lambda item: (-item.final_score, -item.source_count, item.recipe_id))
        elapsed_ms = (time.perf_counter() - t0) * 1000
        return reduced[:top_k], elapsed_ms

    @staticmethod
    def _normalize(candidates: list[InferenceCandidate]) -> list[tuple[InferenceCandidate, float]]:
        scores = [float(candidate.score or 0.0) for candidate in candidates]
        if not scores:
            return []
        low = min(scores)
        high = max(scores)
        if high <= low:
            return [(candidate, 1.0) for candidate in candidates]
        return [(candidate, (float(candidate.score or 0.0) - low) / (high - low)) for candidate in candidates]

    @staticmethod
    def _merge_reasons(reasons: list[str]) -> str:
        seen: list[str] = []
        for reason in reasons:
            if reason and reason not in seen:
                seen.append(reason)
        return " + ".join(seen[:3])
