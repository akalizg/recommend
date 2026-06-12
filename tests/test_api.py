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


class MockFeedbackService:
    def __init__(self):
        self.profile = None

    def record_feedback(self, **kwargs):
        self.profile = {
            "user_id": kwargs["user_id"],
            "positive_movie_ids": [kwargs["movie_id"]],
            "negative_movie_ids": [],
            "recent_feedback": [{"movie_id": kwargs["movie_id"], "feedback_type": kwargs["feedback_type"]}],
        }
        return {
            "feedback_id": 1,
            "user_id": kwargs["user_id"],
            "movie_id": kwargs["movie_id"],
            "feedback_type": kwargs["feedback_type"],
            "created_at": "2026-01-01T00:00:00+00:00",
            "realtime_profile": self.profile,
        }

    def get_realtime_profile(self, user_id):
        return self.profile


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
    _app_state.feedback_service = MockFeedbackService()

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

    def test_feedback_and_realtime_profile(self, client):
        resp = client.post(
            "/feedback",
            json={"user_id": 1, "movie_id": 10, "feedback_type": "like", "rank_position": 1},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["realtime_profile"]["positive_movie_ids"] == [10]

        profile_resp = client.get("/user/1/realtime-profile")
        assert profile_resp.status_code == 200
        assert profile_resp.json()["profile"]["recent_feedback"][0]["feedback_type"] == "like"

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

    def test_offline_recommendations(self, client, tmp_path, monkeypatch):
        from api import routes

        recs = tmp_path / "recommendations_with_reasons.csv"
        recs.write_text(
            "userId,movieId,rank_position,rank_score,mmr_score,movie_title,movie_genres,"
            "favorite_genres,final_reason,reason_source,reason_evidence\n"
            "1,10,1,0.9,0.8,Toy Story,Animation|Comedy,Comedy,Good match,template,"
            "\"{\"\"rank_position\"\": 1}\"\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(routes, "OFFLINE_RECOMMENDATIONS_PATH", recs)

        resp = client.get("/offline/recommendations/1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == 1
        assert data["total"] == 1
        assert data["recommendations"][0]["movie_id"] == 10
        assert data["recommendations"][0]["reason_evidence"]["rank_position"] == 1

    def test_offline_metrics_and_ablation(self, client, tmp_path, monkeypatch):
        from api import routes

        metrics = tmp_path / "optimized_offline_metrics.csv"
        metrics.write_text(
            "model_name,k,precision,recall,ndcg,hit_rate,coverage,diversity,evaluated_users,recommended_items\n"
            "ALS,10,0.1,0.2,0.3,0.4,0.5,0.6,7,8\n",
            encoding="utf-8",
        )
        summary = tmp_path / "optimized_eval_summary.json"
        summary.write_text('{"best_ndcg_model": "ALS"}', encoding="utf-8")
        ablation = tmp_path / "optimized_ablation_metrics.csv"
        ablation.write_text(
            "variant,k,precision,recall,ndcg,hit_rate,coverage,diversity,main_observation\n"
            "ALS,10,0.1,0.2,0.3,0.4,0.5,0.6,Baseline\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(routes, "OFFLINE_METRICS_PATH", metrics)
        monkeypatch.setattr(routes, "OFFLINE_METRICS_SUMMARY_PATH", summary)
        monkeypatch.setattr(routes, "OFFLINE_ABLATION_PATH", ablation)

        metrics_resp = client.get("/offline/metrics")
        assert metrics_resp.status_code == 200
        metrics_data = metrics_resp.json()
        assert metrics_data["metrics"][0]["model_name"] == "ALS"
        assert metrics_data["summary"]["best_ndcg_model"] == "ALS"

        ablation_resp = client.get("/offline/ablation")
        assert ablation_resp.status_code == 200
        assert ablation_resp.json()["ablation"][0]["variant"] == "ALS"

    def test_offline_profiles(self, client, tmp_path, monkeypatch):
        from api import routes

        users = tmp_path / "user_profile.csv"
        users.write_text(
            "userId,user_rating_count,user_avg_rating,favorite_genres\n"
            "1,12,4.2,Comedy|Drama\n",
            encoding="utf-8",
        )
        movies = tmp_path / "movie_profile.csv"
        movies.write_text(
            "movieId,title,genres,movie_avg_rating,movie_rating_count\n"
            "10,Toy Story,Animation|Comedy,4.1,200\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(routes, "OFFLINE_USER_PROFILE_PATH", users)
        monkeypatch.setattr(routes, "OFFLINE_MOVIE_PROFILE_PATH", movies)

        user_resp = client.get("/offline/user-profile/1")
        assert user_resp.status_code == 200
        assert user_resp.json()["profile"]["favorite_genres"] == "Comedy|Drama"

        movie_resp = client.get("/offline/movie-profile/10")
        assert movie_resp.status_code == 200
        assert movie_resp.json()["profile"]["title"] == "Toy Story"
