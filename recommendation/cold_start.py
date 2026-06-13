from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.config import PROJECT_ROOT


DEFAULT_PROFILE = PROJECT_ROOT / "data" / "features" / "movie_profile.csv"
DEFAULT_METADATA = PROJECT_ROOT / "data" / "recipe-canonical" / "recipe_metadata.csv"

PROFILE_COLS = [
    "movieId",
    "title",
    "clean_title",
    "genres",
    "tag_text",
    "movie_avg_rating",
    "movie_rating_count",
    "movie_popularity",
    "has_image",
    "image_url",
    "ready_in_display",
    "recipe_yield_raw",
    "author_name",
    "review_count",
    "rating_value",
]
METADATA_COLS = [
    "recipe_id",
    "minutes",
    "n_steps",
    "n_ingredients",
    "calories",
    "total_fat_pct",
    "sugar_pct",
    "sodium_pct",
    "protein_pct",
    "saturated_fat_pct",
    "carbohydrates_pct",
]

_TABLE_CACHE: dict[str, Any] = {}


def cold_start_recommend(
    preferred_tags: list[str] | None = None,
    ingredients: list[str] | None = None,
    dietary_goals: list[str] | None = None,
    max_minutes: int | None = None,
    min_rating: float | None = None,
    require_image: bool = False,
    limit: int = 20,
    profile_path: str | Path = DEFAULT_PROFILE,
    metadata_path: str | Path = DEFAULT_METADATA,
) -> dict[str, Any]:
    if limit <= 0:
        raise ValueError("推荐数量必须大于 0")

    profile = _load_profile(Path(profile_path))
    metadata = _load_metadata(Path(metadata_path))
    df = profile.merge(metadata, left_on="movieId", right_on="recipe_id", how="left")

    terms = _normalize_terms([*(preferred_tags or []), *(ingredients or []), *(dietary_goals or [])])
    tag_terms = _normalize_terms(preferred_tags or [])
    ingredient_terms = _normalize_terms(ingredients or [])
    goal_terms = _normalize_terms(dietary_goals or [])

    df["movie_avg_rating"] = _numeric_column(df, "movie_avg_rating")
    df["movie_rating_count"] = _numeric_column(df, "movie_rating_count")
    df["movie_popularity"] = _numeric_column(df, "movie_popularity")
    df["has_image"] = _numeric_column(df, "has_image")
    df["minutes"] = _numeric_column(df, "minutes", np.nan)

    if min_rating is not None:
        df = df[df["movie_avg_rating"] >= float(min_rating)].copy()
    if require_image:
        df = df[df["has_image"] > 0].copy()

    if df.empty:
        return {"recommendations": [], "total": 0, "source": "content_cold_start"}

    text = _combined_text(df)
    preference_score = _term_match_score(text, terms)
    tag_score = _term_match_score(text, tag_terms)
    ingredient_score = _term_match_score(text, ingredient_terms)
    goal_score = _dietary_goal_score(df, goal_terms)
    time_score = _time_score(df, max_minutes)
    rating_score = (df["movie_avg_rating"].clip(0, 5) / 5.0).to_numpy(dtype=float)
    popularity = np.log1p(df["movie_rating_count"].clip(lower=0).to_numpy(dtype=float))
    popularity_score = popularity / popularity.max() if popularity.max() > 0 else popularity
    image_score = df["has_image"].clip(0, 1).to_numpy(dtype=float)

    if terms:
        score = (
            0.34 * preference_score
            + 0.18 * ingredient_score
            + 0.16 * tag_score
            + 0.12 * goal_score
            + 0.08 * time_score
            + 0.08 * rating_score
            + 0.03 * popularity_score
            + 0.01 * image_score
        )
    else:
        score = 0.45 * rating_score + 0.35 * popularity_score + 0.15 * image_score + 0.05 * time_score

    df = df.assign(_cold_start_score=score)
    candidate_count = min(max(limit * 8, 80), len(df))
    candidates = df.sort_values(
        ["_cold_start_score", "movie_avg_rating", "movie_rating_count", "movieId"],
        ascending=[False, False, False, True],
    ).head(candidate_count)
    selected = _diverse_select(candidates, limit)
    return {
        "recommendations": [_item_from_row(row) for row in selected.to_dict(orient="records")],
        "total": int(len(selected)),
        "source": "content_cold_start_hot_diverse",
        "preference_profile": {
            "preferred_tags": preferred_tags or [],
            "ingredients": ingredients or [],
            "dietary_goals": dietary_goals or [],
            "max_minutes": max_minutes,
            "min_rating": min_rating,
            "require_image": require_image,
        },
    }


