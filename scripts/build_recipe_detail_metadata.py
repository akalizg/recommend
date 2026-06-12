"""Build a compact recipe detail table from Food.com enhanced V3."""
from __future__ import annotations

import argparse
import ast
import json
import logging
import re
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ENHANCED = PROJECT_ROOT / "data" / "recipe_enhanced_v3.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "recipe-canonical" / "recipe_detail_metadata.csv"

NUTRITION_LABELS = [
    "calories",
    "total_fat_pct",
    "sugar_pct",
    "sodium_pct",
    "protein_pct",
    "saturated_fat_pct",
    "carbohydrates_pct",
]

DETAIL_COLUMNS = [
    "id",
    "name",
    "minutes",
    "submitted",
    "tags",
    "nutrition",
    "n_steps",
    "steps",
    "description",
    "ingredients",
    "n_ingredients",
    "quantities",
    "serves",
    "has_image",
    "image_url",
    "recipe_yield_raw",
    "recipe_yield_min",
    "recipe_yield_max",
    "serves_best_guess",
    "yield_unit_raw",
    "yield_type",
    "ready_in_display",
    "author_name",
    "photo_count",
    "rating_value",
    "review_count",
]

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build compact Food.com recipe detail metadata.")
    parser.add_argument("--enhanced", default=str(DEFAULT_ENHANCED), help="Food.com enhanced V3 CSV.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output detail metadata CSV.")
    return parser.parse_args()


def _literal_list(value: object) -> list:
    if value is None or pd.isna(value):
        return []
    if isinstance(value, list):
        return value
    try:
        parsed = ast.literal_eval(str(value))
    except (SyntaxError, ValueError):
        return []
    return parsed if isinstance(parsed, list) else []


def _json_list(value: object) -> str:
    values = [str(item).strip() for item in _literal_list(value) if str(item).strip()]
    return json.dumps(values, ensure_ascii=False)


def _nutrition_json(value: object) -> str:
    values = _literal_list(value)
    result = {}
    for index, label in enumerate(NUTRITION_LABELS):
        try:
            result[label] = float(values[index])
        except (IndexError, TypeError, ValueError):
            result[label] = None
    return json.dumps(result, ensure_ascii=False)


def _slugify(name: object) -> str:
    text = "" if name is None or pd.isna(name) else str(name).lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "recipe"


def _source_url(row: pd.Series) -> str:
    return f"https://www.food.com/recipe/{_slugify(row.get('name'))}-{int(row['recipe_id'])}"


def build_recipe_detail_metadata(
    enhanced_path: str | Path | None = None,
    output_path: str | Path | None = None,
) -> dict:
    enhanced_file = Path(enhanced_path).resolve() if enhanced_path else DEFAULT_ENHANCED
    output_file = Path(output_path).resolve() if output_path else DEFAULT_OUTPUT
    if not enhanced_file.exists():
        raise FileNotFoundError(f"Enhanced recipe CSV not found: {enhanced_file}")

    header = pd.read_csv(enhanced_file, nrows=0).columns.tolist()
    missing = sorted(set(DETAIL_COLUMNS) - set(header))
    if missing:
        raise ValueError(f"Enhanced recipe CSV missing columns: {missing}")

    df = pd.read_csv(enhanced_file, usecols=DETAIL_COLUMNS)
    df["id"] = pd.to_numeric(df["id"], errors="coerce")
    df = df.dropna(subset=["id"]).copy()
    df["id"] = df["id"].astype(int)
    df = df.drop_duplicates("id")

    detail = pd.DataFrame(
        {
            "recipe_id": df["id"],
            "name": df["name"].fillna("").astype(str),
            "description": df["description"].fillna("").astype(str),
            "minutes": pd.to_numeric(df["minutes"], errors="coerce"),
            "submitted": df["submitted"].fillna("").astype(str),
            "tags_json": df["tags"].map(_json_list),
            "ingredients_json": df["ingredients"].map(_json_list),
            "quantities_json": df["quantities"].map(_json_list),
            "steps_json": df["steps"].map(_json_list),
            "nutrition_json": df["nutrition"].map(_nutrition_json),
            "n_steps": pd.to_numeric(df["n_steps"], errors="coerce"),
            "n_ingredients": pd.to_numeric(df["n_ingredients"], errors="coerce"),
            "serves": df["serves"].fillna("").astype(str),
            "has_image": pd.to_numeric(df["has_image"], errors="coerce").fillna(0).astype(int),
            "image_url": df["image_url"].fillna("").astype(str).str.strip(),
            "recipe_yield_raw": df["recipe_yield_raw"].fillna("").astype(str),
            "recipe_yield_min": pd.to_numeric(df["recipe_yield_min"], errors="coerce"),
            "recipe_yield_max": pd.to_numeric(df["recipe_yield_max"], errors="coerce"),
            "serves_best_guess": pd.to_numeric(df["serves_best_guess"], errors="coerce"),
            "yield_unit_raw": df["yield_unit_raw"].fillna("").astype(str),
            "yield_type": df["yield_type"].fillna("").astype(str),
            "ready_in_display": df["ready_in_display"].fillna("").astype(str),
            "author_name": df["author_name"].fillna("").astype(str),
            "photo_count": pd.to_numeric(df["photo_count"], errors="coerce"),
            "rating_value": pd.to_numeric(df["rating_value"], errors="coerce"),
            "review_count": pd.to_numeric(df["review_count"], errors="coerce"),
        }
    )
    detail["source_url"] = detail.apply(_source_url, axis=1)

    output_file.parent.mkdir(parents=True, exist_ok=True)
    detail.to_csv(output_file, index=False, encoding="utf-8-sig")
    summary = {
        "input_rows": int(len(df)),
        "output_rows": int(len(detail)),
        "with_image": int((detail["image_url"].astype(str).str.len() > 0).sum()),
        "output_path": str(output_file),
    }
    logger.info("Recipe detail metadata summary: %s", summary)
    return summary


def main() -> None:
    args = parse_args()
    build_recipe_detail_metadata(args.enhanced, args.output)


if __name__ == "__main__":
    main()
