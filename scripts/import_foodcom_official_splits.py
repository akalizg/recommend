"""
Import the official Food.com train/validation/test interaction splits.

The project still uses historical MovieLens-compatible column names internally:
userId means Food.com user_id, and movieId means recipe_id. This script keeps
the official split boundary intact while producing the CSV files consumed by
the existing Spark, ranking, and evaluation stages.
"""
from __future__ import annotations

import argparse
import ast
import logging
from pathlib import Path
from typing import Iterable

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SPLIT_DIR = PROJECT_ROOT / "data"
DEFAULT_RECIPE_FILE = PROJECT_ROOT / "data" / "food-com" / "RAW_recipes.csv"
DEFAULT_CANONICAL_DIR = PROJECT_ROOT / "data" / "recipe-canonical"
DEFAULT_PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
SPLIT_FILES = {
    "train": "interactions_train.csv",
    "valid": "interactions_validation.csv",
    "test": "interactions_test.csv",
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import official Food.com interaction splits.")
    parser.add_argument("--split-dir", default=str(DEFAULT_SPLIT_DIR), help="Directory with interactions_*.csv files.")
    parser.add_argument("--recipe-file", default=str(DEFAULT_RECIPE_FILE), help="RAW_recipes.csv file.")
    parser.add_argument("--canonical-dir", default=str(DEFAULT_CANONICAL_DIR), help="Canonical recipe output directory.")
    parser.add_argument("--processed-dir", default=str(DEFAULT_PROCESSED_DIR), help="Processed pipeline output directory.")
    parser.add_argument("--max-train-interactions", type=int, default=0, help="Optional train row cap; 0 means full train split.")
    parser.add_argument("--max-users", type=int, default=0, help="Optional cap by most active train users; 0 means all users.")
    parser.add_argument("--max-recipes", type=int, default=0, help="Optional cap by most interacted train recipes; 0 means all recipes.")
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


def _read_split(path: Path, split_name: str) -> pd.DataFrame:
    required = {"user_id", "recipe_id", "date", "rating"}
    header = set(pd.read_csv(path, nrows=0).columns)
    missing = sorted(required - header)
    if missing:
        raise ValueError(f"{path} missing columns: {missing}")

    df = pd.read_csv(path, usecols=["user_id", "recipe_id", "date", "rating"])
    df["user_id"] = pd.to_numeric(df["user_id"], errors="coerce")
    df["recipe_id"] = pd.to_numeric(df["recipe_id"], errors="coerce")
    df["rating"] = pd.to_numeric(df["rating"], errors="coerce")
    df = df.dropna(subset=["user_id", "recipe_id", "rating", "date"]).copy()
    df["user_id"] = df["user_id"].astype(int)
    df["recipe_id"] = df["recipe_id"].astype(int)
    df["rating"] = df["rating"].astype(float)
    df["timestamp"] = df["date"].map(_unix_timestamp).astype(int)
    df["split"] = split_name
    return df


def _to_pipeline_ratings(df: pd.DataFrame) -> pd.DataFrame:
    ratings = df.rename(columns={"user_id": "userId", "recipe_id": "movieId"})[
        ["userId", "movieId", "rating", "timestamp"]
    ].copy()
    ratings["rating_norm"] = ratings["rating"] / 5.0
    ratings = ratings[["userId", "movieId", "rating", "rating_norm", "timestamp"]]
    return ratings.sort_values(["userId", "timestamp", "movieId"]).drop_duplicates(
        ["userId", "movieId", "timestamp"],
        keep="last",
    )


def _build_recipe_tables(recipes: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    recipes = recipes.copy()
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

    movies = pd.DataFrame(
        {
            "movieId": recipes["id"].astype(int),
            "title": recipes["movie_title"],
            "genres": recipes["genres"].replace("", "recipe"),
        }
    ).sort_values("movieId")

    movies_clean = pd.DataFrame(
        {
            "movieId": recipes["id"].astype(int),
            "title": recipes["movie_title"],
            "clean_title": recipes["title"],
            "year": recipes["year"].fillna(0).astype(int),
            "genres": recipes["genres"].replace("", "recipe"),
        }
    ).sort_values("movieId")
    movies_clean["genre_count"] = movies_clean["genres"].map(lambda value: len([item for item in str(value).split("|") if item]))

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
    tags = pd.DataFrame(tag_rows).drop_duplicates(["movieId", "tag"]) if tag_rows else pd.DataFrame(columns=["userId", "movieId", "tag", "timestamp"])
    movie_tags = tags[["movieId", "tag"]].copy()
    movie_tags["tag_type"] = movie_tags["tag"].map(lambda value: "ingredient" if str(value).startswith("ingredient:") else "recipe_tag")
    movie_tags = movie_tags.drop_duplicates(["movieId", "tag", "tag_type"]).sort_values(["movieId", "tag"])

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
            "description": recipes.get("description", "").fillna("") if "description" in recipes.columns else "",
            "n_steps": pd.to_numeric(recipes["n_steps"], errors="coerce").fillna(0).astype(int),
            "n_ingredients": pd.to_numeric(recipes["n_ingredients"], errors="coerce").fillna(0).astype(int),
            **{col: recipes[col] for col in nutrition_cols},
        }
    ).sort_values("recipe_id")
    return movies, movies_clean, tags, movie_tags, links, metadata


