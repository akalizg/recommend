"""
Enrich MovieLens movies with TMDB metadata.

Reads movies.csv and links.csv, calls the TMDB movie details API by tmdbId,
and writes movie_metadata.csv next to the detected MovieLens files.
"""
import argparse
import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional

import pandas as pd
import requests
from dotenv import load_dotenv
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import PROJECT_ROOT, get_settings


TMDB_MOVIE_URL = "https://api.themoviedb.org/3/movie/{tmdb_id}"
POSTER_BASE_URL = "https://image.tmdb.org/t/p/w500"
BACKDROP_BASE_URL = "https://image.tmdb.org/t/p/w780"

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def detect_data_dir(explicit_dir: Optional[str] = None) -> Path:
    """Find a directory containing the MovieLens CSV files."""
    required = {"movies.csv", "links.csv"}
    candidates = []

    if explicit_dir:
        candidates.append(Path(explicit_dir))

    settings = get_settings()
    candidates.extend([
        Path(settings.movielens_data_dir),
        PROJECT_ROOT / "data" / "ml-latest-small",
        PROJECT_ROOT,
        Path.cwd(),
    ])

    seen = set()
    for candidate in candidates:
        candidate = candidate.resolve()
        if candidate in seen:
            continue
        seen.add(candidate)
        if all((candidate / name).exists() for name in required):
            return candidate

    checked = ", ".join(str(p.resolve()) for p in candidates)
    raise FileNotFoundError(f"Could not find movies.csv and links.csv. Checked: {checked}")


def image_url(base_url: str, path: Optional[str]) -> str:
    if not path or pd.isna(path):
        return ""
    return f"{base_url}{path}"


