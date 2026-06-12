"""Select the best enhanced ranker from existing data/rank artifacts.

This script does not rerun Spark or recall stages. It reads the current
rank_train/rank_candidates files, joins profile metadata, adds recommendation
system features, compares XGBoost, LightGBM, and logistic regression, then
exports Top50 candidates from the best validation model for the main MMR stage.
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TRAIN = PROJECT_ROOT / "data" / "rank" / "rank_train.csv"
DEFAULT_CANDIDATES = PROJECT_ROOT / "data" / "rank" / "rank_candidates_optimized.csv"
DEFAULT_FEATURES = PROJECT_ROOT / "data" / "rank" / "rank_feature_columns.json"
DEFAULT_USER_PROFILE = PROJECT_ROOT / "data" / "features" / "user_profile.csv"
DEFAULT_MOVIE_PROFILE = PROJECT_ROOT / "data" / "features" / "movie_profile.csv"
DEFAULT_RECIPE_METADATA = PROJECT_ROOT / "data" / "recipe-canonical" / "recipe_metadata.csv"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "rank" / "enhanced"
DEFAULT_MODEL_DIR = PROJECT_ROOT / "models" / "enhanced_ranker"

BASE_REQUIRED = {"userId", "movieId", "label"}
PROFILE_COLS = [
    "movieId",
    "has_image",
    "photo_count",
    "rating_value",
    "review_count",
    "recipe_yield_min",
    "recipe_yield_max",
    "serves_best_guess",
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
USER_PROFILE_COLS = ["userId", "high_rating_movie_ids", "recent_movie_ids"]
ENHANCED_FEATURES = [
    "rating_alignment_score",
    "popularity_adjusted_genre_match",
    "recall_strength_score",
    "als_itemcf_agreement",
    "embedding_lightgcn_agreement",
    "active_recall_interaction",
    "is_recent_user_recipe",
    "is_high_rating_user_recipe",
    "has_image",
    "log_photo_count",
    "log_review_count",
    "external_rating_value",
    "external_rating_gap",
    "recipe_yield_span",
    "serves_best_guess",
    "recipe_age_years",
    "recipe_recency_score",
    "minutes",
    "log_minutes",
    "n_steps",
    "n_ingredients",
    "calories",
    "protein_pct",
    "total_fat_pct",
    "sugar_pct",
    "sodium_pct",
    "carbohydrates_pct",
    "protein_per_calorie",
    "ingredient_step_ratio",
]

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Select and export the best enhanced recipe ranker from existing rank data.")
    parser.add_argument("--train", default=str(DEFAULT_TRAIN))
    parser.add_argument("--candidates", default=str(DEFAULT_CANDIDATES))
    parser.add_argument("--features", default=str(DEFAULT_FEATURES))
    parser.add_argument("--user-profile", default=str(DEFAULT_USER_PROFILE))
    parser.add_argument("--movie-profile", default=str(DEFAULT_MOVIE_PROFILE))
    parser.add_argument("--recipe-metadata", default=str(DEFAULT_RECIPE_METADATA))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--model-dir", default=str(DEFAULT_MODEL_DIR))
    parser.add_argument("--max-train-rows", type=int, default=0, help="0 means use all rows.")
    parser.add_argument("--max-candidate-rows", type=int, default=0, help="0 means use all rows.")
    parser.add_argument("--n-estimators", type=int, default=120)
    parser.add_argument("--valid-user-ratio", type=float, default=0.2)
    parser.add_argument("--top-n", type=int, default=50)
    return parser.parse_args()


def _load_json_list(path: Path) -> list[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not all(isinstance(item, str) for item in data):
        raise ValueError(f"Feature file must contain a JSON list of strings: {path}")
    return data


def _available_usecols(path: Path, wanted: list[str]) -> list[str]:
    columns = pd.read_csv(path, nrows=0).columns.tolist()
    return [col for col in wanted if col in columns]


def _read_rank(path: Path, feature_columns: list[str], max_rows: int = 0) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Rank input not found: {path}")
    df = pd.read_csv(path)
    missing = sorted((BASE_REQUIRED | set(feature_columns)) - set(df.columns))
    if missing:
        raise ValueError(f"{path} missing required columns: {missing}")
    df["userId"] = pd.to_numeric(df["userId"], errors="coerce")
    df["movieId"] = pd.to_numeric(df["movieId"], errors="coerce")
    df["label"] = pd.to_numeric(df["label"], errors="coerce").fillna(0).astype(int).clip(0, 1)
    df = df.dropna(subset=["userId", "movieId"]).copy()
    df["userId"] = df["userId"].astype(int)
    df["movieId"] = df["movieId"].astype(int)
    for col in feature_columns:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0).astype("float32")
    if max_rows > 0 and len(df) > max_rows and "label" in df.columns:
        parts = []
        for _, group in df.groupby("label", group_keys=False):
            n = max(1, int(max_rows * len(group) / len(df)))
            parts.append(group.sample(n=min(n, len(group)), random_state=42))
        df = pd.concat(parts, ignore_index=True)
        if len(df) > max_rows:
            df = df.sample(n=max_rows, random_state=42).reset_index(drop=True)
    return df


def _read_movie_features(path: Path) -> pd.DataFrame:
    usecols = _available_usecols(path, PROFILE_COLS)
    df = pd.read_csv(path, usecols=usecols)
    if "movieId" not in df.columns:
        raise ValueError(f"{path} missing movieId")
    df["movieId"] = pd.to_numeric(df["movieId"], errors="coerce")
    df = df.dropna(subset=["movieId"]).drop_duplicates("movieId").copy()
    df["movieId"] = df["movieId"].astype(int)
    return df


def _read_recipe_metadata(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame({"recipe_id": pd.Series(dtype=int)})
    usecols = _available_usecols(path, METADATA_COLS)
    df = pd.read_csv(path, usecols=usecols)
    if "recipe_id" not in df.columns:
        return pd.DataFrame({"recipe_id": pd.Series(dtype=int)})
    df["recipe_id"] = pd.to_numeric(df["recipe_id"], errors="coerce")
    df = df.dropna(subset=["recipe_id"]).drop_duplicates("recipe_id").copy()
    df["recipe_id"] = df["recipe_id"].astype(int)
    return df


def _id_set(value: Any) -> set[int]:
    if value is None or pd.isna(value):
        return set()
    result = set()
    for part in str(value).split("|"):
        try:
            result.add(int(float(part)))
        except (TypeError, ValueError):
            continue
    return result


def _read_user_sets(path: Path) -> pd.DataFrame:
    usecols = _available_usecols(path, USER_PROFILE_COLS)
    df = pd.read_csv(path, usecols=usecols)
    if "userId" not in df.columns:
        raise ValueError(f"{path} missing userId")
    df["userId"] = pd.to_numeric(df["userId"], errors="coerce")
    df = df.dropna(subset=["userId"]).drop_duplicates("userId").copy()
    df["userId"] = df["userId"].astype(int)
    for col in ["high_rating_movie_ids", "recent_movie_ids"]:
        if col not in df.columns:
            df[col] = ""
    df["_high_rating_set"] = df["high_rating_movie_ids"].map(_id_set)
    df["_recent_set"] = df["recent_movie_ids"].map(_id_set)
    return df[["userId", "_high_rating_set", "_recent_set"]]


def _add_features(
    df: pd.DataFrame,
    movie_features: pd.DataFrame,
    metadata: pd.DataFrame,
    user_sets: pd.DataFrame,
) -> pd.DataFrame:
    out = df.merge(movie_features, on="movieId", how="left").merge(
        metadata,
        left_on="movieId",
        right_on="recipe_id",
        how="left",
    ).merge(user_sets, on="userId", how="left")

    for col in [
        "has_image",
        "photo_count",
        "rating_value",
        "review_count",
        "recipe_yield_min",
        "recipe_yield_max",
        "serves_best_guess",
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
    ]:
        if col not in out.columns:
            out[col] = 0.0
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0.0).astype("float32")

    out["rating_alignment_score"] = 1.0 - (
        (out["user_avg_rating"] - out["movie_avg_rating"]).abs().clip(0, 5) / 5.0
    )
    out["popularity_adjusted_genre_match"] = out["genre_match_score"] * np.log1p(out["movie_rating_count"].clip(lower=0))
    out["recall_strength_score"] = out["merged_recall_score"] * (1.0 + out["recall_source_count"])
    out["als_itemcf_agreement"] = np.minimum(out["als_score"], out["itemcf_score"])
    out["embedding_lightgcn_agreement"] = np.minimum(out["embedding_score"], out["lightgcn_score"])
    out["active_recall_interaction"] = out["active_level_code"].clip(lower=0) * out["recall_source_count"]

    recent_sets = out["_recent_set"].map(lambda value: value if isinstance(value, set) else set())
    high_sets = out["_high_rating_set"].map(lambda value: value if isinstance(value, set) else set())
    movie_ids = out["movieId"].astype(int).tolist()
    out["is_recent_user_recipe"] = [1.0 if movie_id in ids else 0.0 for movie_id, ids in zip(movie_ids, recent_sets)]
    out["is_high_rating_user_recipe"] = [1.0 if movie_id in ids else 0.0 for movie_id, ids in zip(movie_ids, high_sets)]

    out["has_image"] = out["has_image"].clip(0, 1)
    out["log_photo_count"] = np.log1p(out["photo_count"].clip(lower=0))
    out["log_review_count"] = np.log1p(out["review_count"].clip(lower=0))
    out["external_rating_value"] = out["rating_value"].where(out["rating_value"] > 0, out["movie_avg_rating"])
    out["external_rating_gap"] = (out["user_avg_rating"] - out["external_rating_value"]).abs().clip(0, 5)
    out["recipe_yield_span"] = (out["recipe_yield_max"] - out["recipe_yield_min"]).clip(lower=0)
    out["recipe_age_years"] = (2026.0 - out["movie_year"]).clip(lower=0)
    out["recipe_recency_score"] = 1.0 / (1.0 + out["recipe_age_years"])
    out["log_minutes"] = np.log1p(out["minutes"].clip(lower=0))
    out["protein_per_calorie"] = out["protein_pct"] / out["calories"].replace(0, np.nan)
    out["protein_per_calorie"] = out["protein_per_calorie"].replace([np.inf, -np.inf], 0).fillna(0.0)
    out["ingredient_step_ratio"] = out["n_ingredients"] / out["n_steps"].replace(0, np.nan)
    out["ingredient_step_ratio"] = out["ingredient_step_ratio"].replace([np.inf, -np.inf], 0).fillna(0.0)

    for col in ENHANCED_FEATURES:
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0.0).astype("float32")
    return out.drop(columns=["recipe_id", "_recent_set", "_high_rating_set"], errors="ignore")


def _split_by_user(df: pd.DataFrame, valid_user_ratio: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(42)
    users = np.array(sorted(df["userId"].unique()))
    rng.shuffle(users)
    valid_count = max(1, int(len(users) * valid_user_ratio))
    valid_users = set(users[:valid_count].tolist())
    valid = df[df["userId"].isin(valid_users)].copy()
    train = df[~df["userId"].isin(valid_users)].copy()
    if train.empty or valid.empty:
        raise ValueError("Train/valid split produced empty data.")
    return train, valid


def _ranking_metrics(df: pd.DataFrame, score_col: str, k: int = 10) -> dict[str, float]:
    precision, recall, ndcg, hit_rate = [], [], [], []
    ordered = df.sort_values(["userId", score_col, "movieId"], ascending=[True, False, True])
    for _, group in ordered.groupby("userId", sort=False):
        relevant = int((group["label"] == 1).sum())
        if relevant <= 0:
            continue
        top = group.head(k)
        hits = top["label"].astype(int).tolist()
        hit_count = sum(hits)
        precision.append(hit_count / k)
        recall.append(hit_count / relevant)
        hit_rate.append(1.0 if hit_count else 0.0)
        dcg = sum(rel / math.log2(idx + 2) for idx, rel in enumerate(hits))
        idcg = sum(1 / math.log2(idx + 2) for idx in range(min(relevant, k)))
        ndcg.append(dcg / idcg if idcg else 0.0)
    count = len(precision)
    return {
        "precision_at_10": float(np.mean(precision)) if count else 0.0,
        "recall_at_10": float(np.mean(recall)) if count else 0.0,
        "ndcg_at_10": float(np.mean(ndcg)) if count else 0.0,
        "hit_rate_at_10": float(np.mean(hit_rate)) if count else 0.0,
        "evaluated_users": int(count),
    }


def _fit_models(train: pd.DataFrame, valid: pd.DataFrame, feature_columns: list[str], n_estimators: int):
    import joblib
    import xgboost as xgb
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import accuracy_score, log_loss, roc_auc_score
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    try:
        import lightgbm as lgb
    except Exception:
        lgb = None

    X_train = train[feature_columns].astype(np.float32)
    y_train = train["label"].astype(int)
    X_valid = valid[feature_columns].astype(np.float32)
    y_valid = valid["label"].astype(int)
    models: list[tuple[str, Any, str]] = []

    xgb_grid = [
        {"max_depth": 4, "learning_rate": 0.05},
        {"max_depth": 5, "learning_rate": 0.05},
        {"max_depth": 5, "learning_rate": 0.08},
    ]
    for params in xgb_grid:
        model = xgb.XGBClassifier(
            objective="binary:logistic",
            eval_metric="auc",
            n_estimators=n_estimators,
            subsample=0.85,
            colsample_bytree=0.85,
            random_state=42,
            n_jobs=-1,
            tree_method="hist",
            **params,
        )
        models.append((f"xgboost_depth{params['max_depth']}_lr{params['learning_rate']}", model, "xgb"))

    if lgb is not None:
        models.append(
            (
                "lightgbm",
                lgb.LGBMClassifier(
                    objective="binary",
                    n_estimators=n_estimators,
                    learning_rate=0.05,
                    num_leaves=63,
                    subsample=0.85,
                    colsample_bytree=0.85,
                    random_state=42,
                    n_jobs=-1,
                    verbose=-1,
                ),
                "lgb",
            )
        )
    models.append(
        (
            "logistic_regression",
            make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, class_weight="balanced", n_jobs=-1)),
            "sklearn",
        )
    )

    results = []
    trained = {}
    for name, model, model_kind in models:
        logger.info("Training enhanced ranker: %s", name)
        if model_kind == "xgb":
            model.fit(X_train, y_train, eval_set=[(X_valid, y_valid)], verbose=False)
        else:
            model.fit(X_train, y_train)
        if hasattr(model, "predict_proba"):
            prob = model.predict_proba(X_valid)[:, 1]
        else:
            prob = model.predict(X_valid)
        prob = np.asarray(prob, dtype=float)
        if y_valid.nunique() >= 2:
            auc = float(roc_auc_score(y_valid, prob))
            loss = float(log_loss(y_valid, np.clip(prob, 1e-6, 1 - 1e-6), labels=[0, 1]))
        else:
            auc = 0.0
            loss = 0.0
        eval_df = valid[["userId", "movieId", "label"]].copy()
        eval_df["score"] = prob
        rank_metrics = _ranking_metrics(eval_df, "score", 10)
        row = {
            "model": name,
            "auc": auc,
            "accuracy": float(accuracy_score(y_valid, prob >= 0.5)),
            "logloss": loss,
            **rank_metrics,
        }
        results.append(row)
        trained[name] = (model, model_kind)
    comparison = pd.DataFrame(results).sort_values(["ndcg_at_10", "auc", "model"], ascending=[False, False, True])
    best_name = str(comparison.iloc[0]["model"])
    best_model, best_kind = trained[best_name]
    return comparison, best_name, best_model, best_kind, joblib


def _predict_best(model: Any, kind: str, df: pd.DataFrame, feature_columns: list[str]) -> np.ndarray:
    X = df[feature_columns].astype(np.float32)
    if hasattr(model, "predict_proba"):
        score = model.predict_proba(X)[:, 1]
    else:
        score = model.predict(X)
    score = np.asarray(score, dtype=float)
    return np.clip(score, 0.0, 1.0)


def train_enhanced_ranker(
    train_path: str | Path = DEFAULT_TRAIN,
    candidates_path: str | Path = DEFAULT_CANDIDATES,
    feature_path: str | Path = DEFAULT_FEATURES,
    user_profile_path: str | Path = DEFAULT_USER_PROFILE,
    movie_profile_path: str | Path = DEFAULT_MOVIE_PROFILE,
    recipe_metadata_path: str | Path = DEFAULT_RECIPE_METADATA,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    model_dir: str | Path = DEFAULT_MODEL_DIR,
    max_train_rows: int = 0,
    max_candidate_rows: int = 0,
    n_estimators: int = 120,
    valid_user_ratio: float = 0.2,
    top_n: int = 50,
) -> dict[str, Any]:
    output_path = Path(output_dir)
    model_path = Path(model_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    model_path.mkdir(parents=True, exist_ok=True)

    base_features = _load_json_list(Path(feature_path))
    movie_features = _read_movie_features(Path(movie_profile_path))
    metadata = _read_recipe_metadata(Path(recipe_metadata_path))
    user_sets = _read_user_sets(Path(user_profile_path))

    logger.info("Reading existing rank train: %s", train_path)
    train_raw = _read_rank(Path(train_path), base_features, max_train_rows)
    train_enhanced = _add_features(train_raw, movie_features, metadata, user_sets)
    feature_columns = [*base_features, *[col for col in ENHANCED_FEATURES if col not in base_features]]
    train_df, valid_df = _split_by_user(train_enhanced, valid_user_ratio)

    comparison, best_name, best_model, best_kind, joblib = _fit_models(train_df, valid_df, feature_columns, n_estimators)
    comparison_path = output_path / "enhanced_model_comparison.csv"
    comparison.to_csv(comparison_path, index=False)

    feature_columns_path = output_path / "enhanced_rank_feature_columns.json"
    feature_columns_path.write_text(json.dumps(feature_columns, ensure_ascii=False, indent=2), encoding="utf-8")

    if best_kind in {"xgb", "lgb"} and hasattr(best_model, "feature_importances_"):
        importance = pd.DataFrame({"feature": feature_columns, "importance": best_model.feature_importances_.astype(float)})
    else:
        importance = pd.DataFrame({"feature": feature_columns, "importance": np.zeros(len(feature_columns))})
    importance = importance.sort_values(["importance", "feature"], ascending=[False, True])
    importance_path = output_path / "enhanced_feature_importance.csv"
    importance.to_csv(importance_path, index=False)

    if best_kind == "xgb":
        best_model_path = model_path / "best_enhanced_xgboost.json"
        best_model.save_model(str(best_model_path))
    elif best_kind == "lgb":
        best_model_path = model_path / "best_enhanced_lightgbm.txt"
        best_model.booster_.save_model(str(best_model_path))
    else:
        best_model_path = model_path / "best_enhanced_logistic_regression.joblib"
        joblib.dump(best_model, best_model_path)

    logger.info("Reading existing rank candidates: %s", candidates_path)
    candidates_raw = _read_rank(Path(candidates_path), base_features, max_candidate_rows)
    candidates_enhanced = _add_features(candidates_raw, movie_features, metadata, user_sets)
    candidates_enhanced["rank_score"] = _predict_best(best_model, best_kind, candidates_enhanced, feature_columns)
    ranked = (
        candidates_enhanced.sort_values(
            ["userId", "rank_score", "merged_recall_score", "movieId"],
            ascending=[True, False, False, True],
        )
        .groupby("userId", group_keys=False)
        .head(top_n)
        .copy()
    )
    ranked["rank_position"] = ranked.groupby("userId").cumcount() + 1
    ranked_output_cols = [
        "userId",
        "movieId",
        "rank_position",
        "rank_score",
        "label",
        "als_score",
        "itemcf_score",
        "merged_recall_score",
        "recall_source_count",
        "genre_match_score",
        "movie_avg_rating",
        "movie_popularity",
        "rating_alignment_score",
        "is_recent_user_recipe",
        "has_image",
        "review_count",
        "calories",
        "protein_pct",
    ]
    for col in ranked_output_cols:
        if col not in ranked.columns:
            ranked[col] = 0.0
    ranked_path = output_path / "ranked_top50_enhanced.csv"
    ranked[ranked_output_cols].to_csv(ranked_path, index=False)

    metrics = {
        "train_rows": int(len(train_df)),
        "valid_rows": int(len(valid_df)),
        "feature_count": int(len(feature_columns)),
        "enhanced_feature_count": int(len(ENHANCED_FEATURES)),
        "best_model": best_name,
        "best_model_kind": best_kind,
        "best_valid_auc": float(comparison.iloc[0]["auc"]),
        "best_valid_ndcg_at_10": float(comparison.iloc[0]["ndcg_at_10"]),
        "best_valid_precision_at_10": float(comparison.iloc[0]["precision_at_10"]),
        "best_valid_recall_at_10": float(comparison.iloc[0]["recall_at_10"]),
        "candidate_rows_scored": int(len(candidates_enhanced)),
        "ranked_rows": int(len(ranked)),
        "ranked_user_count": int(ranked["userId"].nunique()),
        "comparison_path": str(comparison_path),
        "feature_columns_path": str(feature_columns_path),
        "feature_importance_path": str(importance_path),
        "best_model_path": str(best_model_path),
        "ranked_output_path": str(ranked_path),
    }
    metrics_path = output_path / "enhanced_ranker_metrics.json"
    metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info("best model: %s", best_name)
    logger.info("valid AUC: %.6f", metrics["best_valid_auc"])
    logger.info("valid NDCG@10: %.6f", metrics["best_valid_ndcg_at_10"])
    logger.info("ranked rows: %s", metrics["ranked_rows"])
    logger.info("quality validation result: success")
    return metrics


def main() -> None:
    args = parse_args()
    try:
        train_enhanced_ranker(
            args.train,
            args.candidates,
            args.features,
            args.user_profile,
            args.movie_profile,
            args.recipe_metadata,
            args.output_dir,
            args.model_dir,
            args.max_train_rows,
            args.max_candidate_rows,
            args.n_estimators,
            args.valid_user_ratio,
            args.top_n,
        )
    except Exception as exc:
        logger.error("%s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
