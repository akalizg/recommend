"""
FastAPI route definitions for the recommendation system.
"""
import json
import logging
import re
import time
from pathlib import Path
from typing import Optional

import faiss
import numpy as np
import pandas as pd
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Depends, Response
from starlette.concurrency import run_in_threadpool

from api.schemas import (
    RecommendationResponse,
    MovieItem,
    MovieDetail,
    PopularResponse,
    UserProfileResponse,
    SearchResponse,
    RebuildResponse,
    HealthResponse,
    ErrorResponse,
    OfflineRecommendationItem,
    OfflineRecommendationsResponse,
    OfflineMetricsResponse,
    OfflineAblationResponse,
    OfflineUserProfileResponse,
    OfflineMovieProfileResponse,
    OfflinePopularRecipesResponse,
    SimilarRecipesResponse,
    ColdStartRequest,
    ColdStartResponse,
    ScenarioRecommendRequest,
    ScenarioRecommendResponse,
    IngredientSearchResponse,
    AuthRegisterRequest,
    AuthLoginRequest,
    AuthUserResponse,
    FeedbackRequest,
    FeedbackResponse,
    ExposureRequest,
    RealtimeProfileResponse,
    ABGroupResponse,
    ABMetricsResponse,
)
from app.config import PROJECT_ROOT

logger = logging.getLogger(__name__)

router = APIRouter()

OFFLINE_RECOMMENDATIONS_PATH = PROJECT_ROOT / "data" / "final" / "recommendations_with_reasons.csv"
OFFLINE_METRICS_PATH = PROJECT_ROOT / "data" / "eval" / "optimized_offline_metrics.csv"
OFFLINE_METRICS_FALLBACK_PATH = PROJECT_ROOT / "data" / "eval" / "offline_metrics.csv"
OFFLINE_METRICS_SUMMARY_PATH = PROJECT_ROOT / "data" / "eval" / "optimized_eval_summary.json"
OFFLINE_METRICS_SUMMARY_FALLBACK_PATH = PROJECT_ROOT / "data" / "eval" / "eval_summary.json"
OFFLINE_ABLATION_PATH = PROJECT_ROOT / "data" / "eval" / "optimized_ablation_metrics.csv"
OFFLINE_ABLATION_FALLBACK_PATH = PROJECT_ROOT / "data" / "eval" / "ablation_metrics.csv"
OFFLINE_USER_PROFILE_PATH = PROJECT_ROOT / "data" / "features" / "user_profile.csv"
OFFLINE_MOVIE_PROFILE_PATH = PROJECT_ROOT / "data" / "features" / "movie_profile.csv"
OFFLINE_RECIPE_DETAIL_PATH = PROJECT_ROOT / "data" / "recipe-canonical" / "recipe_detail_metadata.csv"
OFFLINE_RECIPE_METADATA_PATH = PROJECT_ROOT / "data" / "recipe-canonical" / "recipe_metadata.csv"
OFFLINE_INGREDIENT_TRANSLATION_PATH = PROJECT_ROOT / "data" / "recipe-canonical" / "ingredient_frequency_translated.tsv"
ENHANCED_RANKED_TOP50_PATH = PROJECT_ROOT / "data" / "rank" / "enhanced" / "ranked_top50_enhanced.csv"
FAISS_HNSW_SPARK_INDEX_PATH = PROJECT_ROOT / "models" / "faiss_hnsw_spark.index"
FAISS_HNSW_SPARK_IDS_PATH = PROJECT_ROOT / "models" / "faiss_hnsw_spark_ids.npy"
FAISS_SPARK_VECTORS_PATH = PROJECT_ROOT / "data" / "faiss" / "movie_vectors.npy"
FAISS_SPARK_VECTOR_IDS_PATH = PROJECT_ROOT / "data" / "faiss" / "movie_ids.npy"

_faiss_similarity_cache: dict[str, object] = {}
_offline_table_cache: dict[str, object] = {}
_recipe_detail_row_cache: dict[int, dict] = {}
_ingredient_map_cache: dict[str, object] = {}

_INGREDIENT_WORD_LABELS = {
    "all-purpose": "通用",
    "almonds": "杏仁",
    "apple": "苹果",
    "apples": "苹果",
    "bacon": "培根",
    "baking": "烘焙",
    "banana": "香蕉",
    "bananas": "香蕉",
    "basil": "罗勒",
    "bay": "月桂",
    "beans": "豆",
    "beef": "牛肉",
    "bell": "甜椒",
    "berries": "浆果",
    "black": "黑",
    "boneless": "无骨",
    "breast": "胸肉",
    "breasts": "胸肉",
    "broth": "汤",
    "brown": "红",
    "butter": "黄油",
    "buttermilk": "酪乳",
    "canned": "罐装",
    "carrot": "胡萝卜",
    "carrots": "胡萝卜",
    "cheddar": "切达",
    "cheese": "奶酪",
    "chicken": "鸡肉",
    "chilies": "辣椒",
    "chili": "辣椒",
    "chips": "碎片",
    "chocolate": "巧克力",
    "cilantro": "香菜",
    "cinnamon": "肉桂",
    "clove": "瓣",
    "cloves": "瓣",
    "condensed": "浓缩",
    "cooked": "熟",
    "cooking": "烹饪",
    "corn": "玉米",
    "cream": "奶油",
    "dry": "干",
    "egg": "鸡蛋",
    "eggs": "鸡蛋",
    "fat-free": "无脂",
    "feta": "菲达",
    "fillets": "鱼片",
    "flour": "面粉",
    "fresh": "新鲜",
    "freshly": "新鲜",
    "garlic": "大蒜",
    "ginger": "姜",
    "granules": "颗粒",
    "green": "青",
    "ground": "碎",
    "half": "半块",
    "halves": "半块",
    "hot": "辣",
    "italian": "意式",
    "jack": "杰克",
    "leaf": "叶",
    "leaves": "叶",
    "lean": "瘦",
    "lemon": "柠檬",
    "light": "淡",
    "low-fat": "低脂",
    "low-sodium": "低钠",
    "mayonnaise": "蛋黄酱",
    "milk": "牛奶",
    "monterey": "蒙特利",
    "mushroom": "蘑菇",
    "mushrooms": "蘑菇",
    "mustard": "芥末",
    "noodles": "面条",
    "nutmeg": "肉豆蔻",
    "oil": "油",
    "olive": "橄榄",
    "olives": "橄榄",
    "onion": "洋葱",
    "onions": "洋葱",
    "paprika": "红椒粉",
    "parmesan": "帕玛森",
    "parsley": "欧芹",
    "pepper": "胡椒",
    "peppers": "椒",
    "pieces": "块",
    "pork": "猪肉",
    "potato": "土豆",
    "potatoes": "土豆",
    "powder": "粉",
    "red": "红",
    "reduced-sodium": "低钠",
    "rice": "米饭",
    "salsa": "莎莎酱",
    "sauce": "酱",
    "scallions": "小葱",
    "sea": "海",
    "seeds": "籽",
    "sesame": "芝麻",
    "sharp": "浓味",
    "shrimp": "虾",
    "skim": "脱脂",
    "skinless": "去皮",
    "sodium": "钠",
    "soup": "汤",
    "sour": "酸",
    "soy": "酱油",
    "spray": "喷雾",
    "stock": "高汤",
    "sugar": "糖",
    "swiss": "瑞士",
    "thighs": "腿肉",
    "tomato": "番茄",
    "tomatoes": "番茄",
    "turkey": "火鸡",
    "vanilla": "香草",
    "vegetable": "植物",
    "water": "水",
    "wheat": "小麦",
    "white": "白",
    "whole": "整",
    "wine": "葡萄酒",
    "wings": "翅",
    "yolks": "蛋黄",
}

