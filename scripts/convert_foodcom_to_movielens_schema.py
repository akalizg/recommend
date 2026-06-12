"""
Convert the Food.com recipe dataset into the canonical CSV schema used by the
existing offline recommendation pipeline.

The downstream Spark jobs still use historical column names such as movieId and
genres. In this migrated recipe theme, movieId means recipe id, title means
recipe name, and genres means recipe tags.
"""
from __future__ import annotations

import argparse
import ast
import logging
import shutil
from pathlib import Path
from typing import Iterable

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT_DIR = PROJECT_ROOT / "data" / "food-com"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "recipe-canonical"
DEFAULT_MIN_RECIPE_INTERACTIONS = 5
DEFAULT_MIN_USER_INTERACTIONS = 5
DEFAULT_MAX_RECIPES = 12_000
DEFAULT_MAX_USERS = 1_500
DEFAULT_MAX_INTERACTIONS = 120_000
DEFAULT_CHUNK_SIZE = 100_000

OUTPUT_FILES = ("ratings.csv", "movies.csv", "tags.csv", "links.csv", "recipe_metadata.csv")

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert Food.com raw CSV files to the pipeline canonical schema.")
    parser.add_argument("--input-dir", default=str(DEFAULT_INPUT_DIR), help="Directory with RAW_recipes.csv and RAW_interactions.csv.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Canonical output directory.")
    parser.add_argument("--min-recipe-interactions", type=int, default=DEFAULT_MIN_RECIPE_INTERACTIONS)
    parser.add_argument("--min-user-interactions", type=int, default=DEFAULT_MIN_USER_INTERACTIONS)
    parser.add_argument("--max-recipes", type=int, default=DEFAULT_MAX_RECIPES)
    parser.add_argument("--max-users", type=int, default=DEFAULT_MAX_USERS)
    parser.add_argument("--max-interactions", type=int, default=DEFAULT_MAX_INTERACTIONS)
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    return parser.parse_args()


def _literal_list(value: object) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if pd.isna(value):
        return []
    try:
        parsed = ast.literal_eval(str(value))
    except (SyntaxError, ValueError):
        return []
    return parsed if isinstance(parsed, list) else []


def _clean_token(value: object) -> str:
    text = str(value).strip().lower().replace("|", " ").replace(",", " ")
    return " ".join(text.split())


def _join_tokens(values: Iterable[object], limit: int = 30) -> str:
    tokens: list[str] = []
    seen: set[str] = set()
    for value in values:
        token = _clean_token(value)
        if not token or token in seen:
            continue
        seen.add(token)
        tokens.append(token)
        if len(tokens) >= limit:
            break
    return "|".join(tokens)


def _parse_year(value: object) -> int | None:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return int(parsed.year)


def _unix_timestamp(value: object) -> int:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return 0
    return int(parsed.timestamp())


def _safe_nutrition(value: object) -> list[float]:
    values = _literal_list(value)
    numbers: list[float] = []
    for item in values[:7]:
        try:
            numbers.append(float(item))
        except (TypeError, ValueError):
            numbers.append(0.0)
    while len(numbers) < 7:
        numbers.append(0.0)
    return numbers


