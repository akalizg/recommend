"""Build a lightweight recipe knowledge graph in Neo4j."""

from __future__ import annotations

import ast
import logging
import sys
from argparse import ArgumentParser
from pathlib import Path
from typing import Any

import pandas as pd
from neo4j import GraphDatabase

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from knowledge_graph.config import NEO4J_DATABASE, NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER

logger = logging.getLogger(__name__)


class KnowledgeGraphBuilder:
    def __init__(self) -> None:
        self.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    def close(self) -> None:
        self.driver.close()

    def clear_database(self) -> None:
        with self.driver.session(database=NEO4J_DATABASE) as session:
            session.run("MATCH (n) DETACH DELETE n")
        logger.info("Database cleared")

    def create_indexes(self) -> None:
        statements = [
            "CREATE CONSTRAINT recipe_id_unique IF NOT EXISTS FOR (r:Recipe) REQUIRE r.recipe_id IS UNIQUE",
            "CREATE CONSTRAINT ingredient_name_unique IF NOT EXISTS FOR (i:Ingredient) REQUIRE i.name IS UNIQUE",
            "CREATE CONSTRAINT tag_name_unique IF NOT EXISTS FOR (t:Tag) REQUIRE t.name IS UNIQUE",
            "CREATE INDEX recipe_minutes_idx IF NOT EXISTS FOR (r:Recipe) ON (r.minutes)",
        ]
        with self.driver.session(database=NEO4J_DATABASE) as session:
            for stmt in statements:
                session.run(stmt)
        logger.info("Indexes and constraints created")

    def build_recipe_nodes(self, recipe_df: pd.DataFrame) -> None:
        query = """
        MERGE (r:Recipe {recipe_id: $recipe_id})
        SET r.title = $title,
            r.minutes = $minutes,
            r.steps = $steps,
            r.calories = $calories,
            r.protein = $protein,
            r.fat = $fat,
            r.sodium = $sodium
        """
        with self.driver.session(database=NEO4J_DATABASE) as session:
            for _, row in recipe_df.iterrows():
                session.run(
                    query,
                    recipe_id=int(row["recipe_id"]),
                    title=str(row.get("title", "")),
                    minutes=int(row["minutes"]) if pd.notna(row.get("minutes")) else 0,
                    steps=self._normalize_text(row.get("steps", "")),
                    calories=float(row["calories"]) if pd.notna(row.get("calories")) else 0,
                    protein=float(row["protein"]) if pd.notna(row.get("protein")) else 0,
                    fat=float(row["fat"]) if pd.notna(row.get("fat")) else 0,
                    sodium=float(row["sodium"]) if pd.notna(row.get("sodium")) else 0,
                )
        logger.info("Created %s recipe nodes", len(recipe_df))

    def build_ingredient_nodes_and_relations(self, recipe_df: pd.DataFrame) -> None:
        with self.driver.session(database=NEO4J_DATABASE) as session:
            for _, row in recipe_df.iterrows():
                recipe_id = int(row["recipe_id"])
                ingredients = self._parse_list_field(row.get("ingredients"))
                for ingredient in ingredients:
                    name = self._normalize_text(ingredient)
                    if not name:
                        continue
                    session.run("MERGE (i:Ingredient {name: $name})", name=name)
                    session.run(
                        """
                        MATCH (r:Recipe {recipe_id: $recipe_id})
                        MATCH (i:Ingredient {name: $name})
                        MERGE (r)-[:CONTAINS]->(i)
                        """,
                        recipe_id=recipe_id,
                        name=name,
                    )
        logger.info("Created ingredient nodes and relations")

    def build_tag_nodes_and_relations(self, profile_df: pd.DataFrame) -> None:
        if not {"movieId", "genres"}.issubset(profile_df.columns):
            logger.warning("movie_profile.csv missing expected columns movieId/genres")
            return
        with self.driver.session(database=NEO4J_DATABASE) as session:
            for _, row in profile_df.iterrows():
                recipe_id = int(row["movieId"])
                raw_tags = str(row.get("genres", "")).split("|")
                tags = []
                for tag in raw_tags:
                    clean_tag = str(tag).strip().strip('"').strip("'").lower()
                    if clean_tag and clean_tag != "(no genres listed)":
                        tags.append(clean_tag)
                for tag in tags:
                    session.run("MERGE (t:Tag {name: $tag})", tag=tag)
                    session.run(
                        """
                        MATCH (r:Recipe {recipe_id: $recipe_id})
                        MATCH (t:Tag {name: $tag})
                        MERGE (r)-[:HAS_TAG]->(t)
                        """,
                        recipe_id=recipe_id,
                        tag=tag,
                    )
        logger.info("Created tag nodes and relations")

    @staticmethod
    def _normalize_text(value: Any) -> str:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return ""
        return str(value).strip()

    @staticmethod
    def _parse_list_field(value: Any) -> list[str]:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return []
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        text = str(value).strip()
        if not text:
            return []
        try:
            parsed = ast.literal_eval(text)
            if isinstance(parsed, list):
                return [str(v).strip() for v in parsed if str(v).strip()]
        except Exception:
            pass

        normalized = text.strip().strip('"').strip("'")
        if "|" in normalized:
            return [part.strip() for part in normalized.split("|") if part.strip()]
        if "," in normalized:
            return [part.strip() for part in normalized.split(",") if part.strip()]
        return [normalized] if normalized else []

    def build_all(
        self,
        recipe_path: str = "data/recipe-canonical/recipe_metadata.csv",
        profile_path: str = "data/features/movie_profile.csv",
        limit: int | None = None,
        clear: bool = True,
    ) -> None:
        recipe_file = Path(recipe_path)
        profile_file = Path(profile_path)
        if not recipe_file.exists():
            raise FileNotFoundError(recipe_file)
        if not profile_file.exists():
            raise FileNotFoundError(profile_file)

        recipe_df = pd.read_csv(recipe_file)
        profile_df = pd.read_csv(profile_file)
        if limit is not None:
            recipe_df = recipe_df.head(limit)
            profile_df = profile_df.head(limit)

        if clear:
            self.clear_database()
        self.create_indexes()
        self.build_recipe_nodes(recipe_df)
        self.build_ingredient_nodes_and_relations(recipe_df)
        self.build_tag_nodes_and_relations(profile_df)
        logger.info("Knowledge graph build complete")


def build_arg_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Build the recipe knowledge graph in Neo4j")
    parser.add_argument("--recipe-path", default="data/recipe-canonical/recipe_metadata.csv")
    parser.add_argument("--profile-path", default="data/features/movie_profile.csv")
    parser.add_argument("--limit", type=int, default=None, help="Optional sample size for quick validation")
    parser.add_argument("--no-clear", action="store_true", help="Do not clear the Neo4j database before building")
    return parser


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    args = build_arg_parser().parse_args()
    KnowledgeGraphBuilder().build_all(
        recipe_path=args.recipe_path,
        profile_path=args.profile_path,
        limit=args.limit,
        clear=not args.no_clear,
    )
