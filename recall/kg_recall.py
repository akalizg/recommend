"""Knowledge graph based recall utilities."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd
from neo4j import GraphDatabase

from knowledge_graph.config import NEO4J_DATABASE, NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER


class KGRecall:
    def __init__(self) -> None:
        self.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        self._recipe_df = self._load_recipe_table()
        self._user_profile_df = self._load_user_profile_table()
        self._recipe_ingredient_map = self._build_recipe_ingredient_map()
        self._recipe_tag_map = self._build_recipe_tag_map()
        self._recipe_popularity_map = self._build_popularity_map()

    def close(self) -> None:
        self.driver.close()

    @staticmethod
    def _normalize_terms(values: list[str] | None) -> list[str]:
        return [str(v).strip().lower() for v in values or [] if str(v).strip()]

    @staticmethod
    def _load_recipe_table(recipe_path: str | Path = "data/recipe-canonical/recipe_metadata.csv") -> pd.DataFrame:
        path = Path(recipe_path)
        if not path.exists():
            raise FileNotFoundError(path)
        return pd.read_csv(path)

    @staticmethod
    def _load_user_profile_table(user_profile_path: str | Path = "data/features/user_profile.csv") -> pd.DataFrame:
        path = Path(user_profile_path)
        if not path.exists():
            raise FileNotFoundError(path)
        return pd.read_csv(path)

    @staticmethod
    def _parse_pipe_values(value: Any) -> list[str]:
        if pd.isna(value):
            return []
        return [part.strip().strip('"').strip("'").lower() for part in str(value).split("|") if part.strip()]

    def _build_recipe_ingredient_map(self) -> dict[int, list[str]]:
        if not {"recipe_id", "ingredients"}.issubset(self._recipe_df.columns):
            return {}
        mapping: dict[int, list[str]] = {}
        for _, row in self._recipe_df[["recipe_id", "ingredients"]].dropna().iterrows():
            mapping[int(row["recipe_id"])] = self._parse_pipe_values(row["ingredients"])
        return mapping

    def _build_recipe_tag_map(self) -> dict[int, list[str]]:
        if not {"recipe_id", "genres"}.issubset(self._recipe_df.columns):
            return {}
        mapping: dict[int, list[str]] = {}
        for _, row in self._recipe_df[["recipe_id", "genres"]].dropna().iterrows():
            mapping[int(row["recipe_id"])] = self._parse_pipe_values(row["genres"])
        return mapping

    def _build_popularity_map(self) -> dict[int, float]:
        if not {"recipe_id", "rating_count"}.issubset(self._recipe_df.columns):
            return {}
        counts = pd.to_numeric(self._recipe_df["rating_count"], errors="coerce").fillna(0.0)
        if counts.empty:
            return {}
        max_count = float(counts.max() or 1.0)
        popularity = (counts / max_count).clip(0.0, 1.0)
        return {int(rid): float(score) for rid, score in zip(self._recipe_df["recipe_id"], popularity)}

    def _get_user_profile_row(self, user_id: int) -> pd.Series | None:
        if self._user_profile_df.empty or "userId" not in self._user_profile_df.columns:
            return None
        match = self._user_profile_df[self._user_profile_df["userId"] == user_id]
        return match.iloc[0] if not match.empty else None

    def build_query_from_user_profile(self, user_id: int) -> dict[str, Any]:
        profile = self._get_user_profile_row(user_id)
        if profile is None:
            return {
                "ingredients": [],
                "tags": [],
                "max_calories": 1000,
                "min_protein": 0,
            }

        tags = self._normalize_terms(self._parse_pipe_values(profile.get("favorite_genres", "")))
        decade_tags = self._normalize_terms(self._parse_pipe_values(profile.get("favorite_decades", "")))
        ingredients = self._infer_top_ingredients_from_profile(profile)
        if not ingredients:
            ingredients = self._infer_fallback_ingredients_from_profile(profile)

        active_level = str(profile.get("active_level", "")).strip().lower()
        user_avg_rating = float(profile.get("user_avg_rating", 0) or 0)

        max_calories = 1000
        min_protein = 0
        if "healthy" in tags or "dietary" in tags:
            max_calories = 700
            min_protein = 10
        if active_level == "medium":
            min_protein = max(min_protein, 15)
        elif active_level == "high":
            min_protein = max(min_protein, 20)

        if user_avg_rating >= 4.5:
            max_calories = min(max_calories, 800)
        elif user_avg_rating <= 3.5:
            max_calories = max(max_calories, 1200)

        expanded_tags = list(dict.fromkeys([*tags, *decade_tags]))
        return {
            "ingredients": ingredients,
            "tags": expanded_tags,
            "max_calories": max_calories,
            "min_protein": min_protein,
        }

    def _infer_top_ingredients_from_profile(self, profile: pd.Series, top_k: int = 3) -> list[str]:
        recent_ids = self._parse_pipe_values(profile.get("recent_movie_ids", ""))
        high_ids = self._parse_pipe_values(profile.get("high_rating_movie_ids", ""))
        candidate_ids = []
        for value in recent_ids + high_ids:
            try:
                candidate_ids.append(int(value))
            except Exception:
                continue
        counter: Counter[str] = Counter()
        for recipe_id in candidate_ids[:20]:
            for ingredient in self._recipe_ingredient_map.get(recipe_id, []):
                if ingredient:
                    counter[ingredient] += 1
        if not counter:
            return []
        return [name for name, _ in counter.most_common(top_k)]

    def _infer_fallback_ingredients_from_profile(self, profile: pd.Series, top_k: int = 3) -> list[str]:
        tags = self._normalize_terms(self._parse_pipe_values(profile.get("favorite_genres", "")))
        candidates: list[str] = []
        if any(tag in tags for tag in ["main-ingredient", "course", "side-dishes"]):
            candidates.extend(["onion", "garlic", "salt"])
        if any(tag in tags for tag in ["dessert", "desserts", "sweet"]):
            candidates.extend(["sugar", "butter", "flour"])
        if any(tag in tags for tag in ["healthy", "dietary"]):
            candidates.extend(["chicken", "broccoli", "tomato"])
        if any(tag in tags for tag in ["easy", "time-to-make"]):
            candidates.extend(["chicken", "egg", "rice"])
        if not candidates:
            candidates = ["salt", "pepper", "water"]
        deduped = []
        for item in candidates:
            if item not in deduped:
                deduped.append(item)
        return deduped[:top_k]

    def recall_by_ingredients(self, ingredients: list[str], top_n: int = 50) -> list[tuple[int, float]]:
        ingredients = self._normalize_terms(ingredients)
        if not ingredients:
            return []
        with self.driver.session(database=NEO4J_DATABASE) as session:
            result = session.run(
                """
                MATCH (r:Recipe)-[:CONTAINS]->(i:Ingredient)
                WHERE ANY(x IN $ingredients WHERE toLower(i.name) CONTAINS x)
                WITH r, COUNT(DISTINCT i) AS match_count
                RETURN r.recipe_id AS recipe_id, match_count
                ORDER BY match_count DESC, recipe_id ASC
                LIMIT $top_n
                """,
                ingredients=ingredients,
                top_n=top_n,
            )
            return [(int(record["recipe_id"]), float(record["match_count"])) for record in result]

    def recall_by_tags(self, tags: list[str], top_n: int = 50) -> list[tuple[int, float]]:
        tags = self._normalize_terms(tags)
        if not tags:
            return []
        with self.driver.session(database=NEO4J_DATABASE) as session:
            result = session.run(
                """
                MATCH (r:Recipe)-[:HAS_TAG]->(t:Tag)
                WHERE toLower(t.name) IN $tags
                WITH r, COUNT(DISTINCT t) AS match_count
                RETURN r.recipe_id AS recipe_id, match_count
                ORDER BY match_count DESC, recipe_id ASC
                LIMIT $top_n
                """,
                tags=tags,
                top_n=top_n,
            )
            return [(int(record["recipe_id"]), float(record["match_count"])) for record in result]

    def recall_by_nutrition(self, max_calories: float = 500, min_protein: float = 20, top_n: int = 50) -> list[tuple[int, float]]:
        with self.driver.session(database=NEO4J_DATABASE) as session:
            result = session.run(
                """
                MATCH (r:Recipe)
                WHERE coalesce(r.calories, 0) <= $max_calories AND coalesce(r.protein, 0) >= $min_protein
                RETURN r.recipe_id AS recipe_id, coalesce(r.protein, 0) AS protein, coalesce(r.calories, 0) AS calories
                ORDER BY protein DESC, calories ASC, recipe_id ASC
                LIMIT $top_n
                """,
                max_calories=max_calories,
                min_protein=min_protein,
                top_n=top_n,
            )
            return [(int(record["recipe_id"]), float(record["protein"])) for record in result]

    def get_recipe_popularity(self, recipe_id: int) -> float:
        return float(self._recipe_popularity_map.get(int(recipe_id), 0.0))

    def get_long_tail_bonus(self, recipe_id: int) -> float:
        popularity = self.get_recipe_popularity(recipe_id)
        return max(0.0, 1.0 - popularity)

    def recall_by_recipe_similarity(self, recipe_id: int, top_n: int = 20) -> list[tuple[int, float]]:
        with self.driver.session(database=NEO4J_DATABASE) as session:
            result = session.run(
                """
                MATCH (r:Recipe {recipe_id: $recipe_id})-[:CONTAINS]->(i:Ingredient)<-[:CONTAINS]-(other:Recipe)
                WHERE other.recipe_id <> $recipe_id
                WITH other, COUNT(DISTINCT i) AS shared_ingredients
                RETURN other.recipe_id AS recipe_id, shared_ingredients
                ORDER BY shared_ingredients DESC, recipe_id ASC
                LIMIT $top_n
                """,
                recipe_id=recipe_id,
                top_n=top_n,
            )
            return [(int(record["recipe_id"]), float(record["shared_ingredients"])) for record in result]

    def hybrid_recall(
        self,
        ingredients: list[str] | None = None,
        tags: list[str] | None = None,
        max_calories: float | None = None,
        min_protein: float | None = None,
        top_n: int = 100,
    ) -> list[tuple[int, float]]:
        scores: dict[int, float] = {}
        if ingredients:
            for recipe_id, score in self.recall_by_ingredients(ingredients, top_n=top_n):
                scores[recipe_id] = scores.get(recipe_id, 0.0) + score * 0.42
        if tags:
            for recipe_id, score in self.recall_by_tags(tags, top_n=top_n):
                scores[recipe_id] = scores.get(recipe_id, 0.0) + score * 0.28
        if max_calories is not None and min_protein is not None:
            for recipe_id, score in self.recall_by_nutrition(max_calories, min_protein, top_n=top_n):
                scores[recipe_id] = scores.get(recipe_id, 0.0) + score * 0.18

        if not scores:
            return []

        max_score = max(scores.values()) or 1.0
        for recipe_id in list(scores.keys()):
            base = scores[recipe_id] / max_score
            novelty_bonus = self.get_long_tail_bonus(recipe_id) * 0.12
            scores[recipe_id] = base + novelty_bonus

        return sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:top_n]


if __name__ == "__main__":
    kg = KGRecall()
    try:
        print(kg.build_query_from_user_profile(6381))
    finally:
        kg.close()