def _load_profile(path: Path) -> pd.DataFrame:
    key = f"profile:{path}:{path.stat().st_mtime_ns if path.exists() else 0}"
    cached = _TABLE_CACHE.get(key)
    if cached is not None:
        return cached
    if not path.exists():
        raise FileNotFoundError(f"食谱画像文件不存在：{path}")
    usecols = [col for col in PROFILE_COLS if col in pd.read_csv(path, nrows=0).columns]
    df = pd.read_csv(path, usecols=usecols)
    if "movieId" not in df.columns:
        raise ValueError(f"{path} 缺少 movieId 字段")
    df["movieId"] = pd.to_numeric(df["movieId"], errors="coerce")
    df = df.dropna(subset=["movieId"]).drop_duplicates("movieId").copy()
    df["movieId"] = df["movieId"].astype(int)
    _TABLE_CACHE.clear()
    _TABLE_CACHE[key] = df
    return df


def _load_metadata(path: Path) -> pd.DataFrame:
    key = f"metadata:{path}:{path.stat().st_mtime_ns if path.exists() else 0}"
    cached = _TABLE_CACHE.get(key)
    if cached is not None:
        return cached
    if not path.exists():
        return pd.DataFrame({"recipe_id": pd.Series(dtype=int)})
    usecols = [col for col in METADATA_COLS if col in pd.read_csv(path, nrows=0).columns]
    df = pd.read_csv(path, usecols=usecols)
    if "recipe_id" not in df.columns:
        return pd.DataFrame({"recipe_id": pd.Series(dtype=int)})
    df["recipe_id"] = pd.to_numeric(df["recipe_id"], errors="coerce")
    df = df.dropna(subset=["recipe_id"]).drop_duplicates("recipe_id").copy()
    df["recipe_id"] = df["recipe_id"].astype(int)
    _TABLE_CACHE[key] = df
    return df


def _normalize_terms(values: list[str]) -> list[str]:
    terms = []
    for value in values:
        text = str(value or "").strip().lower()
        if not text:
            continue
        terms.extend(part for part in re.split(r"[|,;/]+", text) if part.strip())
    return sorted({term.strip() for term in terms if term.strip()})


def _combined_text(df: pd.DataFrame) -> pd.Series:
    columns = [col for col in ["title", "clean_title", "genres", "tag_text"] if col in df.columns]
    if not columns:
        return pd.Series([""] * len(df), index=df.index)
    return df[columns].fillna("").astype(str).agg(" ".join, axis=1).str.lower()


