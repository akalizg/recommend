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
            "title": f"Test Recipe {movie_id}",
            "genres": "Dinner|Quick",
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
            "title": ["Chicken Soup", "Apple Pie", "Test Recipe"],
            "genres": ["Soup|Dinner", "Dessert|Baking", "Quick"],
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
        self.exposures = []

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

    def record_exposure(self, **kwargs):
        self.exposures.append(kwargs)
        return {
            "event_id": len(self.exposures),
            "user_id": kwargs["user_id"],
            "movie_id": kwargs["movie_id"],
            "event_type": "exposure",
            "created_at": "2026-01-01T00:00:00+00:00",
        }


class MockABService:
    def assign_group(self, user_id, experiment_name="recall_rank_v1"):
        return {"experiment_name": experiment_name, "group_name": "A"}

    def metrics(self, experiment_name="recall_rank_v1"):
        return {"experiment_name": experiment_name, "groups": [{"group_name": "A", "events": 1}]}


@pytest.fixture
def client(tmp_path, monkeypatch):
    from app.main import create_app
    from api import routes
    from api.routes import _app_state
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "elasticsearch_enabled", False)
    recs = tmp_path / "recommendations_with_reasons.csv"
    recs.write_text(
        "userId,movieId,rank_position,rank_score,mmr_score,movie_title,movie_genres,"
        "favorite_genres,final_reason,reason_source,reason_evidence,image_url,ready_in_display,"
        "recipe_yield_raw,author_name\n"
        "1,10,1,0.9,0.8,Chicken Soup,Soup|Dinner,Dinner,Good match,template,"
        "\"{\"\"rank_position\"\": 1}\",https://example.com/soup.jpg,30 mins,4 servings,Chef A\n"
        "1,11,2,0.8,0.7,Apple Pie,Dessert|Baking,Dessert,Sweet match,template,"
        "\"{\"\"rank_position\"\": 2}\",https://example.com/pie.jpg,60 mins,8 servings,Chef B\n",
        encoding="utf-8",
    )
    movies = tmp_path / "movie_profile.csv"
    movies.write_text(
        "movieId,title,clean_title,genres,movie_avg_rating,movie_rating_count,movie_popularity,"
        "image_url,ready_in_display,recipe_yield_raw,author_name,description\n"
        "10,Chicken Soup,Chicken Soup,Soup|Dinner,4.1,200,90,https://example.com/soup.jpg,"
        "30 mins,4 servings,Chef A,Cozy chicken soup\n"
        "11,Apple Pie,Apple Pie,Dessert|Baking,4.4,150,80,https://example.com/pie.jpg,"
        "60 mins,8 servings,Chef B,Classic apple pie\n"
        "12,Chicken Stew,Chicken Stew,Stew|Dinner,4.2,120,70,https://example.com/stew.jpg,"
        "45 mins,6 servings,Chef C,Rich chicken stew\n",
        encoding="utf-8",
    )
    detail = tmp_path / "recipe_detail_metadata.csv"
    detail.write_text(
        "recipe_id,ingredients_json,quantities_json,steps_json,nutrition_json,source_url\n"
        "10,\"[\"\"chicken\"\"]\",\"[\"\"1 lb\"\"]\",\"[\"\"Simmer\"\"]\",\"{\"\"calories\"\": 250}\","
        "https://www.food.com/recipe/chicken-soup-10\n",
        encoding="utf-8",
    )
    metadata = tmp_path / "recipe_metadata.csv"
    metadata.write_text(
        "recipe_id,minutes,n_steps,n_ingredients,ingredients,calories,total_fat_pct,sugar_pct,sodium_pct,"
        "protein_pct,saturated_fat_pct,carbohydrates_pct\n"
        "10,30,5,6,chicken|salt|onion,250,8,4,15,65,4,12\n"
        "11,60,8,5,apple|sugar|butter,520,20,70,25,8,12,65\n"
        "12,45,7,7,chicken|potato|onion,360,14,6,18,55,8,20\n",
        encoding="utf-8",
    )
    users = tmp_path / "user_profile.csv"
    users.write_text(
        "userId,user_rating_count,user_avg_rating,favorite_genres\n"
        "1,12,4.2,Soup|Dinner\n",
        encoding="utf-8",
    )
    ingredient_translation = tmp_path / "ingredient_frequency_translated.tsv"
    ingredient_translation.write_text(
        "ingredient\tcount\ttranslated_ingredient\n"
        "chicken\t2\t鸡肉\n"
        "onion\t2\t洋葱\n"
        "apple\t1\t苹果\n"
        "potato\t1\t土豆\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(routes, "OFFLINE_RECOMMENDATIONS_PATH", recs)
    monkeypatch.setattr(routes, "OFFLINE_MOVIE_PROFILE_PATH", movies)
    monkeypatch.setattr(routes, "OFFLINE_RECIPE_DETAIL_PATH", detail)
    monkeypatch.setattr(routes, "OFFLINE_RECIPE_METADATA_PATH", metadata)
    monkeypatch.setattr(routes, "OFFLINE_INGREDIENT_TRANSLATION_PATH", ingredient_translation)
    monkeypatch.setattr(routes, "OFFLINE_USER_PROFILE_PATH", users)
    monkeypatch.setattr(get_settings(), "auth_db_path", str(tmp_path / "auth_users.db"))
    routes._faiss_similarity_cache.clear()
    routes._ingredient_map_cache.clear()

    # Wire mock services
    _app_state.pipeline = MockPipeline()
    _app_state.recall_service = MockRecallService()
    _app_state.ranking_service = MockRankingService()
    _app_state.user_profile_builder = MockUserProfileBuilder()
    _app_state.cache = None
    _app_state.faiss_index = None
    _app_state.embedding_service = None
    _app_state.feedback_service = MockFeedbackService()
    _app_state.ab_service = MockABService()

    app = create_app()
    return TestClient(app)


class TestAPIEndpoints:

    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_auth_register_and_login(self, client):
        register_resp = client.post(
            "/auth/register",
            json={
                "username": "demo_user",
                "password": "secret123",
                "display_name": "Demo User",
                "recipe_user_id": 1,
            },
        )
        assert register_resp.status_code == 200
        registered = register_resp.json()
        assert registered["username"] == "demo_user"
        assert registered["user_id"] == 1
        assert registered["recipe_user_id"] == 1

        login_resp = client.post(
            "/auth/login",
            json={"username": "demo_user", "password": "secret123"},
        )
        assert login_resp.status_code == 200
        logged_in = login_resp.json()
        assert logged_in["account_id"] == registered["account_id"]
        assert logged_in["display_name"] == "Demo User"

        bad_resp = client.post(
            "/auth/login",
            json={"username": "demo_user", "password": "wrong123"},
        )
        assert bad_resp.status_code == 401

    def test_recommend(self, client):
        resp = client.get("/recommend/1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == 1
        assert len(data["recommendations"]) == 2
        assert data["recommendations"][0]["movie_id"] == 10
        assert "took_ms" in data

    def test_recommend_with_topk(self, client):
        resp = client.get("/recommend/1?top_k=2")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["recommendations"]) == 2

    def test_recommend_prefers_realtime_cache(self, client):
        from api.routes import _app_state

        class LocalCache:
            settings = type("Settings", (), {"redis_ttl_recommend": 600})()

            def get_json(self, key):
                if key == "recipe:realtime_rec:user:1:k:2":
                    return {
                        "user_id": 1,
                        "recommendations": [
                            {
                                "movie_id": 99,
                                "title": "Realtime Soup",
                                "score": 1.23,
                                "genres": "Soup",
                            }
                        ],
                        "cached": False,
                        "took_ms": 0.0,
                        "source": "test",
                    }
                return None

            def set_json(self, *args, **kwargs):
                return True

        _app_state.cache = LocalCache()
        resp = client.get("/recommend/1?top_k=2")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cached"] is True
        assert data["recommendations"][0]["movie_id"] == 99

    def test_popular(self, client):
        resp = client.get("/popular?limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["popular"]) == 3

    def test_movie_detail(self, client):
        resp = client.get("/movie/10")
        assert resp.status_code == 200
        data = resp.json()
        assert data["movie_id"] == 10
        assert data["title"]

    def test_similar_recipes(self, client, tmp_path, monkeypatch):
        import faiss
        import numpy as np
        from api import routes

        vectors = np.array(
            [
                [1.0, 0.0, 0.0],
                [0.95, 0.05, 0.0],
                [0.8, 0.2, 0.0],
            ],
            dtype="float32",
        )
        ids = np.array([10, 11, 12], dtype="int64")
        index = faiss.IndexHNSWFlat(3, 8, faiss.METRIC_INNER_PRODUCT)
        index.add(vectors)
        index_path = tmp_path / "faiss.index"
        index_ids = tmp_path / "faiss_ids.npy"
        vector_path = tmp_path / "vectors.npy"
        vector_ids = tmp_path / "vector_ids.npy"
        faiss.write_index(index, str(index_path))
        np.save(index_ids, ids)
        np.save(vector_path, vectors)
        np.save(vector_ids, ids)

        monkeypatch.setattr(routes, "FAISS_HNSW_SPARK_INDEX_PATH", index_path)
        monkeypatch.setattr(routes, "FAISS_HNSW_SPARK_IDS_PATH", index_ids)
        monkeypatch.setattr(routes, "FAISS_SPARK_VECTORS_PATH", vector_path)
        monkeypatch.setattr(routes, "FAISS_SPARK_VECTOR_IDS_PATH", vector_ids)
        routes._faiss_similarity_cache.clear()

        resp = client.get("/recipe/10/similar?limit=2")
        assert resp.status_code == 200
        data = resp.json()
        assert data["movie_id"] == 10
        assert data["total"] == 2
        assert [item["movie_id"] for item in data["similar"]] == [11, 12]

    def test_movie_not_found(self, client):
        resp = client.get("/movie/99999")
        assert resp.status_code == 404

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

    def test_ab_and_metrics(self, client):
        group_resp = client.get("/ab/group/1")
        assert group_resp.status_code == 200
        assert group_resp.json()["group_name"] == "A"

        metrics_resp = client.get("/ab/metrics")
        assert metrics_resp.status_code == 200
        assert metrics_resp.json()["groups"][0]["group_name"] == "A"

        prom_resp = client.get("/metrics")
        assert prom_resp.status_code == 200
        assert "reciperec_up 1" in prom_resp.text

    def test_search(self, client):
        resp = client.get("/search?q=Chicken")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) >= 1
        assert "Chicken" in data["results"][0]["title"]

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
            "1,10,1,0.9,0.8,Chicken Soup,Soup|Dinner,Dinner,Good match,template,"
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

    def test_scenario_personalized_recommendations(self, client):
        resp = client.post(
            "/recipes/scenario-recommend",
            json={"scenario": "personalized", "user_id": 1, "limit": 2},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["scenario"] == "personalized"
        assert data["context"]["mode"] == "offline_lightgbm_mmr"
        assert [item["movie_id"] for item in data["recommendations"]] == [10, 11]

    def test_scenario_ingredient_recommendations(self, client):
        resp = client.post(
            "/recipes/scenario-recommend",
            json={
                "scenario": "ingredients",
                "ingredients": ["鸡肉"],
                "require_image": False,
                "limit": 2,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["scenario"] == "ingredients"
        assert data["context"]["mode"] == "content_cold_start"
        assert data["context"]["preference_profile"]["ingredients"] == ["chicken"]
        assert data["recommendations"][0]["movie_id"] in {10, 12}

    def test_recipe_ingredients(self, client):
        resp = client.get("/recipes/ingredients?q=chick&limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert data["query"] == "chick"
        assert data["total"] >= len(data["ingredients"])
        assert 0 < len(data["ingredients"]) <= 5
        assert all("chick" in item["name"] for item in data["ingredients"])

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
            "10,Chicken Soup,Soup|Dinner,4.1,200\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(routes, "OFFLINE_USER_PROFILE_PATH", users)
        monkeypatch.setattr(routes, "OFFLINE_MOVIE_PROFILE_PATH", movies)

        user_resp = client.get("/offline/user-profile/1")
        assert user_resp.status_code == 200
        assert user_resp.json()["profile"]["favorite_genres"] == "Comedy|Drama"

        movie_resp = client.get("/offline/movie-profile/10")
        assert movie_resp.status_code == 200
        assert movie_resp.json()["profile"]["title"] == "Chicken Soup"
