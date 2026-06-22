import time

from recommendation.inference_schemas import InferenceCandidate, InferenceContext
from recommendation.parallel_inference import ParallelInferenceService
from recommendation.result_reducer import ResultReducer


class SlowModel:
    name = "slow"

    def recommend(self, user_id, context, top_k):
        time.sleep(0.2)
        return [InferenceCandidate(recipe_id=99, score=1.0, source=self.name)]


class FixedModel:
    def __init__(self, name, recipe_id, delay=0.0):
        self.name = name
        self.recipe_id = recipe_id
        self.delay = delay

    def recommend(self, user_id, context, top_k):
        if self.delay:
            time.sleep(self.delay)
        return [InferenceCandidate(recipe_id=self.recipe_id, score=1.0, source=self.name)]


class ErrorModel:
    name = "error"

    def recommend(self, user_id, context, top_k):
        raise RuntimeError("boom")


def test_parallel_inference_runs_models_concurrently():
    service = ParallelInferenceService(
        models=[
            FixedModel("als", 1, delay=0.15),
            FixedModel("itemcf", 2, delay=0.15),
        ],
        reducer=ResultReducer(model_weights={"als": 1.0, "itemcf": 1.0}),
        max_workers=2,
        model_timeout_ms=500,
        overall_timeout_ms=800,
    )

    started = time.perf_counter()
    response = service.recommend(1, InferenceContext(), top_k=2)
    elapsed = time.perf_counter() - started

    assert elapsed < 0.25
    assert {item.recipe_id for item in response.recommendations} == {1, 2}
    assert all(result.status == "success" for result in response.model_results)


def test_parallel_inference_isolates_errors_and_timeouts():
    service = ParallelInferenceService(
        models=[FixedModel("als", 1), ErrorModel(), SlowModel()],
        reducer=ResultReducer(model_weights={"als": 1.0}),
        max_workers=3,
        model_timeout_ms=50,
        overall_timeout_ms=100,
    )

    response = service.recommend(1, InferenceContext(), top_k=3)
    statuses = {result.model_name: result.status for result in response.model_results}

    assert response.recommendations[0].recipe_id == 1
    assert statuses["als"] == "success"
    assert statuses["error"] == "error"
    assert statuses["slow"] == "timeout"
