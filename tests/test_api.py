"""
API integration tests using FastAPI TestClient.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient


# We need to mock the services to avoid real data loading
class MockPipeline:
    def get_movie_info(self, movie_id):
        return {
            "movie_id": movie_id,
            "title": f"Test Movie {movie_id}",
            "genres": "Action|Comedy",
            "avg_rating": 3.5,
            "rating_count": 100,
            "popularity_score": 4.0,
            "year": 2000,
        }

    def get_popular_movies(self, n=50):
        return [self.get_movie_info(i) for i in range(1, n + 1)]

    def get_user_history(self, uid):
        import pandas as pd
        return pd.DataFrame(columns=["userId", "movieId", "rating"])

    @property
    def movies(self):
        import pandas as pd
        return pd.DataFrame({
            "movieId": [1, 2, 3],
            "title": ["Toy Story (1995)", "Jumanji (1995)", "Test Movie (2000)"],
            "genres": ["Animation|Comedy", "Adventure|Fantasy", "Action"],
            "avg_rating": [4.0, 3.5, 3.0],
            "rating_count": [200, 150, 100],
            "popularity_score": [4.5, 4.0, 3.5],
            "year": [1995, 1995, 2000],
        })

    def parse_genres(self):
        return ["Action", "Adventure", "Animation", "Comedy", "Fantasy"]


class MockRecallService:
    def recall(self, user_id, k=None):
        return [
            {"movie_id": 1, "score": 0.95},
            {"movie_id": 2, "score": 0.90},
            {"movie_id": 3, "score": 0.85},
        ]


class MockRankingService:
    def rank(self, user_id, candidates, top_k=None):
        return [
            {"movie_id": 1, "score": 0.98, "recall_score": 0.95},
            {"movie_id": 2, "score": 0.92, "recall_score": 0.90},
            {"movie_id": 3, "score": 0.87, "recall_score": 0.85},
        ]


class MockUserProfileBuilder:
    def build_profile(self, user_id):
        return {
            "user_id": user_id,
            "avg_rating": 3.8,
            "rating_count": 50,
            "rating_std": 0.8,
            "activity_level": "medium",
            "top_genres": [{"genre": "Action", "score": 0.8}],
            "top_rated_movies": [],
            "recent_ratings": [],
        }


@pytest.fixture
def client():
    from app.main import create_app
    from api.routes import _app_state

    # Wire mock services
    _app_state.pipeline = MockPipeline()
    _app_state.recall_service = MockRecallService()
    _app_state.ranking_service = MockRankingService()
    _app_state.user_profile_builder = MockUserProfileBuilder()
    _app_state.cache = None
    _app_state.faiss_index = None
    _app_state.embedding_service = None

    app = create_app()
    return TestClient(app)


class TestAPIEndpoints:

    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_recommend(self, client):
        resp = client.get("/recommend/1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == 1
        assert len(data["recommendations"]) == 3
        assert data["recommendations"][0]["movie_id"] == 1
        assert "took_ms" in data

    def test_recommend_with_topk(self, client):
        resp = client.get("/recommend/1?top_k=2")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["recommendations"]) == 2

    def test_popular(self, client):
        resp = client.get("/popular?limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["popular"]) == 10

    def test_movie_detail(self, client):
        resp = client.get("/movie/1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["movie_id"] == 1
        assert data["title"] == "Test Movie 1"

    def test_movie_not_found(self, client):
        resp = client.get("/movie/99999")
        assert resp.status_code == 200  # Mock always returns data

    def test_user_profile(self, client):
        resp = client.get("/user/1/profile")
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == 1
        assert data["activity_level"] == "medium"

    def test_search(self, client):
        resp = client.get("/search?q=Toy")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) >= 1
        assert data["results"][0]["title"] == "Toy Story (1995)"

    def test_rebuild_index(self, client):
        resp = client.post("/rebuild-index")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
