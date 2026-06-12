"""
Export a lightweight user-movie-genre graph for future LightGCN training.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TRAIN = PROJECT_ROOT / "data" / "processed" / "train_ratings.csv"
DEFAULT_MOVIE_PROFILE = PROJECT_ROOT / "data" / "features" / "movie_profile.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "lightgcn" / "graph_edges.csv"

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export LightGCN graph edges.")
    parser.add_argument("--train", default=str(DEFAULT_TRAIN))
    parser.add_argument("--movie-profile", default=str(DEFAULT_MOVIE_PROFILE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--min-rating", type=float, default=4.0)
    return parser.parse_args()


def export_lightgcn_graph(
    train_path: str | Path | None = None,
    movie_profile_path: str | Path | None = None,
    output_path: str | Path | None = None,
    min_rating: float = 4.0,
) -> dict:
    train_file = Path(train_path).resolve() if train_path else DEFAULT_TRAIN
    movie_file = Path(movie_profile_path).resolve() if movie_profile_path else DEFAULT_MOVIE_PROFILE
    output_file = Path(output_path).resolve() if output_path else DEFAULT_OUTPUT
    ratings = pd.read_csv(train_file)
    movies = pd.read_csv(movie_file, usecols=["movieId", "genres"])

    ratings["rating"] = pd.to_numeric(ratings["rating"], errors="coerce")
    ratings = ratings[ratings["rating"] >= min_rating].copy()
    user_movie = pd.DataFrame(
        {
            "src_type": "user",
            "src_id": ratings["userId"].astype(int).astype(str),
            "dst_type": "movie",
            "dst_id": ratings["movieId"].astype(int).astype(str),
            "edge_type": "liked",
            "weight": ratings["rating"].astype(float),
        }
    )

    movie_genre_rows = []
    for row in movies.itertuples(index=False):
        for genre in str(row.genres).split("|"):
            genre = genre.strip()
            if genre and genre != "(no genres listed)":
                movie_genre_rows.append(
                    {
                        "src_type": "movie",
                        "src_id": str(int(row.movieId)),
                        "dst_type": "genre",
                        "dst_id": genre,
                        "edge_type": "has_genre",
                        "weight": 1.0,
                    }
                )
    graph = pd.concat([user_movie, pd.DataFrame(movie_genre_rows)], ignore_index=True)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    graph.to_csv(output_file, index=False)
    summary = {
        "user_movie_edges": int(len(user_movie)),
        "movie_genre_edges": int(len(movie_genre_rows)),
        "output_rows": int(len(graph)),
        "output_path": str(output_file),
    }
    logger.info("LightGCN graph export summary: %s", summary)
    return summary


def main() -> None:
    args = parse_args()
    try:
        export_lightgcn_graph(args.train, args.movie_profile, args.output, args.min_rating)
    except Exception as exc:
        logger.error("%s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