_INGREDIENT_PHRASE_LABELS = {
    "boneless skinless chicken breasts": "无骨去皮鸡胸肉",
    "boneless skinless chicken breast": "无骨去皮鸡胸肉",
    "boneless skinless chicken breast halves": "无骨去皮鸡胸肉",
    "boneless skinless chicken thighs": "无骨去皮鸡腿肉",
    "boneless chicken breasts": "无骨鸡胸肉",
    "boneless chicken breast": "无骨鸡胸肉",
    "chicken breasts": "鸡胸肉",
    "chicken breast": "鸡胸肉",
    "chicken thighs": "鸡腿肉",
    "chicken wings": "鸡翅",
    "chicken broth": "鸡汤",
    "chicken stock": "鸡高汤",
    "low sodium chicken broth": "低钠鸡汤",
    "reduced-sodium chicken broth": "低钠鸡汤",
    "cream of chicken soup": "奶油鸡汤",
    "condensed cream of chicken soup": "浓缩奶油鸡汤",
    "cooked chicken": "熟鸡肉",
    "cooked chicken breasts": "熟鸡胸肉",
    "ground chicken": "鸡肉末",
    "whole chicken": "整鸡",
    "whole chickens": "整鸡",
}


def _existing_offline_file(primary: Path, fallback: Optional[Path] = None) -> Path:
    """Resolve the preferred offline artifact without generating or mutating it."""
    if primary.exists():
        return primary
    if fallback and fallback.exists():
        return fallback
    raise HTTPException(status_code=404, detail=f"离线产物不存在：{primary}")


def _read_offline_csv(primary: Path, fallback: Optional[Path] = None) -> tuple[pd.DataFrame, Path]:
    path = _existing_offline_file(primary, fallback)
    try:
        return pd.read_csv(path), path
    except Exception as exc:
        logger.error("Failed to read offline CSV %s: %s", path, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"离线产物读取失败：{path.name}")


def _read_cached_csv(primary: Path, fallback: Optional[Path] = None) -> tuple[pd.DataFrame, Path]:
    path = _existing_offline_file(primary, fallback)
    token = f"{path}:{path.stat().st_mtime_ns}:{path.stat().st_size}"
    cached = _offline_table_cache.get(str(path))
    if isinstance(cached, dict) and cached.get("token") == token:
        return cached["df"], path
    df, _ = _read_offline_csv(path)
    _offline_table_cache[str(path)] = {"token": token, "df": df}
    return df, path


def _read_offline_json(primary: Path, fallback: Optional[Path] = None) -> tuple[Optional[dict], Optional[Path]]:
    try:
        path = _existing_offline_file(primary, fallback)
    except HTTPException:
        return None, None
    try:
        return json.loads(path.read_text(encoding="utf-8")), path
    except Exception as exc:
        logger.error("Failed to read offline JSON %s: %s", path, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"离线摘要读取失败：{path.name}")


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def _json_safe_value(value):
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("{") or text.startswith("["):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return value
    return value


def _json_safe_records(df: pd.DataFrame) -> list[dict]:
    return [{key: _json_safe_value(value) for key, value in row.items()} for row in df.to_dict(orient="records")]


def _ingredient_catalog(path: Path) -> tuple[list[dict], dict[str, str], Path]:
    path = _existing_offline_file(path)
    token = f"{path}:{path.stat().st_mtime_ns}:{path.stat().st_size}"
    cached = _ingredient_map_cache.get(str(path))
    if isinstance(cached, dict) and cached.get("token") == token:
        return cached["items"], cached["zh_to_en"], path

    try:
        df = pd.read_csv(path, sep="\t", encoding="utf-8-sig")
        _require_columns(df, {"ingredient", "count", "translated_ingredient"}, path.name)
    except ValueError as exc:
        logger.error("Ingredient translation file has invalid format %s: %s", path, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"{path.name} 格式无效") from exc
    except Exception as exc:
        logger.error("Failed to read ingredient translations %s: %s", path, exc, exc_info=True)
        raise HTTPException(status_code=500, detail="食材映射读取失败") from exc

    df = df.fillna("")
    records: list[dict] = []
    zh_to_en: dict[str, str] = {}
    for row in df.to_dict(orient="records"):
        name = str(row.get("ingredient") or "").strip().lower()
        raw_label = str(row.get("translated_ingredient") or "").strip()
        label = _clean_ingredient_label(name, raw_label)
        if not name or not label:
            continue
        count_value = pd.to_numeric(row.get("count"), errors="coerce")
        count = 0 if pd.isna(count_value) else int(count_value)
        records.append({"name": name, "label": label, "count": count})
        zh_to_en.setdefault(label.lower(), name)
        zh_to_en.setdefault(name.lower(), name)

    items = sorted(records, key=lambda item: (-item["count"], item["label"], item["name"]))
    _ingredient_map_cache[str(path)] = {"token": token, "items": items, "zh_to_en": zh_to_en}
    return items, zh_to_en, path


def _clean_ingredient_label(name: str, label: str) -> str:
    normalized = str(name or "").strip().lower()
    if normalized in _INGREDIENT_PHRASE_LABELS:
        return _INGREDIENT_PHRASE_LABELS[normalized]

    label = str(label or "").strip()
    if label and not re.search(r"[A-Za-z/]", label):
        return label

    generated = _label_from_english_ingredient(normalized)
    if generated:
        return generated
    return ""


def _label_from_english_ingredient(name: str) -> str:
    parts = [part for part in re.split(r"[\s_/&(),'-]+", name.lower()) if part and part not in {"and", "of", "the"}]
    labels: list[str] = []
    for part in parts:
        translated = _INGREDIENT_WORD_LABELS.get(part)
        if not translated:
            return ""
        if not labels or labels[-1] != translated:
            labels.append(translated)
    text = "".join(labels)
    return text if text else ""


def _map_ingredient_terms(values: list[str]) -> list[str]:
    if not values:
        return []
    _, zh_to_en, _ = _ingredient_catalog(OFFLINE_INGREDIENT_TRANSLATION_PATH)
    mapped: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        mapped.append(zh_to_en.get(text.lower(), text.lower()))
    return sorted(set(mapped))


def _rank_ingredient_matches(items: list[dict], query: str) -> list[dict]:
    if not query:
        return _dedupe_ingredient_labels(items)

    def sort_key(item: dict) -> tuple[int, int, int, int, str]:
        label = str(item.get("label") or "").lower()
        name = str(item.get("name") or "").lower()
        if label == query:
            match_rank = 0
        elif label.startswith(query):
            match_rank = 1
        elif query in label:
            match_rank = 2
        elif name == query:
            match_rank = 3
        elif name.startswith(query):
            match_rank = 4
        else:
            match_rank = 5
        return (match_rank, len(label), -int(item.get("count") or 0), len(name), label)

    return _dedupe_ingredient_labels(sorted(items, key=sort_key))


def _dedupe_ingredient_labels(items: list[dict]) -> list[dict]:
    deduped: list[dict] = []
    seen: set[str] = set()
    for item in items:
        label = str(item.get("label") or "").strip().lower()
        if not label or label in seen:
            continue
        seen.add(label)
        deduped.append(item)
    return deduped


def _require_columns(df: pd.DataFrame, required: set[str], artifact_name: str) -> None:
    missing = sorted(required - set(df.columns))
    if missing:
        raise HTTPException(status_code=500, detail=f"{artifact_name} 缺少必要字段：{missing}")


def _first_profile_row(df: pd.DataFrame, id_column: str, id_value: int, artifact_name: str) -> dict:
    _require_columns(df, {id_column}, artifact_name)
    ids = pd.to_numeric(df[id_column], errors="coerce")
    matched = df[ids == id_value]
    if matched.empty:
        raise HTTPException(status_code=404, detail=f"{artifact_name} 中没有找到 {id_column}={id_value} 的记录")
    return _json_safe_records(matched.head(1))[0]