def _numeric_column(df: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in df.columns:
        return pd.Series(default, index=df.index, dtype=float)
    return pd.to_numeric(df[column], errors="coerce").fillna(default)


def _term_match_score(text: pd.Series, terms: list[str]) -> np.ndarray:
    if not terms:
        return np.zeros(len(text), dtype=float)
    score = np.zeros(len(text), dtype=float)
    for term in terms:
        score += text.str.contains(re.escape(term), regex=True, na=False).to_numpy(dtype=float)
    return np.clip(score / max(len(terms), 1), 0.0, 1.0)


def _dietary_goal_score(df: pd.DataFrame, goals: list[str]) -> np.ndarray:
    if not goals:
        return np.zeros(len(df), dtype=float)
    scores = []
    calories = pd.to_numeric(df.get("calories", np.nan), errors="coerce")
    fat = pd.to_numeric(df.get("total_fat_pct", np.nan), errors="coerce")
    sugar = pd.to_numeric(df.get("sugar_pct", np.nan), errors="coerce")
    sodium = pd.to_numeric(df.get("sodium_pct", np.nan), errors="coerce")
    protein = pd.to_numeric(df.get("protein_pct", np.nan), errors="coerce")
    carbs = pd.to_numeric(df.get("carbohydrates_pct", np.nan), errors="coerce")
    for goal in goals:
        if "low calorie" in goal or "low-calorie" in goal or "低热量" in goal or "低卡" in goal:
            scores.append((calories <= 500).fillna(False).to_numpy(dtype=float))
        elif "high protein" in goal or "high-protein" in goal or "高蛋白" in goal:
            scores.append((protein >= protein.quantile(0.65)).fillna(False).to_numpy(dtype=float))
        elif "low fat" in goal or "low-fat" in goal or "低脂" in goal:
            scores.append((fat <= fat.quantile(0.35)).fillna(False).to_numpy(dtype=float))
        elif "low sugar" in goal or "low-sugar" in goal or "低糖" in goal:
            scores.append((sugar <= sugar.quantile(0.35)).fillna(False).to_numpy(dtype=float))
        elif "low sodium" in goal or "low-sodium" in goal or "低钠" in goal:
            scores.append((sodium <= sodium.quantile(0.35)).fillna(False).to_numpy(dtype=float))
        elif "low carb" in goal or "low-carb" in goal or "低碳" in goal:
            scores.append((carbs <= carbs.quantile(0.35)).fillna(False).to_numpy(dtype=float))
    if not scores:
        return np.zeros(len(df), dtype=float)
    return np.clip(np.mean(scores, axis=0), 0.0, 1.0)


def _time_score(df: pd.DataFrame, max_minutes: int | None) -> np.ndarray:
    minutes = pd.to_numeric(df.get("minutes", np.nan), errors="coerce")
    if max_minutes is None or max_minutes <= 0:
        known = minutes.notna().to_numpy(dtype=float)
        return known * 0.5
    score = np.where(minutes.notna(), np.clip(float(max_minutes) / np.maximum(minutes, 1.0), 0.0, 1.0), 0.0)
    return score.astype(float)


def _genre_set(value: Any) -> set[str]:
    return {part.strip().lower() for part in str(value or "").split("|") if part.strip()}


def _diverse_select(candidates: pd.DataFrame, limit: int) -> pd.DataFrame:
    selected = []
    selected_genres: list[set[str]] = []
    for _, row in candidates.iterrows():
        genres = _genre_set(row.get("genres"))
        if selected_genres:
            max_overlap = max(
                len(genres & existing) / max(len(genres | existing), 1)
                for existing in selected_genres
            )
        else:
            max_overlap = 0.0
        adjusted = float(row["_cold_start_score"]) - 0.12 * max_overlap
        selected.append((adjusted, row))
    ordered = sorted(selected, key=lambda item: (-item[0], int(item[1]["movieId"])))
    rows = []
    for _, row in ordered:
        rows.append(row)
        selected_genres.append(_genre_set(row.get("genres")))
        if len(rows) >= limit:
            break
    return pd.DataFrame(rows)


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None or pd.isna(value):
            return default
        if not math.isfinite(float(value)):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int | None = None) -> int | None:
    val = _safe_float(value, None)
    return int(val) if val is not None else default


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value)


def _item_from_row(row: dict[str, Any]) -> dict[str, Any]:
    recipe_id = int(row["movieId"])
    score = _safe_float(row.get("_cold_start_score"), 0.0) or 0.0
    rating = _safe_float(row.get("rating_value"), _safe_float(row.get("movie_avg_rating"), 0.0))
    reviews = _safe_int(row.get("review_count"), _safe_int(row.get("movie_rating_count"), 0))
    return {
        "movie_id": recipe_id,
        "title": _safe_text(row.get("title") or row.get("clean_title") or f"菜谱 {recipe_id}"),
        "score": round(float(score), 8),
        "genres": _safe_text(row.get("genres")),
        "avg_rating": rating,
        "rating_count": reviews,
        "review_count": reviews,
        "image_url": _safe_text(row.get("image_url")),
        "ready_in_display": _safe_text(row.get("ready_in_display")),
        "recipe_yield_raw": _safe_text(row.get("recipe_yield_raw")),
        "author_name": _safe_text(row.get("author_name")),
        "poster_url": "",
        "backdrop_url": "",
        "overview": "",
        "release_date": "",
        "runtime": _safe_int(row.get("minutes"), None),
        "vote_average": rating,
        "popularity": _safe_float(row.get("movie_popularity"), 0.0),
        "tmdb_id": None,
        "imdb_id": "",
    }
