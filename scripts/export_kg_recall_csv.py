"""Export user-profile-driven knowledge-graph recall candidates to CSV.

The exported format matches the multi-channel recall merger:
userId,movieId,recall_type,recall_score
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from recall.kg_recall import KGRecall


DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "recall" / "kg_recall.csv"
DEFAULT_USERS = PROJECT_ROOT / "data" / "features" / "user_profile.csv"

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export KG recall candidates to CSV.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--users", default=str(DEFAULT_USERS), help="user_profile.csv with userId column")
    parser.add_argument("--limit-users", type=int, default=None, help="Max users to export (default: all users)")
    parser.add_argument("--top-n", type=int, default=50, help="Top-N KG candidates per user")
    return parser.parse_args()


def load_user_ids(users_path: str | Path, limit_users: int | None) -> list[int]:
    df = pd.read_csv(users_path, usecols=["userId"])
    user_ids = pd.to_numeric(df["userId"], errors="coerce").dropna().astype(int).drop_duplicates().tolist()
    return user_ids if limit_users is None else user_ids[:limit_users]


def export_kg_recall_csv(
    output_path: str | Path,
    user_ids: list[int],
    top_n: int,
) -> pd.DataFrame:
    kg = KGRecall()
    rows: list[dict] = []
    try:
        for idx, user_id in enumerate(user_ids, start=1):
            query = kg.build_query_from_user_profile(user_id)
            results = kg.hybrid_recall(
                ingredients=query.get("ingredients"),
                tags=query.get("tags"),
                max_calories=query.get("max_calories"),
                min_protein=query.get("min_protein"),
                top_n=top_n,
            )
            for recipe_id, score in results:
                rows.append(
                    {
                        "userId": int(user_id),
                        "movieId": int(recipe_id),
                        "recall_type": "kg",
                        "recall_score": float(score),
                    }
                )
            if idx % 50 == 0:
                logger.info("KG recall exported for %s users", idx)
    finally:
        kg.close()

    df = pd.DataFrame(rows, columns=["userId", "movieId", "recall_type", "recall_score"])
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_file, index=False)
    logger.info("Exported KG recall rows=%s to %s", len(df), output_file)
    return df


def main() -> None:
    args = parse_args()
    user_ids = load_user_ids(args.users, args.limit_users)
    export_kg_recall_csv(
        output_path=args.output,
        user_ids=user_ids,
        top_n=args.top_n,
    )


if __name__ == "__main__":
    main()