def _optional_recipe_detail(movie_id: int) -> dict:
    if not OFFLINE_RECIPE_DETAIL_PATH.exists():
        return {}
    if movie_id in _recipe_detail_row_cache:
        return _recipe_detail_row_cache[movie_id]
    try:
        usecols = pd.read_csv(OFFLINE_RECIPE_DETAIL_PATH, nrows=0).columns.tolist()
        for chunk in pd.read_csv(OFFLINE_RECIPE_DETAIL_PATH, chunksize=50_000, usecols=usecols):
            if "recipe_id" not in chunk.columns:
                raise HTTPException(status_code=500, detail=f"{OFFLINE_RECIPE_DETAIL_PATH.name} 缺少 recipe_id 字段")
            ids = pd.to_numeric(chunk["recipe_id"], errors="coerce")
            matched = chunk[ids == movie_id]
            if not matched.empty:
                detail = _json_safe_records(matched.head(1))[0]
                _recipe_detail_row_cache[movie_id] = detail
                return detail
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to read recipe detail row %s: %s", movie_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail="菜谱详情元数据读取失败") from exc
    _recipe_detail_row_cache[movie_id] = {}
    return {}


def get_metadata_cache_token(state: "AppState") -> str:
    if state.pipeline and hasattr(state.pipeline, "metadata_cache_token"):
        return state.pipeline.metadata_cache_token()
    return "metadata_unknown"


def build_movie_item(movie_id: int, title: str, score: float, info: Optional[dict] = None) -> MovieItem:
    """Build a recommendation item while preserving optional display metadata."""
    info = info or {}
    return MovieItem(
        movie_id=int(movie_id),
        title=info.get("title") or info.get("movie_title") or info.get("name") or title,
        score=float(score),
        genres=info.get("genres") or info.get("movie_genres") or "",
        avg_rating=_row_float(info, "rating_value", "avg_rating", "movie_avg_rating", default=0.0),
        rating_count=_row_int(info, "review_count", "rating_count", "movie_rating_count", default=0),
        review_count=_row_int(info, "review_count", "rating_count", "movie_rating_count", default=0),
        final_reason=info.get("final_reason") or "",
        reason_source=info.get("reason_source") or "",
        image_url=info.get("image_url") or "",
        ready_in_display=info.get("ready_in_display") or "",
        recipe_yield_raw=info.get("recipe_yield_raw") or "",
        author_name=info.get("author_name") or "",
        poster_url=info.get("poster_url", ""),
        backdrop_url=info.get("backdrop_url", ""),
        overview=info.get("overview") or info.get("description") or "",
        release_date=info.get("release_date", ""),
        runtime=info.get("runtime"),
        vote_average=info.get("vote_average"),
        popularity=info.get("popularity"),
        tmdb_id=info.get("tmdb_id"),
        imdb_id=info.get("imdb_id", ""),
    )


def movie_detail_from_search_row(row, info: Optional[dict] = None) -> MovieDetail:
    """Build search result details from the matched row plus optional metadata."""
    info = info or {}
    detail = {
        "movie_id": int(row["movieId"]),
        "title": str(row["title"]),
        "genres": str(row.get("genres", "")),
        "avg_rating": float(row.get("avg_rating", 0)) if pd.notna(row.get("avg_rating")) else 0.0,
        "rating_count": int(row.get("rating_count", 0)) if pd.notna(row.get("rating_count")) else 0,
        "popularity_score": float(row.get("popularity_score", 0)) if pd.notna(row.get("popularity_score")) else 0.0,
        "year": int(row.get("year")) if pd.notna(row.get("year")) else None,
    }

    for field in [
        "poster_url",
        "backdrop_url",
        "overview",
        "release_date",
        "runtime",
        "vote_average",
        "popularity",
        "tmdb_id",
        "imdb_id",
    ]:
        if field in info:
            detail[field] = info[field]

    return MovieDetail(**detail)


def _row_id(row: dict, *keys: str) -> int:
    for key in keys:
        value = row.get(key)
        if value is not None and not pd.isna(value):
            return int(float(value))
    raise KeyError(f"Missing id from {keys}")


def _row_float(row: dict, *keys: str, default: float = 0.0) -> float:
    for key in keys:
        value = row.get(key)
        if value is not None and not pd.isna(value):
            return float(value)
    return default


def _row_int(row: dict, *keys: str, default: int = 0) -> int:
    return int(_row_float(row, *keys, default=float(default)))


def _row_text(row: dict, *keys: str, default: str = "") -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and not pd.isna(value):
            return str(value)
    return default


def _movie_detail_from_profile(profile: dict) -> MovieDetail:
    """Map legacy internal movieId fields to a recipe detail response."""
    movie_id = _row_id(profile, "movie_id", "movieId", "recipe_id", "id")
    title = _row_text(profile, "title", "name", "clean_title", default=f"菜谱 {movie_id}")
    genres = _row_text(profile, "genres", "movie_genres")
    avg_rating = _row_float(profile, "rating_value", "avg_rating", "movie_avg_rating")
    rating_count = _row_int(profile, "review_count", "rating_count", "movie_rating_count")
    popularity = _row_float(profile, "popularity_score", "movie_popularity", "popularity")
    detail = {
        "movie_id": movie_id,
        "title": title,
        "genres": genres,
        "avg_rating": avg_rating,
        "rating_count": rating_count,
        "popularity_score": popularity,
        "year": profile.get("year"),
        "image_url": profile.get("image_url") or "",
        "description": profile.get("description") or profile.get("overview") or "",
        "minutes": profile.get("minutes"),
        "ready_in_display": profile.get("ready_in_display") or "",
        "recipe_yield_raw": profile.get("recipe_yield_raw") or "",
        "serves_best_guess": profile.get("serves_best_guess"),
        "author_name": profile.get("author_name") or "",
        "source_url": profile.get("source_url") or profile.get("foodcom_url") or "",
        "ingredients_json": profile.get("ingredients_json"),
        "quantities_json": profile.get("quantities_json"),
        "steps_json": profile.get("steps_json"),
        "nutrition_json": profile.get("nutrition_json"),
        "n_ingredients": profile.get("n_ingredients"),
        "n_steps": profile.get("n_steps"),
        "submitted": profile.get("submitted") or "",
        "photo_count": profile.get("photo_count"),
        "review_count": profile.get("review_count"),
        "poster_url": profile.get("poster_url") or "",
        "backdrop_url": profile.get("backdrop_url") or "",
        "overview": profile.get("overview") or profile.get("description") or "",
        "release_date": profile.get("release_date") or "",
        "runtime": profile.get("runtime"),
        "vote_average": profile.get("vote_average"),
        "popularity": profile.get("popularity"),
        "tmdb_id": profile.get("tmdb_id"),
        "imdb_id": profile.get("imdb_id") or "",
    }
    return MovieDetail(**detail)


def _es_repository():
    from search.es_recipe_repository import ESRecipeRepository

    return ESRecipeRepository()


def _recipe_from_es(movie_id: int) -> dict:
    record = _es_repository().get_recipe(movie_id)
    return record or {}


def _search_recipes_from_es(query: str, limit: int) -> list[dict]:
    return _es_repository().search_recipes(query, limit)


def _recipes_from_es(movie_ids: list[int]) -> dict[int, dict]:
    return _es_repository().get_recipes(movie_ids)


def _offline_profile(movie_id: int) -> dict:
    profiles, path = _read_cached_csv(OFFLINE_MOVIE_PROFILE_PATH)
    profile = _first_profile_row(profiles, "movieId", movie_id, path.name)
    detail = _optional_recipe_detail(movie_id)
    if detail:
        profile.update({key: value for key, value in detail.items() if value is not None})
    return profile


def _offline_profile_without_detail(movie_id: int) -> dict:
    profiles, path = _read_cached_csv(OFFLINE_MOVIE_PROFILE_PATH)
    return _first_profile_row(profiles, "movieId", movie_id, path.name)


