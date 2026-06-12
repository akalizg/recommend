"""Merge Food.com enhanced V3 image/detail metadata into recipe artifacts."""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ENHANCED = PROJECT_ROOT / "data" / "recipe_enhanced_v3.csv"
DEFAULT_PROFILE = PROJECT_ROOT / "data" / "features" / "movie_profile.csv"
DEFAULT_RECOMMENDATIONS = PROJECT_ROOT / "data" / "final" / "recommendations_with_reasons.csv"
DEFAULT_METADATA_OUTPUT = PROJECT_ROOT / "data" / "recipe-canonical" / "recipe_enhanced_metadata.csv"

ENHANCED_COLUMNS = [
    "id",
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

PROFILE_COLUMNS = [column for column in ENHANCED_COLUMNS if column != "id"]
RECOMMENDATION_COLUMNS = [
    "image_url",
    "recipe_yield_raw",
    "serves_best_guess",
    "ready_in_display",
    "author_name",
    "photo_count",
    "rating_value",
    "review_count",
]

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Enrich recipe profile/recommendation artifacts with image metadata.")
    parser.add_argument("--enhanced", default=str(DEFAULT_ENHANCED), help="Food.com enhanced V3 CSV.")
    parser.add_argument("--profile", default=str(DEFAULT_PROFILE), help="movie_profile.csv to update in place.")
    parser.add_argument("--recommendations", default=str(DEFAULT_RECOMMENDATIONS), help="recommendations_with_reasons.csv to update in place.")
    parser.add_argument("--metadata-output", default=str(DEFAULT_METADATA_OUTPUT), help="Compact enhanced metadata output.")
    return parser.parse_args()


def _read_enhanced(path: Path) -> pd.DataFrame:
    header = pd.read_csv(path, nrows=0).columns.tolist()
    missing = sorted(set(ENHANCED_COLUMNS) - set(header))
    if missing:
        raise ValueError(f"Enhanced recipe CSV missing columns: {missing}")

    df = pd.read_csv(path, usecols=ENHANCED_COLUMNS)
    df["id"] = pd.to_numeric(df["id"], errors="coerce")
    df = df.dropna(subset=["id"]).copy()
    df["id"] = df["id"].astype(int)
    df = df.drop_duplicates("id")
    df["image_url"] = df["image_url"].fillna("").astype(str).str.strip()
    df["has_image"] = pd.to_numeric(df["has_image"], errors="coerce").fillna(0).astype(int)
    return df


def _drop_existing(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    existing = [column for column in columns if column in df.columns]
    return df.drop(columns=existing) if existing else df


def enrich_recipe_images(
    enhanced_path: str | Path | None = None,
    profile_path: str | Path | None = None,
    recommendations_path: str | Path | None = None,
    metadata_output_path: str | Path | None = None,
) -> dict:
    enhanced_file = Path(enhanced_path).resolve() if enhanced_path else DEFAULT_ENHANCED
    profile_file = Path(profile_path).resolve() if profile_path else DEFAULT_PROFILE
    recommendations_file = Path(recommendations_path).resolve() if recommendations_path else DEFAULT_RECOMMENDATIONS
    metadata_output = Path(metadata_output_path).resolve() if metadata_output_path else DEFAULT_METADATA_OUTPUT

    for path in (enhanced_file, profile_file, recommendations_file):
        if not path.exists():
            raise FileNotFoundError(f"Required file not found: {path}")

    enhanced = _read_enhanced(enhanced_file)
    metadata_output.parent.mkdir(parents=True, exist_ok=True)
    enhanced.to_csv(metadata_output, index=False, encoding="utf-8-sig")

    profile = pd.read_csv(profile_file)
    if "movieId" not in profile.columns:
        raise ValueError(f"{profile_file} missing movieId")
    profile["movieId"] = pd.to_numeric(profile["movieId"], errors="coerce").astype("Int64")
    profile = _drop_existing(profile, PROFILE_COLUMNS)
    profile = profile.merge(
        enhanced.rename(columns={"id": "movieId"})[["movieId", *PROFILE_COLUMNS]],
        on="movieId",
        how="left",
    )
    profile["image_url"] = profile["image_url"].fillna("")
    profile["has_image"] = pd.to_numeric(profile["has_image"], errors="coerce").fillna(0).astype(int)
    profile.to_csv(profile_file, index=False, encoding="utf-8-sig")

    recs = pd.read_csv(recommendations_file)
    if "movieId" not in recs.columns:
        raise ValueError(f"{recommendations_file} missing movieId")
    recs["movieId"] = pd.to_numeric(recs["movieId"], errors="coerce").astype("Int64")
    recs = _drop_existing(recs, RECOMMENDATION_COLUMNS)
    recs = recs.merge(
        enhanced.rename(columns={"id": "movieId"})[["movieId", *RECOMMENDATION_COLUMNS]],
        on="movieId",
        how="left",
    )
    recs["image_url"] = recs["image_url"].fillna("")
    recs.to_csv(recommendations_file, index=False, encoding="utf-8-sig")

    profile_image_count = int((profile["image_url"].astype(str).str.len() > 0).sum())
    rec_image_count = int((recs["image_url"].astype(str).str.len() > 0).sum())
    summary = {
        "enhanced_rows": int(len(enhanced)),
        "profile_rows": int(len(profile)),
        "profile_rows_with_image": profile_image_count,
        "profile_image_coverage": float(profile_image_count / len(profile)) if len(profile) else 0.0,
        "recommendation_rows": int(len(recs)),
        "recommendation_rows_with_image": rec_image_count,
        "recommendation_image_coverage": float(rec_image_count / len(recs)) if len(recs) else 0.0,
        "metadata_output": str(metadata_output),
        "profile_output": str(profile_file),
        "recommendations_output": str(recommendations_file),
    }
    logger.info("Recipe image enrichment summary: %s", summary)
    return summary


def main() -> None:
    args = parse_args()
    enrich_recipe_images(args.enhanced, args.profile, args.recommendations, args.metadata_output)


if __name__ == "__main__":
    main()
