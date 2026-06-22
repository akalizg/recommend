from __future__ import annotations

import logging
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

from recommendation.inference_schemas import (
    BaseInferenceModel,
    InferenceContext,
    ModelInferenceResult,
    ParallelInferenceResponse,
)
from recommendation.result_reducer import ResultReducer

logger = logging.getLogger(__name__)


class ParallelInferenceService:
    def __init__(
        self,
        models: list[BaseInferenceModel],
        reducer: ResultReducer | None = None,
        max_workers: int = 4,
        model_timeout_ms: int = 800,
        overall_timeout_ms: int = 1500,
    ):
        self.models = list(models)
        self.reducer = reducer or ResultReducer()
        self.max_workers = max(1, int(max_workers))
        self.model_timeout_ms = max(1, int(model_timeout_ms))
        self.overall_timeout_ms = max(self.model_timeout_ms, int(overall_timeout_ms))

    def recommend(self, user_id: int, context: InferenceContext, top_k: int) -> ParallelInferenceResponse:
        t0 = time.perf_counter()
        model_results: list[ModelInferenceResult] = []
        if not self.models:
            reduced, reduce_ms = self.reducer.reduce([], top_k)
            return ParallelInferenceResponse(reduced, [], reduce_ms, (time.perf_counter() - t0) * 1000)

        executor = ThreadPoolExecutor(max_workers=min(self.max_workers, len(self.models)), thread_name_prefix="parallel-rec")
        future_to_model = {}
        start_times = {}
        pending = set()
        try:
            for model in self.models:
                future = executor.submit(self._run_model, model, user_id, context, top_k)
                future_to_model[future] = model.name
                start_times[future] = time.perf_counter()
                pending.add(future)

            deadline = t0 + self.overall_timeout_ms / 1000.0
            while pending:
                now = time.perf_counter()
                if now >= deadline:
                    break
                done, pending = wait(pending, timeout=min(0.05, max(0.0, deadline - now)), return_when=FIRST_COMPLETED)
                for future in done:
                    model_results.append(self._future_result(future, future_to_model[future]))

                now = time.perf_counter()
                timed_out = [
                    future
                    for future in pending
                    if (now - start_times[future]) * 1000 >= self.model_timeout_ms
                ]
                for future in timed_out:
                    pending.remove(future)
                    future.cancel()
                    model_results.append(
                        ModelInferenceResult(
                            model_name=future_to_model[future],
                            status="timeout",
                            duration_ms=round((now - start_times[future]) * 1000, 2),
                            error=f"model timeout after {self.model_timeout_ms}ms",
                        )
                    )

            for future in list(pending):
                future.cancel()
                model_results.append(
                    ModelInferenceResult(
                        model_name=future_to_model[future],
                        status="timeout",
                        duration_ms=round((time.perf_counter() - start_times[future]) * 1000, 2),
                        error=f"overall timeout after {self.overall_timeout_ms}ms",
                    )
                )
        finally:
            for future in pending:
                future.cancel()
            executor.shutdown(wait=False)

        reduced, reduce_ms = self.reducer.reduce(model_results, top_k)
        took_ms = (time.perf_counter() - t0) * 1000
        return ParallelInferenceResponse(
            recommendations=reduced,
            model_results=model_results,
            reduce_duration_ms=round(reduce_ms, 2),
            took_ms=round(took_ms, 2),
        )

    @staticmethod
    def _run_model(
        model: BaseInferenceModel,
        user_id: int,
        context: InferenceContext,
        top_k: int,
    ) -> ModelInferenceResult:
        t0 = time.perf_counter()
        try:
            candidates = model.recommend(user_id, context, top_k)
            return ModelInferenceResult(
                model_name=model.name,
                candidates=candidates,
                status="success",
                duration_ms=round((time.perf_counter() - t0) * 1000, 2),
            )
        except Exception as exc:
            logger.warning("Parallel inference model %s failed: %s", model.name, exc, exc_info=True)
            return ModelInferenceResult(
                model_name=model.name,
                status="error",
                duration_ms=round((time.perf_counter() - t0) * 1000, 2),
                error=str(exc),
            )

    @staticmethod
    def _future_result(future, model_name: str) -> ModelInferenceResult:
        try:
            return future.result()
        except Exception as exc:
            return ModelInferenceResult(model_name=model_name, status="error", error=str(exc))