def import_official_splits(
    split_dir: str | Path | None = None,
    recipe_file: str | Path | None = None,
    canonical_dir: str | Path | None = None,
    processed_dir: str | Path | None = None,
    max_train_interactions: int = 0,
    max_users: int = 0,
    max_recipes: int = 0,
) -> dict:
    split_path = Path(split_dir).resolve() if split_dir else DEFAULT_SPLIT_DIR
    recipe_path = Path(recipe_file).resolve() if recipe_file else DEFAULT_RECIPE_FILE
    canonical_path = Path(canonical_dir).resolve() if canonical_dir else DEFAULT_CANONICAL_DIR
    processed_path = Path(processed_dir).resolve() if processed_dir else DEFAULT_PROCESSED_DIR

    split_files = {name: split_path / file_name for name, file_name in SPLIT_FILES.items()}
    missing_files = [str(path) for path in [recipe_path, *split_files.values()] if not path.exists()]
    if missing_files:
        raise FileNotFoundError(f"Missing required Food.com files: {missing_files}")
    if max_train_interactions < 0 or max_users < 0 or max_recipes < 0:
        raise ValueError("max limits must be zero or positive.")

    splits = {name: _read_split(path, name) for name, path in split_files.items()}
    train = splits["train"]
    if max_users:
        keep_users = set(train["user_id"].value_counts().head(max_users).index.astype(int))
        splits = {name: df[df["user_id"].isin(keep_users)].copy() for name, df in splits.items()}
        train = splits["train"]
    if max_recipes:
        keep_recipes = set(train["recipe_id"].value_counts().head(max_recipes).index.astype(int))
        splits = {name: df[df["recipe_id"].isin(keep_recipes)].copy() for name, df in splits.items()}
        train = splits["train"]
    if max_train_interactions:
        train = train.sort_values(["timestamp", "user_id", "recipe_id"], ascending=[False, True, True]).head(max_train_interactions)
        splits["train"] = train.copy()

    all_interactions = pd.concat(splits.values(), ignore_index=True)
    if all_interactions.empty:
        raise ValueError("Official split import produced no interactions.")

    recipe_cols = [
        "id",
        "name",
        "minutes",
        "submitted",
        "tags",
        "nutrition",
        "n_steps",
        "description",
        "ingredients",
        "n_ingredients",
    ]
    recipes = pd.read_csv(recipe_path, usecols=lambda col: col in recipe_cols)
    if "description" not in recipes.columns:
        recipes["description"] = ""
    recipes["id"] = pd.to_numeric(recipes["id"], errors="coerce")
    recipes = recipes.dropna(subset=["id", "name"]).copy()
    recipes["id"] = recipes["id"].astype(int)

    valid_recipe_ids = set(all_interactions["recipe_id"].unique())
    recipes = recipes[recipes["id"].isin(valid_recipe_ids)].drop_duplicates("id").copy()
    valid_recipe_ids = set(recipes["id"].unique())
    splits = {name: df[df["recipe_id"].isin(valid_recipe_ids)].copy() for name, df in splits.items()}
    all_interactions = pd.concat(splits.values(), ignore_index=True)
    if recipes.empty or all_interactions.empty:
        raise ValueError("No official split interactions matched RAW_recipes.csv.")

    ratings_by_split = {name: _to_pipeline_ratings(df) for name, df in splits.items()}
    ratings_all = pd.concat(ratings_by_split.values(), ignore_index=True).sort_values(["userId", "timestamp", "movieId"])
    canonical_ratings = ratings_all[["userId", "movieId", "rating", "timestamp"]]
    movies, movies_clean, tags, movie_tags, links, metadata = _build_recipe_tables(recipes)

    canonical_path.mkdir(parents=True, exist_ok=True)
    processed_path.mkdir(parents=True, exist_ok=True)

    canonical_ratings.to_csv(canonical_path / "ratings.csv", index=False)
    movies.to_csv(canonical_path / "movies.csv", index=False)
    tags.to_csv(canonical_path / "tags.csv", index=False)
    links.to_csv(canonical_path / "links.csv", index=False)
    metadata.to_csv(canonical_path / "recipe_metadata.csv", index=False)

    ratings_all.to_csv(processed_path / "ratings_clean.csv", index=False)
    ratings_by_split["train"].to_csv(processed_path / "train_ratings.csv", index=False)
    ratings_by_split["valid"].to_csv(processed_path / "valid_ratings.csv", index=False)
    ratings_by_split["test"].to_csv(processed_path / "test_ratings.csv", index=False)
    movies_clean.to_csv(processed_path / "movies_clean.csv", index=False)
    movie_tags.to_csv(processed_path / "movie_tags.csv", index=False)

    summary = {
        "split_dir": str(split_path),
        "recipe_file": str(recipe_path),
        "canonical_dir": str(canonical_path),
        "processed_dir": str(processed_path),
        "train_rows": int(len(ratings_by_split["train"])),
        "valid_rows": int(len(ratings_by_split["valid"])),
        "test_rows": int(len(ratings_by_split["test"])),
        "ratings_rows": int(len(ratings_all)),
        "user_count": int(ratings_all["userId"].nunique()),
        "recipe_count": int(ratings_all["movieId"].nunique()),
        "recipe_metadata_rows": int(len(metadata)),
        "movie_tag_rows": int(len(movie_tags)),
    }
    logger.info("Official Food.com split import summary: %s", summary)
    return summary


def main() -> None:
    args = parse_args()
    import_official_splits(
        split_dir=args.split_dir,
        recipe_file=args.recipe_file,
        canonical_dir=args.canonical_dir,
        processed_dir=args.processed_dir,
        max_train_interactions=args.max_train_interactions,
        max_users=args.max_users,
        max_recipes=args.max_recipes,
    )


if __name__ == "__main__":
    main()
