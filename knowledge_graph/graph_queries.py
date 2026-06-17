"""Reusable Neo4j query helpers for the knowledge graph."""

from __future__ import annotations

from typing import Any, Iterable

from neo4j import GraphDatabase

from knowledge_graph.config import NEO4J_DATABASE, NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER


class KnowledgeGraphQueries:
    def __init__(self) -> None:
        self.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    def close(self) -> None:
        self.driver.close()

    def _run(self, query: str, **params: Any):
        with self.driver.session(database=NEO4J_DATABASE) as session:
            return list(session.run(query, **params))

    def get_recipe_by_id(self, recipe_id: int):
        records = self._run(
            """
            MATCH (r:Recipe {recipe_id: $recipe_id})
            RETURN r
            LIMIT 1
            """,
            recipe_id=recipe_id,
        )
        return records[0]["r"] if records else None

    def get_recipes_by_ingredient(self, ingredient: str, limit: int = 10):
        return self._run(
            """
            MATCH (r:Recipe)-[:CONTAINS]->(i:Ingredient {name: $ingredient})
            RETURN r.recipe_id AS recipe_id, r.title AS title
            LIMIT $limit
            """,
            ingredient=ingredient,
            limit=limit,
        )

    def get_recipes_by_tag(self, tag: str, limit: int = 10):
        return self._run(
            """
            MATCH (r:Recipe)-[:HAS_TAG]->(t:Tag {name: $tag})
            RETURN r.recipe_id AS recipe_id, r.title AS title
            LIMIT $limit
            """,
            tag=tag,
            limit=limit,
        )
