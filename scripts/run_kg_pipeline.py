"""Run the knowledge graph pipeline end-to-end."""

from __future__ import annotations

import argparse
import logging

from knowledge_graph.graph_builder import KnowledgeGraphBuilder
from recall.kg_recall import KGRecall

logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run knowledge graph pipeline")
    parser.add_argument("--recipe-path", default="data/recipe-canonical/recipe_metadata.csv")
    parser.add_argument("--profile-path", default="data/features/movie_profile.csv")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--no-clear", action="store_true")
    args = parser.parse_args()

    builder = KnowledgeGraphBuilder()
    try:
        builder.build_all(
            recipe_path=args.recipe_path,
            profile_path=args.profile_path,
            limit=args.limit,
            clear=not args.no_clear,
        )
    finally:
        builder.close()

    kg = KGRecall()
    try:
        print(kg.hybrid_recall(ingredients=["chicken"], tags=["quick", "dinner"], top_n=10))
    finally:
        kg.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    main()