def _prepare_output_dir(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for file_name in OUTPUT_FILES:
        path = output_dir / file_name
        if path.exists():
            path.unlink()


def _read_interactions_subset(
    interactions_file: Path,
    min_recipe_interactions: int,
    min_user_interactions: int,
    max_recipes: int,
    max_users: int,
    max_interactions: int,
    chunk_size: int,
) -> tuple[pd.DataFrame, int]:
    interaction_cols = ["user_id", "recipe_id", "date", "rating"]
    recipe_counts: pd.Series | None = None
    raw_rows = 0

    logger.info("Scanning Food.com interactions for popular recipes...")
    for chunk in pd.read_csv(interactions_file, usecols=interaction_cols, chunksize=chunk_size):
        raw_rows += int(len(chunk))
        chunk["recipe_id"] = pd.to_numeric(chunk["recipe_id"], errors="coerce")
        chunk["rating"] = pd.to_numeric(chunk["rating"], errors="coerce")
        chunk = chunk.dropna(subset=["recipe_id", "rating"])
        chunk = chunk[chunk["rating"] > 0]
        counts = chunk["recipe_id"].astype(int).value_counts()
        recipe_counts = counts if recipe_counts is None else recipe_counts.add(counts, fill_value=0)

    if recipe_counts is None or recipe_counts.empty:
        raise ValueError("No rated Food.com interactions found.")
    eligible_recipes = set(
        recipe_counts[recipe_counts >= min_recipe_interactions]
        .sort_values(ascending=False)
        .head(max_recipes)
        .index.astype(int)
        .tolist()
    )
    logger.info("Eligible recipe ids after count filter: %s", len(eligible_recipes))

    user_counts: pd.Series | None = None
    logger.info("Scanning Food.com interactions for active users...")
    for chunk in pd.read_csv(interactions_file, usecols=interaction_cols, chunksize=chunk_size):
        chunk["user_id"] = pd.to_numeric(chunk["user_id"], errors="coerce")
        chunk["recipe_id"] = pd.to_numeric(chunk["recipe_id"], errors="coerce")
        chunk["rating"] = pd.to_numeric(chunk["rating"], errors="coerce")
        chunk = chunk.dropna(subset=["user_id", "recipe_id", "rating", "date"])
        chunk = chunk[(chunk["rating"] > 0) & (chunk["recipe_id"].astype(int).isin(eligible_recipes))]
        counts = chunk["user_id"].astype(int).value_counts()
        user_counts = counts if user_counts is None else user_counts.add(counts, fill_value=0)

    if user_counts is None or user_counts.empty:
        raise ValueError("No active Food.com users found after recipe filtering.")
    eligible_users = set(
        user_counts[user_counts >= min_user_interactions]
        .sort_values(ascending=False)
        .head(max_users)
        .index.astype(int)
        .tolist()
    )
    logger.info("Eligible user ids after count filter: %s", len(eligible_users))

    frames: list[pd.DataFrame] = []
    logger.info("Building filtered interaction subset...")
    for chunk in pd.read_csv(interactions_file, usecols=interaction_cols, chunksize=chunk_size):
        chunk["user_id"] = pd.to_numeric(chunk["user_id"], errors="coerce")
        chunk["recipe_id"] = pd.to_numeric(chunk["recipe_id"], errors="coerce")
        chunk["rating"] = pd.to_numeric(chunk["rating"], errors="coerce")
        chunk = chunk.dropna(subset=["user_id", "recipe_id", "rating", "date"])
        chunk["user_id"] = chunk["user_id"].astype(int)
        chunk["recipe_id"] = chunk["recipe_id"].astype(int)
        chunk = chunk[
            (chunk["rating"] > 0)
            & chunk["recipe_id"].isin(eligible_recipes)
            & chunk["user_id"].isin(eligible_users)
        ].copy()
        if not chunk.empty:
            frames.append(chunk)

    if not frames:
        raise ValueError("Filtered Food.com interactions are empty.")
    interactions = pd.concat(frames, ignore_index=True)
    interactions["rating"] = interactions["rating"].astype(float)
    interactions["timestamp"] = interactions["date"].map(_unix_timestamp).astype(int)
    interactions = interactions.sort_values(["timestamp", "user_id", "recipe_id"], ascending=[False, True, True])
    interactions = interactions.head(max_interactions).copy()
    interactions = interactions.drop_duplicates(["user_id", "recipe_id", "timestamp"])
    return interactions, raw_rows


def convert_foodcom(
    input_dir: str | Path | None = None,
    output_dir: str | Path | None = None,
    min_recipe_interactions: int = DEFAULT_MIN_RECIPE_INTERACTIONS,
    min_user_interactions: int = DEFAULT_MIN_USER_INTERACTIONS,
    max_recipes: int = DEFAULT_MAX_RECIPES,
    max_users: int = DEFAULT_MAX_USERS,
    max_interactions: int = DEFAULT_MAX_INTERACTIONS,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> dict:
    source_dir = Path(input_dir).resolve() if input_dir else DEFAULT_INPUT_DIR
    output_path = Path(output_dir).resolve() if output_dir else DEFAULT_OUTPUT_DIR
    recipes_file = source_dir / "RAW_recipes.csv"
    interactions_file = source_dir / "RAW_interactions.csv"

    if not recipes_file.exists():
        raise FileNotFoundError(f"RAW_recipes.csv not found: {recipes_file}")
    if not interactions_file.exists():
        raise FileNotFoundError(f"RAW_interactions.csv not found: {interactions_file}")
    if min_recipe_interactions < 1 or min_user_interactions < 1:
        raise ValueError("min interaction thresholds must be positive.")
    if max_recipes < 1 or max_users < 1 or max_interactions < 1:
        raise ValueError("max limits must be positive.")

    logger.info("Food.com input directory: %s", source_dir)
    logger.info("Canonical output directory: %s", output_path)

    recipe_cols = [
        "id",
        "name",
        "minutes",
        "submitted",
        "tags",
        "nutrition",
        "n_steps",
        "ingredients",
        "n_ingredients",
    ]
    recipes = pd.read_csv(recipes_file, usecols=recipe_cols)
    raw_recipe_rows = int(len(recipes))
    required_recipe_cols = {"id", "name", "minutes", "submitted", "tags", "nutrition", "n_steps", "description", "ingredients", "n_ingredients"}
    required_interaction_cols = {"user_id", "recipe_id", "date", "rating"}
    recipe_missing = sorted((required_recipe_cols - {"description"}) - set(recipes.columns))
    interaction_header = set(pd.read_csv(interactions_file, nrows=0).columns)
    interaction_missing = sorted(required_interaction_cols - interaction_header)
    if recipe_missing:
        raise ValueError(f"RAW_recipes.csv missing columns: {recipe_missing}")
    if interaction_missing:
        raise ValueError(f"RAW_interactions.csv missing columns: {interaction_missing}")

    interactions, raw_interaction_rows = _read_interactions_subset(
        interactions_file,
        min_recipe_interactions,
        min_user_interactions,
        max_recipes,
        max_users,
        max_interactions,
        chunk_size,
    )

    valid_recipe_ids = set(interactions["recipe_id"].unique())
    recipes["id"] = pd.to_numeric(recipes["id"], errors="coerce")
    recipes = recipes.dropna(subset=["id", "name"]).copy()
    recipes["id"] = recipes["id"].astype(int)
    recipes = recipes[recipes["id"].isin(valid_recipe_ids)].drop_duplicates("id").copy()
    valid_recipe_ids = set(recipes["id"].unique())
    interactions = interactions[interactions["recipe_id"].isin(valid_recipe_ids)].copy()

    if interactions.empty or recipes.empty:
        raise ValueError("Converted Food.com subset is empty. Relax thresholds or increase limits.")

    recipes["tag_list"] = recipes["tags"].map(_literal_list)
    recipes["ingredient_list"] = recipes["ingredients"].map(_literal_list)
    recipes["nutrition_list"] = recipes["nutrition"].map(_safe_nutrition)
    recipes["genres"] = recipes["tag_list"].map(lambda values: _join_tokens(values, limit=24))
    recipes["ingredient_text"] = recipes["ingredient_list"].map(lambda values: _join_tokens(values, limit=40))
    recipes["year"] = recipes["submitted"].map(_parse_year)
    recipes["title"] = recipes["name"].fillna("").astype(str).str.strip()
    recipes["title"] = recipes["title"].where(recipes["title"] != "", "Untitled recipe")
    recipes["movie_title"] = recipes["title"] + " (" + recipes["year"].fillna(0).astype(int).astype(str) + ")"

    nutrition_cols = [
        "calories",
        "total_fat_pct",
        "sugar_pct",
        "sodium_pct",
        "protein_pct",
        "saturated_fat_pct",
        "carbohydrates_pct",
    ]
    nutrition = pd.DataFrame(recipes["nutrition_list"].tolist(), columns=nutrition_cols, index=recipes.index)
    recipes = pd.concat([recipes, nutrition], axis=1)

    ratings = interactions.rename(columns={"user_id": "userId", "recipe_id": "movieId"})[
        ["userId", "movieId", "rating", "timestamp"]
    ].copy()
    ratings = ratings.sort_values(["userId", "timestamp", "movieId"])

    movies = pd.DataFrame(
        {
            "movieId": recipes["id"].astype(int),
            "title": recipes["movie_title"],
            "genres": recipes["genres"].replace("", "recipe"),
        }
    ).sort_values("movieId")

    tag_rows: list[dict] = []
    for row in recipes.itertuples(index=False):
        recipe_id = int(row.id)
        for tag in row.tag_list[:30]:
            cleaned = _clean_token(tag)
            if cleaned:
                tag_rows.append({"userId": 0, "movieId": recipe_id, "tag": cleaned, "timestamp": 0})
        for ingredient in row.ingredient_list[:20]:
            cleaned = _clean_token(ingredient)
            if cleaned:
                tag_rows.append({"userId": 0, "movieId": recipe_id, "tag": f"ingredient:{cleaned}", "timestamp": 0})
    tags = pd.DataFrame(tag_rows).drop_duplicates(["movieId", "tag"])

    links = pd.DataFrame(
        {
            "movieId": recipes["id"].astype(int),
            "imdbId": recipes["id"].astype(int),
            "tmdbId": recipes["id"].astype(int),
        }
    ).sort_values("movieId")

    metadata = pd.DataFrame(
        {
            "recipe_id": recipes["id"].astype(int),
            "name": recipes["title"],
            "minutes": pd.to_numeric(recipes["minutes"], errors="coerce").fillna(0).astype(int),
            "submitted": recipes["submitted"].fillna(""),
            "tags": recipes["genres"],
            "ingredients": recipes["ingredient_text"],
            "description": "",
            "n_steps": pd.to_numeric(recipes["n_steps"], errors="coerce").fillna(0).astype(int),
            "n_ingredients": pd.to_numeric(recipes["n_ingredients"], errors="coerce").fillna(0).astype(int),
            **{col: recipes[col] for col in nutrition_cols},
        }
    ).sort_values("recipe_id")

    _prepare_output_dir(output_path)
    ratings.to_csv(output_path / "ratings.csv", index=False)
    movies.to_csv(output_path / "movies.csv", index=False)
    tags.to_csv(output_path / "tags.csv", index=False)
    links.to_csv(output_path / "links.csv", index=False)
    metadata.to_csv(output_path / "recipe_metadata.csv", index=False)

    readme_src = source_dir / "README.md"
    if readme_src.exists():
        shutil.copy2(readme_src, output_path / "README.foodcom.md")

    summary = {
        "input_dir": str(source_dir),
        "output_dir": str(output_path),
        "raw_recipe_rows": raw_recipe_rows,
        "raw_interaction_rows": raw_interaction_rows,
        "ratings_rows": int(len(ratings)),
        "recipe_rows": int(len(movies)),
        "tag_rows": int(len(tags)),
        "user_count": int(ratings["userId"].nunique()),
        "recipe_count": int(ratings["movieId"].nunique()),
        "min_recipe_interactions": int(min_recipe_interactions),
        "min_user_interactions": int(min_user_interactions),
        "max_recipes": int(max_recipes),
        "max_users": int(max_users),
        "max_interactions": int(max_interactions),
        "files": {file_name: str(output_path / file_name) for file_name in OUTPUT_FILES},
    }
    logger.info("Food.com conversion summary: %s", summary)
    return summary


def main() -> None:
    args = parse_args()
    convert_foodcom(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        min_recipe_interactions=args.min_recipe_interactions,
        min_user_interactions=args.min_user_interactions,
        max_recipes=args.max_recipes,
        max_users=args.max_users,
        max_interactions=args.max_interactions,
        chunk_size=args.chunk_size,
    )


if __name__ == "__main__":
    main()
