"""
Centralized configuration management using pydantic-settings.
Loads from .env file and environment variables.
"""
from pathlib import Path
from pydantic import field_validator
from pydantic_settings import BaseSettings
from functools import lru_cache

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # Application
    app_name: str = "RecipeRecommend"
    app_version: str = "1.0.0"
    debug: bool = True
    log_level: str = "INFO"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ""
    redis_max_connections: int = 50

    # Redis TTL (seconds)
    redis_ttl_user_profile: int = 3600
    redis_ttl_recommend: int = 1800
    redis_ttl_popular: int = 600
    redis_ttl_topk: int = 300

    # FAISS Index
    faiss_index_path: str = str(PROJECT_ROOT / "models" / "faiss_hnsw.index")
    faiss_dimension: int = 64
    faiss_m: int = 32
    faiss_ef_construction: int = 200
    faiss_ef_search: int = 64

    # HNSW
    hnsw_m: int = 32
    hnsw_ef_construction: int = 200
    hnsw_ef_search: int = 64

    # Embedding
    embedding_dim: int = 64
    embedding_model_path: str = str(PROJECT_ROOT / "models" / "embeddings.npz")

    # Ranking
    rank_model_path: str = str(PROJECT_ROOT / "models" / "xgb_rank_model.json")
    rank_top_k: int = 100

    # Feature
    feature_cache_path: str = str(PROJECT_ROOT / "models" / "features.pkl")

    # Data
    foodcom_data_dir: str = str(PROJECT_ROOT / "data" / "food-com")
    canonical_data_dir: str = str(PROJECT_ROOT / "data" / "recipe-canonical")
    recommendation_db_path: str = str(PROJECT_ROOT / "data" / "recommendations.db")
    auth_db_path: str = str(PROJECT_ROOT / "data" / "auth_users.db")

    # Elasticsearch
    elasticsearch_url: str = "http://localhost:9200"
    elasticsearch_index_recipes: str = "recipes"
    elasticsearch_enabled: bool = True
    elasticsearch_timeout_seconds: float = 2.0

    # Spark
    spark_master_url: str = "spark://192.168.88.161:7077"
    spark_driver_memory: str = "1g"
    spark_executor_memory: str = "1g"
    spark_executor_cores: str = "1"
    spark_executor_instances: str = "3"
    spark_sql_shuffle_partitions: int = 12
    spark_default_parallelism: int = 12
    spark_ui_show_console_progress: bool = False

    # Kafka
    kafka_enabled: bool = True
    kafka_bootstrap_servers: str = "node1:9092"
    kafka_feedback_topic: str = "recipe_feedback"
    kafka_realtime_recommend_topic: str = "recipe_realtime_recommend"
    kafka_client_id: str = "reciperec-api"
    kafka_consumer_group: str = "reciperec-feedback-consumer"
    kafka_request_timeout_ms: int = 3000

    # MinIO artifact storage
    minio_enabled: bool = True
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_secure: bool = False
    minio_bucket: str = "reciperec"
    minio_artifact_prefix: str = "offline/latest"
    minio_connect_timeout_seconds: float = 3.0
    minio_read_timeout_seconds: float = 10.0

    # Recommendation
    recall_top_k: int = 200
    final_top_k: int = 20
    popular_fallback_count: int = 50

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug_flag(cls, value):
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"release", "prod", "production"}:
                return False
            if normalized in {"dev", "development"}:
                return True
        return value

    model_config = {
        "env_file": str(PROJECT_ROOT / ".env"),
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }

    @property
    def redis_url(self) -> str:
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def models_dir(self) -> Path:
        return PROJECT_ROOT / "models"

    @property
    def data_dir(self) -> Path:
        return PROJECT_ROOT / "data"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
