"""
Download and extract the MovieLens Latest Small dataset.
"""
import logging
import os
import sys
import zipfile
from pathlib import Path
from urllib.request import urlretrieve

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def download_movielens():
    settings = get_settings()
    data_dir = Path(settings.movielens_data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    zip_path = data_dir.parent / "ml-latest-small.zip"
    url = settings.movielens_url

    # Already extracted?
    required_files = ["ratings.csv", "movies.csv", "tags.csv", "links.csv"]
    if all((data_dir / f).exists() for f in required_files):
        logger.info(f"MovieLens data already exists at {data_dir}")
        return

    # Download
    if not zip_path.exists():
        logger.info(f"Downloading from {url} ...")
        urlretrieve(url, zip_path)
        logger.info(f"Downloaded to {zip_path}")
    else:
        logger.info(f"Using cached zip at {zip_path}")

    # Extract
    logger.info(f"Extracting to {data_dir.parent} ...")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(data_dir.parent)

    logger.info("MovieLens data ready!")
    # Verify
    for f in required_files:
        fp = data_dir / f
        if fp.exists():
            logger.info(f"  ✓ {f} ({fp.stat().st_size:,} bytes)")
        else:
            logger.error(f"  ✗ {f} MISSING!")


if __name__ == "__main__":
    download_movielens()
