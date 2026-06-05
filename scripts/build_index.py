"""
Standalone script to download data, run the full pipeline,
train embeddings, build FAISS index, and train the ranking model.
"""
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings
from app.logging_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


def build_all():
    """Run the complete build pipeline."""
    t_total = time.perf_counter()

    # 1. Download data
    logger.info("=" * 50)
    logger.info("STEP 1: Downloading MovieLens data")
    logger.info("=" * 50)
    from scripts.download_data import download_movielens
    download_movielens()

    # 2. Feature pipeline
    logger.info("=" * 50)
    logger.info("STEP 2: Running feature pipeline")
    logger.info("=" * 50)
    from feature.pipeline import FeaturePipeline
    pipeline = FeaturePipeline().run()
    pipeline.save()

    # 3. Embeddings
    logger.info("=" * 50)
    logger.info("STEP 3: Training embeddings (Matrix Factorization)")
    logger.info("=" * 50)
    from embedding.embedding_service import EmbeddingService
    embedding_service = EmbeddingService(pipeline)
    embedding_service.train(pipeline)
    embedding_service.save()

    # 4. FAISS index
    logger.info("=" * 50)
    logger.info("STEP 4: Building FAISS HNSW index")
    logger.info("=" * 50)
    from recall.faiss_index import FaissHNSWIndex
    faiss_index = FaissHNSWIndex()
    faiss_index.build(embedding_service.item_embeddings, pipeline.movie_ids)

    # 5. Rank model
    logger.info("=" * 50)
    logger.info("STEP 5: Training ranking model (XGBoost)")
    logger.info("=" * 50)
    from rank.train import train_rank_model
    train_rank_model(pipeline, embedding_service)

    elapsed = time.perf_counter() - t_total
    logger.info("=" * 50)
    logger.info(f"ALL DONE in {elapsed:.1f}s ({elapsed/60:.1f}m)")
    logger.info("=" * 50)


if __name__ == "__main__":
    build_all()