def fetch_tmdb_movie(session: requests.Session, api_key: str, tmdb_id: int, timeout: float) -> dict:
    response = session.get(
        TMDB_MOVIE_URL.format(tmdb_id=tmdb_id),
        params={"api_key": api_key, "language": "zh-CN"},
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()


def base_metadata(row: pd.Series) -> dict:
    imdb_id = row.get("imdbId", "")
    tmdb_id = row.get("tmdbId", "")
    return {
        "movieId": int(row["movieId"]),
        "tmdbId": "" if pd.isna(tmdb_id) else str(int(tmdb_id)),
        "imdbId": "" if pd.isna(imdb_id) else str(int(imdb_id)),
        "title": str(row.get("title", "")),
        "genres": str(row.get("genres", "")),
        "poster_url": "",
        "backdrop_url": "",
        "overview": "",
        "release_date": "",
        "runtime": "",
        "vote_average": "",
        "popularity": "",
    }


def load_existing_metadata(output_path: Path) -> dict[int, dict]:
    """Load an existing output file so reruns can skip completed rows."""
    if not output_path.exists():
        return {}
    try:
        existing = pd.read_csv(output_path)
        if "movieId" not in existing.columns:
            logger.warning("Ignoring existing metadata without movieId column: %s", output_path)
            return {}
        existing["movieId"] = pd.to_numeric(existing["movieId"], errors="coerce")
        existing = existing.dropna(subset=["movieId"])
        rows = {}
        for _, row in existing.iterrows():
            item = row.fillna("").to_dict()
            item["movieId"] = int(item["movieId"])
            rows[item["movieId"]] = item
        logger.info("Loaded %s existing metadata rows from %s", len(rows), output_path)
        return rows
    except Exception as exc:
        logger.warning("Could not read existing metadata from %s: %s", output_path, exc)
        return {}


def has_display_metadata(item: dict) -> bool:
    """Return true when a row already contains TMDB-sourced display data."""
    return any(item.get(field) not in ("", None) for field in ("poster_url", "backdrop_url", "overview"))


def enrich_movies(
    data_dir: Path,
    output_path: Optional[Path],
    sleep_seconds: float,
    timeout: float,
    limit: Optional[int],
    resume: bool,
) -> Path:
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    api_key = os.getenv("TMDB_API_KEY", "").strip()

    movies = pd.read_csv(data_dir / "movies.csv")
    links = pd.read_csv(data_dir / "links.csv")
    merged = movies.merge(links, on="movieId", how="left")

    if limit:
        merged = merged.head(limit)

    output_path = output_path or data_dir / "movie_metadata.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Reading MovieLens files from %s", data_dir)
    logger.info("Writing metadata to %s", output_path)

    if not api_key:
        logger.warning("TMDB_API_KEY is not set. Writing fallback metadata without images.")
        rows = [base_metadata(row) for _, row in merged.iterrows()]
        pd.DataFrame(rows).to_csv(output_path, index=False, encoding="utf-8")
        return output_path

    rows = []
    existing_rows = load_existing_metadata(output_path) if resume else {}
    session = requests.Session()

    for _, row in tqdm(merged.iterrows(), total=len(merged), desc="Fetching TMDB metadata"):
        item = base_metadata(row)
        tmdb_id = row.get("tmdbId")

        existing = existing_rows.get(item["movieId"])
        if existing and has_display_metadata(existing):
            rows.append({**item, **existing, "movieId": item["movieId"]})
            continue

        if pd.notna(tmdb_id):
            try:
                detail = fetch_tmdb_movie(session, api_key, int(tmdb_id), timeout)
                item.update({
                    "poster_url": image_url(POSTER_BASE_URL, detail.get("poster_path")),
                    "backdrop_url": image_url(BACKDROP_BASE_URL, detail.get("backdrop_path")),
                    "overview": detail.get("overview") or "",
                    "release_date": detail.get("release_date") or "",
                    "runtime": detail.get("runtime") if detail.get("runtime") is not None else "",
                    "vote_average": detail.get("vote_average") if detail.get("vote_average") is not None else "",
                    "popularity": detail.get("popularity") if detail.get("popularity") is not None else "",
                })
            except requests.HTTPError as exc:
                status = exc.response.status_code if exc.response is not None else "unknown"
                logger.warning("TMDB request failed for movieId=%s tmdbId=%s status=%s", item["movieId"], int(tmdb_id), status)
            except requests.RequestException as exc:
                logger.warning("TMDB request error for movieId=%s tmdbId=%s: %s", item["movieId"], int(tmdb_id), exc)
            except Exception as exc:
                logger.warning("Failed to process movieId=%s tmdbId=%s: %s", item["movieId"], int(tmdb_id), exc)
            finally:
                if sleep_seconds > 0:
                    time.sleep(sleep_seconds)

        rows.append(item)

    columns = [
        "movieId",
        "tmdbId",
        "imdbId",
        "title",
        "genres",
        "poster_url",
        "backdrop_url",
        "overview",
        "release_date",
        "runtime",
        "vote_average",
        "popularity",
    ]
    pd.DataFrame(rows).reindex(columns=columns).to_csv(output_path, index=False, encoding="utf-8")
    logger.info("Metadata enrichment complete: %s rows", len(rows))
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch TMDB posters and metadata for MovieLens movies.")
    parser.add_argument("--data-dir", help="Directory containing movies.csv and links.csv")
    parser.add_argument("--output", help="Output CSV path. Defaults to movie_metadata.csv in the detected data directory.")
    parser.add_argument("--sleep", type=float, default=0.25, help="Seconds to sleep between TMDB requests.")
    parser.add_argument("--timeout", type=float, default=10.0, help="HTTP request timeout in seconds.")
    parser.add_argument("--limit", type=int, help="Optional row limit for testing.")
    parser.add_argument("--no-resume", action="store_true", help="Fetch all rows again even when output already exists.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data_dir = detect_data_dir(args.data_dir)
    output_path = Path(args.output) if args.output else None
    enrich_movies(data_dir, output_path, args.sleep, args.timeout, args.limit, resume=not args.no_resume)


if __name__ == "__main__":
    main()
