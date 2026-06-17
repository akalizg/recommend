"""Knowledge graph based feature engineering for ranking."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd
from neo4j import GraphDatabase

from knowledge_graph.config import NEO4J_DATABASE, NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER


@dataclass
class KGFeatureEngineer:
    def __post_init__(self) -> None:
        self.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    def close(self) -> None:
        self.driver.close()

    def get_user_tag_matching(self, user_id: int, recipe_id: int) -> int:
        with self.driver.session(database=NEO4J_DATABASE) as session:
            result = session.run(
                """
                MATCH (u:User {user_id: $user_id})-[:PREFERS]->(ut:Tag)
                MATCH (r:Recipe {recipe_id: $recipe_id})-[:HAS_TAG]->(rt:Tag)
                WHERE ut.name = rt.name
                RETURN COUNT(DISTINCT ut) AS match_count
                """,
                user_id=user_id,
                recipe_id=recipe_id,
            )
            record = result.single()
            return int(record["match_count"]) if record else 0

    def get_ingredient_similarity(self, recipe_a: int, recipe_b: int) -> float:
        with self.driver.session(database=NEO4J_DATABASE) as session:
            result = session.run(
                """
                MATCH (a:Recipe {recipe_id: $recipe_a})-[:CONTAINS]->(i:Ingredient)
                WITH collect(DISTINCT i.name) AS ingredients_a
                MATCH (b:Recipe {recipe_id: $recipe_b})-[:CONTAINS]->(j:Ingredient)
                WITH ingredients_a, collect(DISTINCT j.name) AS ingredients_b
                WITH ingredients_a, ingredients_b,
                     [x IN ingredients_a WHERE x IN ingredients_b] AS intersection
                RETURN CASE
                    WHEN size(ingredients_a) = 0 AND size(ingredients_b) = 0 THEN 0.0
                    ELSE toFloat(size(intersection)) / toFloat(size(ingredients_a) + size(ingredients_b) - size(intersection))
                END AS similarity
                """,
                recipe_a=recipe_a,
                recipe_b=recipe_b,
            )
            record = result.single()
            return float(record["similarity"]) if record and record["similarity"] is not None else 0.0

    def add_kg_features_to_candidates(self, candidates_df: pd.DataFrame) -> pd.DataFrame:
        if candidates_df.empty:
            return candidates_df

        rows = []
        for _, row in candidates_df.iterrows():
            user_id = int(row["userId"])
            recipe_id = int(row["movieId"])
            rows.append(
                {
                    "kg_tag_match_score": self.get_user_tag_matching(user_id, recipe_id),
                }
            )
        return pd.concat([candidates_df.reset_index(drop=True), pd.DataFrame(rows)], axis=1)


if __name__ == "__main__":
    print("KGFeatureEngineer is ready to be imported into ranking pipeline.")
