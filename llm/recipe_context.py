"""Build recipe context text for LLM recommendation."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MOVIE_PROFILE = PROJECT_ROOT / "data" / "features" / "movie_profile.csv"
DEFAULT_RECIPE_METADATA = PROJECT_ROOT / "data" / "recipe-canonical" / "recipe_metadata.csv"


class RecipeContextBuilder:
    def __init__(self, movie_profile_path: str | Path = DEFAULT_MOVIE_PROFILE, recipe_metadata_path: str | Path = DEFAULT_RECIPE_METADATA):
        self.movie_profile_path = Path(movie_profile_path)
        self.recipe_metadata_path = Path(recipe_metadata_path)
        self.movie_profile = self._load_csv(self.movie_profile_path)
        self.recipe_metadata = self._load_csv(self.recipe_metadata_path)
        self.recipe_metadata = self._ensure_recipe_id(self.recipe_metadata)
        self.movie_profile = self._ensure_movie_id(self.movie_profile)

    @staticmethod
    def _load_csv(path: Path) -> pd.DataFrame:
        if not path.exists():
            raise FileNotFoundError(path)
        return pd.read_csv(path)

    @staticmethod
    def _ensure_recipe_id(df: pd.DataFrame) -> pd.DataFrame:
        if "recipe_id" not in df.columns and "movieId" in df.columns:
            df = df.rename(columns={"movieId": "recipe_id"})
        return df

    @staticmethod
    def _ensure_movie_id(df: pd.DataFrame) -> pd.DataFrame:
        if "movieId" not in df.columns and "recipe_id" in df.columns:
            df = df.rename(columns={"recipe_id": "movieId"})
        return df

    @staticmethod
    def _split_values(value: object) -> list[str]:
        if value is None or pd.isna(value):
            return []
        text = str(value).strip()
        if not text:
            return []
        parts = []
        for token in text.replace(",", "|").split("|"):
            token = token.strip().strip('"').strip("'")
            if token:
                parts.append(token)
        return parts

    def _recipe_row_to_text(self, row: pd.Series) -> str:
        rid = int(row.get("recipe_id", row.get("movieId", -1)))
        title = str(row.get("title", row.get("name", f"Recipe {rid}")))
        ingredients = self._split_values(row.get("ingredients", ""))
        tags = self._split_values(row.get("genres", row.get("tags", "")))
        calories = row.get("calories", row.get("movie_popularity", ""))
        protein = row.get("protein", row.get("protein_pct", ""))
        minutes = row.get("minutes", row.get("recipe_minutes", ""))
        return (
            f"recipe_id: {rid}\n"
            f"title: {title}\n"
            f"ingredients: {', '.join(ingredients[:8]) if ingredients else 'unknown'}\n"
            f"tags: {', '.join(tags[:8]) if tags else 'unknown'}\n"
            f"minutes: {minutes}\n"
            f"calories: {calories}\n"
            f"protein: {protein}"
        )

    def build_recipe_context(self, recipe_ids: Iterable[int], max_items: int = 20) -> str:
        recipe_ids = list(dict.fromkeys(int(r) for r in recipe_ids))[:max_items]
        if not recipe_ids:
            return ""
        profile = self.movie_profile.copy()
        if "movieId" not in profile.columns:
            raise ValueError("movie_profile.csv must contain movieId")
        profile["movieId"] = pd.to_numeric(profile["movieId"], errors="coerce")
        profile = profile.dropna(subset=["movieId"])
        profile["movieId"] = profile["movieId"].astype(int)
        subset = profile[profile["movieId"].isin(recipe_ids)]
        if subset.empty:
            return "\n\n".join([f"recipe_id: {rid}\ninfo: not found in metadata" for rid in recipe_ids])
        lines = [self._recipe_row_to_text(row) for _, row in subset.iterrows()]
        return "\n\n".join(lines)