def _load_faiss_similarity_assets() -> tuple[faiss.Index, np.ndarray, np.ndarray]:
    """Load FAISS HNSW recipe vector assets with a lightweight process cache."""
    required = [
        FAISS_HNSW_SPARK_INDEX_PATH,
        FAISS_HNSW_SPARK_IDS_PATH,
        FAISS_SPARK_VECTORS_PATH,
        FAISS_SPARK_VECTOR_IDS_PATH,
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise HTTPException(status_code=404, detail=f"FAISS 相似菜谱资产不存在：{missing}")

    token = "|".join(f"{path}:{path.stat().st_mtime_ns}:{path.stat().st_size}" for path in required)
    if _faiss_similarity_cache.get("token") == token:
        return (
            _faiss_similarity_cache["index"],
            _faiss_similarity_cache["index_ids"],
            _faiss_similarity_cache["vectors"],
        )

    try:
        index = faiss.read_index(str(FAISS_HNSW_SPARK_INDEX_PATH))
        index_ids = np.load(FAISS_HNSW_SPARK_IDS_PATH).astype(np.int64)
        vector_ids = np.load(FAISS_SPARK_VECTOR_IDS_PATH).astype(np.int64)
        vectors = np.load(FAISS_SPARK_VECTORS_PATH).astype(np.float32)
    except Exception as exc:
        logger.error("Failed to load FAISS recipe similarity assets: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="FAISS 相似菜谱资产加载失败") from exc

    if vectors.ndim != 2 or index_ids.ndim != 1 or vector_ids.ndim != 1:
        raise HTTPException(status_code=500, detail="FAISS 相似菜谱资产维度不正确")
    if len(index_ids) != index.ntotal or len(vector_ids) != len(vectors):
        raise HTTPException(status_code=500, detail="FAISS 相似菜谱资产不一致")

    order = np.argsort(vector_ids)
    vector_ids_sorted = vector_ids[order]
    vectors_sorted = np.ascontiguousarray(vectors[order], dtype=np.float32)
    _faiss_similarity_cache.clear()
    _faiss_similarity_cache.update(
        {
            "token": token,
            "index": index,
            "index_ids": index_ids,
            "vectors": vectors_sorted,
            "vector_ids": vector_ids_sorted,
        }
    )
    return index, index_ids, vectors_sorted


def _recipe_query_vector(movie_id: int) -> np.ndarray:
    if "vector_ids" not in _faiss_similarity_cache:
        _load_faiss_similarity_assets()
    vector_ids = _faiss_similarity_cache["vector_ids"]
    vectors = _faiss_similarity_cache["vectors"]
    pos = np.searchsorted(vector_ids, movie_id)
    if pos >= len(vector_ids) or int(vector_ids[pos]) != movie_id:
        raise HTTPException(status_code=404, detail=f"菜谱 {movie_id} 没有 FAISS 向量")
    return np.ascontiguousarray(vectors[pos : pos + 1], dtype=np.float32)


def _similar_recipe_items(movie_id: int, limit: int) -> tuple[list[MovieItem], str]:
    index, index_ids, _ = _load_faiss_similarity_assets()
    query = _recipe_query_vector(movie_id)
    search_k = min(max(limit + 8, limit * 3), max(int(index.ntotal), limit + 1))
    try:
        scores, positions = index.search(query, search_k)
    except Exception as exc:
        logger.error("FAISS recipe similarity search failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="FAISS 相似菜谱检索失败") from exc

    candidate_scores: list[tuple[int, float]] = []
    for score, pos in zip(scores[0], positions[0]):
        if int(pos) < 0 or int(pos) >= len(index_ids):
            continue
        candidate_id = int(index_ids[int(pos)])
        if candidate_id == movie_id:
            continue
        candidate_scores.append((candidate_id, float(score)))
        if len(candidate_scores) >= limit:
            break

    es_records = _recipes_from_es([candidate_id for candidate_id, _ in candidate_scores])
    items: list[MovieItem] = []
    for candidate_id, score in candidate_scores:
        try:
            profile = es_records.get(candidate_id) or _offline_profile_without_detail(candidate_id)
        except HTTPException as exc:
            if exc.status_code == 404:
                continue
            raise
        items.append(build_movie_item(candidate_id, f"菜谱 {candidate_id}", score, profile))
        if len(items) >= limit:
            break
    return items, _display_path(FAISS_HNSW_SPARK_INDEX_PATH)


def _popular_recipe_records(limit: int, with_images_first: bool = True) -> tuple[list[dict], Path]:
    profiles, path = _read_offline_csv(OFFLINE_MOVIE_PROFILE_PATH)
    _require_columns(profiles, {"movieId", "title", "genres", "movie_avg_rating", "movie_rating_count"}, path.name)

    df = profiles.copy()
    df["movieId"] = pd.to_numeric(df["movieId"], errors="coerce")
    df["movie_avg_rating"] = pd.to_numeric(df["movie_avg_rating"], errors="coerce").fillna(0.0)
    df["movie_rating_count"] = pd.to_numeric(df["movie_rating_count"], errors="coerce").fillna(0.0)
    if "movie_popularity" in df.columns:
        df["movie_popularity"] = pd.to_numeric(df["movie_popularity"], errors="coerce").fillna(0.0)
    else:
        df["movie_popularity"] = df["movie_avg_rating"] * (df["movie_rating_count"] + 1).pow(0.5)
    if "image_url" not in df.columns:
        df["image_url"] = ""
    df["has_display_image"] = df["image_url"].fillna("").astype(str).str.len() > 0
    sort_columns = ["movie_popularity", "movie_avg_rating", "movie_rating_count", "movieId"]
    ascending = [False, False, False, True]
    if with_images_first:
        sort_columns = ["has_display_image", *sort_columns]
        ascending = [False, *ascending]
    df = df.dropna(subset=["movieId"]).sort_values(sort_columns, ascending=ascending).head(limit)

    records = []
    for record in _json_safe_records(df):
        records.append(
            {
                "movie_id": int(record.get("movieId")),
                "title": record.get("title") or record.get("clean_title") or "",
                "genres": record.get("genres") or "",
                "score": record.get("movie_popularity") or 0.0,
                "avg_rating": record.get("rating_value") or record.get("movie_avg_rating") or 0.0,
                "rating_count": record.get("movie_rating_count") or 0,
                "year": record.get("year"),
                "image_url": record.get("image_url") or "",
                "ready_in_display": record.get("ready_in_display") or "",
                "recipe_yield_raw": record.get("recipe_yield_raw") or "",
                "author_name": record.get("author_name") or "",
                "review_count": record.get("review_count"),
            }
        )
    return records, path


def _token_set(value) -> set[str]:
    if value is None or pd.isna(value):
        return set()
    return {
        part.strip().lower()
        for part in str(value).replace(",", "|").replace("/", "|").split("|")
        if part.strip()
    }


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / max(len(left | right), 1)


def _normalize_values(values: list[float]) -> list[float]:
    if not values:
        return []
    arr = np.asarray(values, dtype=float)
    arr = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)
    low = float(arr.min())
    high = float(arr.max())
    if high <= low:
        return [1.0 for _ in values]
    return ((arr - low) / (high - low)).tolist()


def _profile_records_by_id(recipe_ids: list[int]) -> tuple[dict[int, dict], Path]:
    ids = {int(recipe_id) for recipe_id in recipe_ids}
    if not ids:
        return {}, OFFLINE_MOVIE_PROFILE_PATH
    profiles, path = _read_cached_csv(OFFLINE_MOVIE_PROFILE_PATH)
    _require_columns(profiles, {"movieId"}, path.name)
    subset = profiles[pd.to_numeric(profiles["movieId"], errors="coerce").isin(ids)]
    records = {}
    for record in _json_safe_records(subset):
        records[int(record["movieId"])] = record
    return records, path


def _personalized_recipe_items(user_id: int, limit: int) -> tuple[list[MovieItem], str, dict]:
    try:
        df, path = _read_cached_csv(OFFLINE_RECOMMENDATIONS_PATH)
        _require_columns(df, {"userId", "movieId"}, path.name)
        working = df.copy()
        working["userId"] = pd.to_numeric(working["userId"], errors="coerce")
        user_recs = working[working["userId"] == user_id].copy()
    except HTTPException as exc:
        if exc.status_code != 404:
            raise
        user_recs = pd.DataFrame()
        path = OFFLINE_RECOMMENDATIONS_PATH

    if user_recs.empty:
        popular_records, popular_path = _popular_recipe_records(limit)
        items = [
            build_movie_item(record["movie_id"], record["title"], float(record.get("score") or 0.0), record)
            for record in popular_records
        ]
        return items, _display_path(popular_path), {"fallback": "popular", "user_id": user_id}

    if "rank_position" in user_recs.columns:
        user_recs["_rank_position"] = pd.to_numeric(user_recs["rank_position"], errors="coerce").fillna(10**9)
        user_recs = user_recs.sort_values(["_rank_position", "movieId"], ascending=[True, True])
    else:
        score_col = "rank_score" if "rank_score" in user_recs.columns else "mmr_score"
        if score_col in user_recs.columns:
            user_recs[score_col] = pd.to_numeric(user_recs[score_col], errors="coerce").fillna(0.0)
            user_recs = user_recs.sort_values([score_col, "movieId"], ascending=[False, True])

    items: list[MovieItem] = []
    for record in _json_safe_records(user_recs.head(limit)):
        recipe_id = int(record["movieId"])
        score = _row_float(record, "rank_score", "mmr_score", "recall_score", default=0.0)
        items.append(build_movie_item(recipe_id, f"菜谱 {recipe_id}", score, record))

    supplemented = False
    if len(items) < limit and ENHANCED_RANKED_TOP50_PATH.exists():
        ranked, ranked_path = _read_cached_csv(ENHANCED_RANKED_TOP50_PATH)
        if {"userId", "movieId"}.issubset(set(ranked.columns)):
            existing_ids = {item.movie_id for item in items}
            ranked_working = ranked.copy()
            ranked_working["userId"] = pd.to_numeric(ranked_working["userId"], errors="coerce")
            ranked_working["movieId"] = pd.to_numeric(ranked_working["movieId"], errors="coerce")
            ranked_user = ranked_working[
                (ranked_working["userId"] == user_id) & (~ranked_working["movieId"].isin(existing_ids))
            ].dropna(subset=["movieId"]).copy()
            if not ranked_user.empty:
                if "rank_position" in ranked_user.columns:
                    ranked_user["_rank_position"] = pd.to_numeric(
                        ranked_user["rank_position"], errors="coerce"
                    ).fillna(10**9)
                    ranked_user = ranked_user.sort_values(
                        ["_rank_position", "rank_score", "movieId"], ascending=[True, False, True]
                    )
                elif "rank_score" in ranked_user.columns:
                    ranked_user["rank_score"] = pd.to_numeric(ranked_user["rank_score"], errors="coerce").fillna(0.0)
                    ranked_user = ranked_user.sort_values(["rank_score", "movieId"], ascending=[False, True])
                needed = limit - len(items)
                supplement_records = _json_safe_records(ranked_user.head(needed))
                profile_map, _ = _profile_records_by_id([int(record["movieId"]) for record in supplement_records])
                for record in supplement_records:
                    recipe_id = int(record["movieId"])
                    info = {**profile_map.get(recipe_id, {}), **record}
                    score = _row_float(info, "rank_score", "mmr_score", "recall_score", default=0.0)
                    items.append(build_movie_item(recipe_id, f"菜谱 {recipe_id}", score, info))
                supplemented = True
                path = ranked_path

    return items, _display_path(path), {"fallback": None, "user_id": user_id, "supplemented_from_top50": supplemented}


def _user_preference_terms(user_id: int) -> tuple[set[str], dict]:
    try:
        profiles, path = _read_cached_csv(OFFLINE_USER_PROFILE_PATH)
        profile = _first_profile_row(profiles, "userId", user_id, path.name)
    except HTTPException:
        return set(), {}
    return _token_set(profile.get("favorite_genres")), profile


def _explore_recipe_items(user_id: int, limit: int, exploration: float) -> tuple[list[MovieItem], str, dict]:
    ranked, path = _read_cached_csv(ENHANCED_RANKED_TOP50_PATH, OFFLINE_RECOMMENDATIONS_PATH)
    _require_columns(ranked, {"userId", "movieId"}, path.name)
    working = ranked.copy()
    working["userId"] = pd.to_numeric(working["userId"], errors="coerce")
    working["movieId"] = pd.to_numeric(working["movieId"], errors="coerce")
    user_rows = working[working["userId"] == user_id].dropna(subset=["movieId"]).copy()

    if user_rows.empty:
        return _personalized_recipe_items(user_id, limit)

    score_col = "rank_score" if "rank_score" in user_rows.columns else "mmr_score"
    if score_col in user_rows.columns:
        user_rows[score_col] = pd.to_numeric(user_rows[score_col], errors="coerce").fillna(0.0)
    else:
        user_rows[score_col] = 0.0
    if "rank_position" in user_rows.columns:
        user_rows["_rank_position"] = pd.to_numeric(user_rows["rank_position"], errors="coerce").fillna(10**9)
        user_rows = user_rows.sort_values(["_rank_position", score_col, "movieId"], ascending=[True, False, True])
    else:
        user_rows = user_rows.sort_values([score_col, "movieId"], ascending=[False, True])

    candidate_count = min(max(limit * 6, 50), len(user_rows))
    candidate_rows = _json_safe_records(user_rows.head(candidate_count))
    profile_map, _ = _profile_records_by_id([int(row["movieId"]) for row in candidate_rows])
    favorite_terms, user_profile = _user_preference_terms(user_id)

    merged = []
    raw_scores = [_row_float(row, score_col, default=0.0) for row in candidate_rows]
    pop_scores = [
        _row_float(profile_map.get(int(row["movieId"]), {}), "movie_popularity", "popularity", default=0.0)
        for row in candidate_rows
    ]
    rank_norm = _normalize_values(raw_scores)
    pop_norm = _normalize_values(pop_scores)

    for index, row in enumerate(candidate_rows):
        recipe_id = int(row["movieId"])
        profile = profile_map.get(recipe_id, {})
        record = {**profile, **row}
        recipe_terms = _token_set(record.get("genres") or record.get("movie_genres"))
        novelty = 1.0 - _jaccard(recipe_terms, favorite_terms) if favorite_terms else 0.35
        rating = _row_float(record, "rating_value", "movie_avg_rating", "avg_rating", default=0.0)
        rating_norm = min(max(rating / 5.0, 0.0), 1.0)
        has_image = 1.0 if str(record.get("image_url") or "").strip() else 0.0
        relevance = 0.75 * rank_norm[index] + 0.25 * rating_norm
        discovery = 0.45 * novelty + 0.25 * has_image + 0.20 * pop_norm[index] + 0.10 * rating_norm
        record["_scenario_score"] = (1.0 - exploration) * relevance + exploration * discovery
        record["_scenario_terms"] = recipe_terms
        merged.append(record)

    selected: list[dict] = []
    remaining = merged
    while remaining and len(selected) < limit:
        def adjusted_score(record: dict) -> float:
            if not selected:
                return float(record["_scenario_score"])
            overlap = max(_jaccard(record["_scenario_terms"], item["_scenario_terms"]) for item in selected)
            return float(record["_scenario_score"]) - 0.12 * exploration * overlap

        best = max(remaining, key=adjusted_score)
        selected.append(best)
        remaining = [record for record in remaining if int(record["movieId"]) != int(best["movieId"])]

    items = [
        build_movie_item(
            int(record["movieId"]),
            f"菜谱 {int(record['movieId'])}",
            round(float(record["_scenario_score"]), 8),
            record,
        )
        for record in selected
    ]
    return items, _display_path(path), {
        "user_id": user_id,
        "exploration": exploration,
        "favorite_genres": user_profile.get("favorite_genres", ""),
        "candidate_count": candidate_count,
    }


def _record_exposures(state, user_id: int, items: list[MovieItem], request_id: str, group_name: str) -> None:
    if state.feedback_service is None or not hasattr(state.feedback_service, "record_exposure"):
        return
    for index, item in enumerate(items, start=1):
        try:
            state.feedback_service.record_exposure(
                user_id=user_id,
                movie_id=item.movie_id,
                request_id=request_id,
                run_id=group_name,
                experiment_name="recipe_recall_rank_v1",
                group_name=group_name,
                rank_position=index,
                score=item.score,
                reason="served_from_offline_recipe_recommendations",
            )
        except Exception:
            logger.exception("Failed to record exposure for user=%s recipe=%s", user_id, item.movie_id)


def _offline_recommendation_items(user_id: int, top_k: int) -> list[MovieItem]:
    """Build recommendations from offline artifacts inside a worker thread."""
    try:
        df, path = _read_cached_csv(OFFLINE_RECOMMENDATIONS_PATH)
        _require_columns(df, {"userId", "movieId"}, path.name)
        user_ids = pd.to_numeric(df["userId"], errors="coerce")
        user_recs = df[user_ids == user_id].copy()
    except HTTPException as exc:
        if exc.status_code != 404:
            raise
        user_recs = pd.DataFrame()

    if not user_recs.empty:
        if "rank_position" in user_recs.columns:
            user_recs["_rank_position"] = pd.to_numeric(user_recs["rank_position"], errors="coerce").fillna(10**9)
            user_recs = user_recs.sort_values(["_rank_position", "movieId"], ascending=[True, True])
        return [
            build_movie_item(
                int(record["movieId"]),
                f"Recipe {int(record['movieId'])}",
                _row_float(record, "rank_score", "mmr_score", "recall_score", default=0.0),
                record,
            )
            for record in _json_safe_records(user_recs.head(top_k))
        ]

    popular_records, _ = _popular_recipe_records(top_k)
    return [
        build_movie_item(record["movie_id"], record["title"], float(record.get("score") or 0.0), record)
        for record in popular_records
    ]


# ---------- Application state dependency ----------

class AppState:
    """Holds references to all service layer components."""
    def __init__(self):
        self.pipeline = None
        self.embedding_service = None
        self.faiss_index = None
        self.recall_service = None
        self.ranking_service = None
        self.cache = None
        self.user_profile_builder = None
        self.feedback_service = None
        self.ab_service = None
        self.taste_twin_service = None


_app_state = AppState()


def get_state() -> AppState:
    return _app_state


# ---------- Health ----------

@router.get("/health", response_model=HealthResponse)
async def health(state: AppState = Depends(get_state)):
    from app.config import get_settings
    settings = get_settings()

    redis_ok = False
    faiss_size = 0
    if state.cache:
        redis_ok = state.cache.health_check()
    if state.faiss_index:
        faiss_size = state.faiss_index.ntotal

    return HealthResponse(
        status="ok",
        version=settings.app_version,
        redis=redis_ok,
        faiss_index_size=faiss_size,
    )


# ---------- Authentication ----------

@router.post("/auth/register", response_model=AuthUserResponse)
async def auth_register(payload: AuthRegisterRequest):
    """Create a simple local demo account and bind it to a Food.com user id."""
    from auth.simple_auth import AuthError, SimpleAuthService

    try:
        user = SimpleAuthService().register(**payload.model_dump())
    except AuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AuthUserResponse(**user)


@router.post("/auth/login", response_model=AuthUserResponse)
async def auth_login(payload: AuthLoginRequest):
    """Login a simple local demo account."""
    from auth.simple_auth import AuthError, SimpleAuthService

    try:
        user = SimpleAuthService().login(**payload.model_dump())
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return AuthUserResponse(**user)


# ---------- Recommendation ----------

@router.get("/recipes/recommend/{user_id}", response_model=RecommendationResponse)
@router.get("/recommend/{user_id}", response_model=RecommendationResponse)
async def recommend(
    user_id: int,
    background_tasks: BackgroundTasks,
    top_k: int = Query(default=20, ge=1, le=100, description="推荐数量"),
    use_cache: bool = Query(default=True, description="是否使用 Redis 缓存"),
    state: AppState = Depends(get_state),
):
    """
    Get personalized recipe recommendations from precomputed offline artifacts.

    The legacy /recommend path is kept for compatibility. New callers can use
    /recipes/recommend/{user_id}.
    """
    t0 = time.perf_counter()
    if use_cache and state.cache:
        from feedback.realtime_recommender import RealtimeRecipeRecommender

        realtime_cache_key = RealtimeRecipeRecommender.cache_key(user_id, top_k)
        realtime_result = await run_in_threadpool(state.cache.get_json, realtime_cache_key)
        if realtime_result is not None:
            elapsed = (time.perf_counter() - t0) * 1000
            realtime_result["cached"] = True
            realtime_result["took_ms"] = round(elapsed, 2)
            return RecommendationResponse(**realtime_result)

    cache_key = f"recipe:offline_rec:user:{user_id}:k:{top_k}"
    if use_cache and state.cache:
        cached_result = await run_in_threadpool(state.cache.get_json, cache_key)
        if cached_result is not None:
            elapsed = (time.perf_counter() - t0) * 1000
            cached_result["cached"] = True
            cached_result["took_ms"] = round(elapsed, 2)
            return RecommendationResponse(**cached_result)

    items = await run_in_threadpool(_offline_recommendation_items, user_id, top_k)

    elapsed = (time.perf_counter() - t0) * 1000
    result = RecommendationResponse(
        user_id=user_id,
        recommendations=items,
        cached=False,
        took_ms=round(elapsed, 2),
    )

    if use_cache and state.cache:
        background_tasks.add_task(
            state.cache.set_json,
            cache_key,
            result.model_dump(),
            state.cache.settings.redis_ttl_recommend,
        )

    if state.ab_service is None:
        from experiment.ab_service import ABService

        state.ab_service = ABService(cache=state.cache)
    if state.feedback_service is None:
        from feedback.feedback_service import FeedbackService

        state.feedback_service = FeedbackService(cache=state.cache)
    group_info = await run_in_threadpool(state.ab_service.assign_group, user_id, "recipe_recall_rank_v1")
    group = group_info["group_name"]
    background_tasks.add_task(
        _record_exposures,
        state,
        user_id,
        items,
        f"offline-{user_id}-{int(time.time() * 1000)}",
        group,
    )

    return result

# ---------- Offline Display APIs ----------

@router.get("/offline/recommendations/{user_id}", response_model=OfflineRecommendationsResponse)
async def offline_recommendations(
    user_id: int,
    limit: int = Query(default=20, ge=1, le=100, description="离线推荐数量"),
):
    """Read precomputed offline recommendations for display only."""
    df, path = _read_offline_csv(OFFLINE_RECOMMENDATIONS_PATH)
    _require_columns(df, {"userId", "movieId"}, path.name)

    df["userId"] = pd.to_numeric(df["userId"], errors="coerce")
    user_recs = df[df["userId"] == user_id].copy()
    if user_recs.empty:
        raise HTTPException(status_code=404, detail=f"没有找到用户 {user_id} 的离线推荐结果")

    if "rank_position" in user_recs.columns:
        user_recs["_rank_position"] = pd.to_numeric(user_recs["rank_position"], errors="coerce").fillna(10**9)
        user_recs = user_recs.sort_values(["_rank_position", "movieId"], ascending=[True, True])

    records = _json_safe_records(user_recs.head(limit))
    items = [
        OfflineRecommendationItem(
            user_id=int(record.get("userId")),
            movie_id=int(record.get("movieId")),
            rank_position=record.get("rank_position"),
            rank_score=record.get("rank_score"),
            mmr_score=record.get("mmr_score"),
            movie_title=record.get("movie_title") or "",
            movie_genres=record.get("movie_genres") or "",
            favorite_genres=record.get("favorite_genres") or "",
            final_reason=record.get("final_reason") or "",
            reason_source=record.get("reason_source") or "",
            reason_evidence=record.get("reason_evidence"),
        )
        for record in records
    ]

    return OfflineRecommendationsResponse(
        user_id=user_id,
        recommendations=items,
        total=int(len(user_recs)),
        source=_display_path(path),
    )


@router.get("/offline/metrics", response_model=OfflineMetricsResponse)
async def offline_metrics():
    """Read offline evaluation metrics for dashboard display."""
    metrics, path = _read_offline_csv(OFFLINE_METRICS_PATH, OFFLINE_METRICS_FALLBACK_PATH)
    summary, summary_path = _read_offline_json(OFFLINE_METRICS_SUMMARY_PATH, OFFLINE_METRICS_SUMMARY_FALLBACK_PATH)
    return OfflineMetricsResponse(
        metrics=_json_safe_records(metrics),
        summary=summary,
        source=_display_path(path),
        summary_source=_display_path(summary_path) if summary_path else None,
    )


@router.get("/offline/ablation", response_model=OfflineAblationResponse)
async def offline_ablation():
    """Read offline ablation experiment results for dashboard display."""
    ablation, path = _read_offline_csv(OFFLINE_ABLATION_PATH, OFFLINE_ABLATION_FALLBACK_PATH)
    return OfflineAblationResponse(
        ablation=_json_safe_records(ablation),
        source=_display_path(path),
    )


@router.get("/ab/group/{user_id}", response_model=ABGroupResponse)
async def ab_group(
    user_id: int,
    experiment_name: str = Query(default="recall_rank_v1"),
    state: AppState = Depends(get_state),
):
    """Return the stable A/B group for a user."""
    if state.ab_service is None:
        from experiment.ab_service import ABService

        state.ab_service = ABService(cache=state.cache)
    result = state.ab_service.assign_group(user_id, experiment_name)
    return ABGroupResponse(user_id=user_id, **result)


@router.get("/ab/metrics", response_model=ABMetricsResponse)
async def ab_metrics(
    experiment_name: str = Query(default="recall_rank_v1"),
    state: AppState = Depends(get_state),
):
    """Read lightweight A/B metrics from feedback logs."""
    if state.ab_service is None:
        from experiment.ab_service import ABService

        state.ab_service = ABService(cache=state.cache)
    return ABMetricsResponse(**state.ab_service.metrics(experiment_name))


@router.get("/metrics")
async def prometheus_metrics(state: AppState = Depends(get_state)):
    """Expose Prometheus-compatible process and recommendation counters."""
    from monitor.metrics import build_prometheus_metrics

    redis_ok = bool(state.cache.health_check()) if state.cache else False
    faiss_size = int(state.faiss_index.ntotal) if state.faiss_index else 0
    return Response(
        content=build_prometheus_metrics(redis_ok=redis_ok, faiss_size=faiss_size),
        media_type="text/plain; version=0.0.4",
    )


@router.get("/offline/user-profile/{user_id}", response_model=OfflineUserProfileResponse)
async def offline_user_profile(user_id: int):
    """Read a Spark-built offline user profile for display only."""
    profiles, path = _read_offline_csv(OFFLINE_USER_PROFILE_PATH)
    profile = _first_profile_row(profiles, "userId", user_id, path.name)
    return OfflineUserProfileResponse(
        user_id=user_id,
        profile=profile,
        source=_display_path(path),
    )


@router.get("/offline/movie-profile/{movie_id}", response_model=OfflineMovieProfileResponse)
async def offline_movie_profile(movie_id: int):
    """Read a Spark-built offline movie profile for display only."""
    profiles, path = _read_cached_csv(OFFLINE_MOVIE_PROFILE_PATH)
    profile = _first_profile_row(profiles, "movieId", movie_id, path.name)
    detail = _optional_recipe_detail(movie_id)
    if detail:
        profile.update({key: value for key, value in detail.items() if value is not None})
    return OfflineMovieProfileResponse(
        movie_id=movie_id,
        profile=profile,
        source=_display_path(path),
    )


@router.get("/offline/popular-recipes", response_model=OfflinePopularRecipesResponse)
async def offline_popular_recipes(
    limit: int = Query(default=20, ge=1, le=100),
    with_images_first: bool = Query(default=True, description="展示时优先返回有图片的菜谱"),
):
    """Read popular recipe profiles from offline recipe artifacts."""
    records, path = _popular_recipe_records(limit, with_images_first)
    return OfflinePopularRecipesResponse(
        popular=records,
        total=int(len(records)),
        source=_display_path(path),
    )

# ---------- Popular Recipes ----------

@router.get("/recipes/popular", response_model=PopularResponse)
@router.get("/popular", response_model=PopularResponse)
async def popular(
    limit: int = Query(default=50, ge=1, le=200),
    state: AppState = Depends(get_state),
):
    """Get global popular recipes from offline recipe profiles."""
    t0 = time.perf_counter()
    cache_key = f"recipe:popular:{limit}"
    if state.cache:
        cached = state.cache.get_json(cache_key)
        if cached:
            elapsed = (time.perf_counter() - t0) * 1000
            return PopularResponse(popular=cached, took_ms=round(elapsed, 2))

    records, _ = _popular_recipe_records(limit)
    items = [_movie_detail_from_profile(record) for record in records]
    elapsed = (time.perf_counter() - t0) * 1000

    if state.cache:
        state.cache.set_json(cache_key, [m.model_dump() for m in items], ttl=state.cache.settings.redis_ttl_popular)

    return PopularResponse(popular=items, took_ms=round(elapsed, 2))

# ---------- Recipe Detail ----------

@router.get("/recipe/{movie_id}", response_model=MovieDetail)
@router.get("/movie/{movie_id}", response_model=MovieDetail)
async def movie_detail(
    movie_id: int,
    state: AppState = Depends(get_state),
):
    """Get detailed information about a specific recipe."""
    cache_key = f"recipe:detail:{movie_id}"
    if state.cache:
        cached = state.cache.get_json(cache_key)
        if cached:
            return MovieDetail(**cached)

    try:
        info = _recipe_from_es(movie_id) or _offline_profile(movie_id)
    except HTTPException as exc:
        if exc.status_code == 404:
            raise HTTPException(status_code=404, detail=f"菜谱 {movie_id} 不存在") from exc
        raise
    detail = _movie_detail_from_profile(info)
    if state.cache:
        state.cache.set_json(cache_key, detail.model_dump(), ttl=3600)

    return detail


@router.get("/recipe/{movie_id}/similar", response_model=SimilarRecipesResponse)
@router.get("/movie/{movie_id}/similar", response_model=SimilarRecipesResponse)
async def similar_recipes(
    movie_id: int,
    limit: int = Query(default=8, ge=1, le=30),
):
    """Find similar recipes by querying the FAISS HNSW index with ALS embeddings."""
    items, source = _similar_recipe_items(movie_id, limit)
    return SimilarRecipesResponse(
        movie_id=movie_id,
        similar=items,
        total=len(items),
        source=source,
    )


@router.post("/recipes/cold-start", response_model=ColdStartResponse)
async def cold_start_recipes(payload: ColdStartRequest):
    """Recommend recipes from explicit new-user preferences."""
    from recommendation.cold_start import cold_start_recommend

    params = payload.model_dump()
    params["ingredients"] = _map_ingredient_terms(list(payload.ingredients))
    result = cold_start_recommend(
        **params,
        profile_path=OFFLINE_MOVIE_PROFILE_PATH,
        metadata_path=OFFLINE_RECIPE_METADATA_PATH,
    )
    return ColdStartResponse(**result)


@router.post("/recipes/scenario-recommend", response_model=ScenarioRecommendResponse)
async def scenario_recommend_recipes(payload: ScenarioRecommendRequest):
    """Recommend recipes for product scenarios such as pantry, health, quick meals, and discovery."""
    from recommendation.cold_start import cold_start_recommend

    scenario = payload.scenario.strip().lower().replace("_", "-")
    scenario_aliases = {
        "personal": "personalized",
        "user": "personalized",
        "pantry": "ingredients",
        "ingredient": "ingredients",
        "fridge": "ingredients",
        "health": "healthy",
        "diet": "healthy",
        "fast": "quick",
        "quick-meal": "quick",
        "discover": "explore",
        "discovery": "explore",
    }
    scenario = scenario_aliases.get(scenario, scenario)

    if scenario == "personalized":
        if payload.user_id is None:
            raise HTTPException(status_code=400, detail="个性化推荐需要先提供用户 ID")
        items, source, context = _personalized_recipe_items(payload.user_id, payload.limit)
        return ScenarioRecommendResponse(
            scenario=scenario,
            recommendations=items,
            total=len(items),
            source=source,
            context={"mode": "offline_lightgbm_mmr", **context},
        )

    if scenario == "explore":
        if payload.user_id is None:
            raise HTTPException(status_code=400, detail="探索发现推荐需要先提供用户 ID")
        items, source, context = _explore_recipe_items(payload.user_id, payload.limit, payload.exploration)
        return ScenarioRecommendResponse(
            scenario=scenario,
            recommendations=items,
            total=len(items),
            source=source,
            context={"mode": "lightgbm_top50_discovery_rerank", **context},
        )

    if scenario not in {"ingredients", "healthy", "quick"}:
        raise HTTPException(status_code=400, detail=f"不支持的推荐场景：{payload.scenario}")

    preferred_tags = list(payload.preferred_tags)
    ingredients = _map_ingredient_terms(list(payload.ingredients))
    dietary_goals = list(payload.dietary_goals)
    max_minutes = payload.max_minutes
    min_rating = payload.min_rating

    if scenario == "ingredients":
        preferred_tags.extend(["main-ingredient", "easy"])
    elif scenario == "healthy":
        preferred_tags.extend(["healthy", "dietary"])
        if not dietary_goals:
            dietary_goals = ["healthy", "low-calorie", "low-fat"]
        if min_rating is None:
            min_rating = 4.0
    elif scenario == "quick":
        preferred_tags.extend(["easy", "quick", "30-minutes-or-less", "time-to-make"])
        max_minutes = max_minutes or 30

    result = cold_start_recommend(
        preferred_tags=preferred_tags,
        ingredients=ingredients,
        dietary_goals=dietary_goals,
        max_minutes=max_minutes,
        min_rating=min_rating,
        require_image=payload.require_image,
        limit=payload.limit,
        profile_path=OFFLINE_MOVIE_PROFILE_PATH,
        metadata_path=OFFLINE_RECIPE_METADATA_PATH,
    )
    return ScenarioRecommendResponse(
        scenario=scenario,
        recommendations=result["recommendations"],
        total=int(result["total"]),
        source=f"{result['source']}:{_display_path(OFFLINE_MOVIE_PROFILE_PATH)}",
        context={
            "mode": "content_cold_start",
            "preference_profile": result.get("preference_profile", {}),
        },
    )


@router.get("/recipes/ingredients", response_model=IngredientSearchResponse)
async def recipe_ingredients(
    q: str = Query(default="", description="食材关键词，留空返回高频食材"),
    limit: int = Query(default=30, ge=1, le=200),
):
    """Return frequent recipe ingredients for ingredient input autocomplete."""
    query = q.strip().lower()
    items, _, path = _ingredient_catalog(OFFLINE_INGREDIENT_TRANSLATION_PATH)
    if query:
        matched = [item for item in items if query in item["label"].lower() or query in item["name"]]
    else:
        matched = items
    ranked = _rank_ingredient_matches(matched, query)
    return IngredientSearchResponse(
        ingredients=ranked[:limit],
        total=len(ranked),
        source=_display_path(path),
        query=query,
    )


# ---------- User Profile ----------

@router.get("/user/{user_id}/profile", response_model=UserProfileResponse)
async def user_profile(
    user_id: int,
    state: AppState = Depends(get_state),
):
    """Get user profile: rating stats, genre preferences, history."""
    if state.user_profile_builder is None:
        raise HTTPException(status_code=503, detail="服务尚未初始化")

    cache_key = f"profile:{user_id}"
    if state.cache:
        cached = state.cache.get_json(cache_key)
        if cached:
            return UserProfileResponse(**cached)

    profile = state.user_profile_builder.build_profile(user_id)

    if state.cache:
        state.cache.set_json(cache_key, profile, ttl=state.cache.settings.redis_ttl_user_profile)

    return UserProfileResponse(**profile)


@router.get("/user/{user_id}/realtime-profile", response_model=RealtimeProfileResponse)
async def realtime_user_profile(user_id: int, state: AppState = Depends(get_state)):
    """Read the realtime feedback profile from Redis or SQLite fallback."""
    if state.feedback_service is None:
        from feedback.feedback_service import FeedbackService

        state.feedback_service = FeedbackService(cache=state.cache)
    profile = state.feedback_service.get_realtime_profile(user_id)
    return RealtimeProfileResponse(user_id=user_id, profile=profile)


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(payload: FeedbackRequest, state: AppState = Depends(get_state)):
    """Persist user feedback and update the realtime profile cache."""
    if state.feedback_service is None:
        from feedback.feedback_service import FeedbackService

        state.feedback_service = FeedbackService(cache=state.cache)
    try:
        result = state.feedback_service.record_feedback(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return FeedbackResponse(status="ok", **result)


@router.post("/recommendation-exposure", response_model=dict)
async def submit_recommendation_exposure(payload: ExposureRequest, state: AppState = Depends(get_state)):
    """Persist a recommendation exposure event for CTR and A/B metrics."""
    if state.feedback_service is None:
        from feedback.feedback_service import FeedbackService

        state.feedback_service = FeedbackService(cache=state.cache)
    result = state.feedback_service.record_exposure(**payload.model_dump())
    return {"status": "ok", **result}


# ---------- Search ----------

@router.get("/recipes/search", response_model=SearchResponse)
@router.get("/search", response_model=SearchResponse)
async def search(
    q: str = Query(..., min_length=1, description="搜索关键词"),
    limit: int = Query(default=20, ge=1, le=100),
    state: AppState = Depends(get_state),
):
    """Search recipes by title, tags, author, or description."""
    query = q.lower()
    es_records = _search_recipes_from_es(query, limit)
    if es_records:
        results = [_movie_detail_from_profile(record) for record in es_records]
        return SearchResponse(results=results, total=len(results))

    profiles, path = _read_cached_csv(OFFLINE_MOVIE_PROFILE_PATH)
    _require_columns(profiles, {"movieId", "title"}, path.name)
    searchable = profiles.copy()
    text_columns = [col for col in ["title", "clean_title", "genres", "description", "author_name"] if col in searchable]
    combined = searchable[text_columns].fillna("").astype(str).agg(" ".join, axis=1).str.lower()
    matched = searchable[combined.str.contains(query, regex=False, na=False)].head(limit)
    results = [_movie_detail_from_profile(record) for record in _json_safe_records(matched)]

    return SearchResponse(results=results, total=len(results))

# ---------- Rebuild Index ----------

@router.post("/rebuild-index", response_model=RebuildResponse)
async def rebuild_index(
    state: AppState = Depends(get_state),
):
    """
    Compatibility endpoint for the former online index rebuild.

    Recipe artifacts are rebuilt by scripts/run_recipe_pipeline.py and the
    LightGCN recall stage; this endpoint only clears serving caches.
    """
    t0 = time.perf_counter()
    if state.cache:
        state.cache.delete_pattern("recipe:*")
        state.cache.delete_pattern("rec:*")
        state.cache.delete_pattern("topk:*")
        logger.info("Cleared recipe recommendation caches")
    elapsed = time.perf_counter() - t0
    return RebuildResponse(
        status="success",
        message="食谱推荐服务缓存已清理。如需重建离线产物，请运行 scripts/run_recipe_pipeline.py。",
        took_seconds=round(elapsed, 2),
    )
