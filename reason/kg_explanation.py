"""Generate knowledge-graph-based recommendation explanations."""

from __future__ import annotations

from neo4j import GraphDatabase

from knowledge_graph.config import NEO4J_DATABASE, NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER


class KGExplanation:
    def __init__(self) -> None:
        self.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    def close(self) -> None:
        self.driver.close()

    def explain_recipe(self, user_id: int, recipe_id: int) -> str:
        with self.driver.session(database=NEO4J_DATABASE) as session:
            result = session.run(
                """
                MATCH (r:Recipe {recipe_id: $recipe_id})-[:HAS_TAG]->(t:Tag)
                RETURN collect(DISTINCT t.name) AS tags
                LIMIT 1
                """,
                recipe_id=recipe_id,
            )
            record = result.single()
            tags = record["tags"] if record and record["tags"] else []
            if tags:
                return f"这道菜命中了这些图谱标签：{', '.join(tags[:5])}。"
            return "这道菜与用户的食材和场景偏好存在潜在匹配。"
