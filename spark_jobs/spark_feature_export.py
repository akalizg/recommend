"""
Export Spark-built ranking features for the offline XGBoost rank stage.

This job stays on the offline side path. It does not modify FastAPI, Vue, or
the existing online recommendation flow.
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import shutil
import sys
import tempfile
from pathlib import Path

try:
    from spark_utils import build_spark_session
except ModuleNotFoundError:
    from spark_jobs.spark_utils import build_spark_session


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_USER_PROFILE = PROJECT_ROOT / "data" / "features" / "user_profile.csv"
DEFAULT_MOVIE_PROFILE = PROJECT_ROOT / "data" / "features" / "movie_profile.csv"
DEFAULT_MERGED_RECALL = PROJECT_ROOT / "data" / "recall" / "merged_recall_candidates.csv"
DEFAULT_TRAIN_RATINGS = PROJECT_ROOT / "data" / "processed" / "train_ratings.csv"
DEFAULT_TEST_RATINGS = PROJECT_ROOT / "data" / "processed" / "test_ratings.csv"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "rank"

RECALL_COLUMNS = (
    "als_score",
    "itemcf_score",
    "embedding_score",
    "lightgcn_score",
    "content_score",
    "hot_score",
    "kg_score",
    "is_als_recall",
    "is_itemcf_recall",
    "is_embedding_recall",
    "is_lightgcn_recall",
    "is_content_recall",
    "is_hot_recall",
    "is_kg_recall",
    "recall_source_count",
    "merged_recall_score",
)

FEATURE_COLUMNS = [
    "user_rating_count",
    "user_avg_rating",
    "user_rating_std",
    "user_min_rating",
    "user_max_rating",
    "active_level_code",
    "movie_avg_rating",
    "movie_rating_count",
    "movie_rating_std",
    "movie_popularity",
    "movie_year",
    "movie_decade_code",
    "genre_count",
    "tag_count",
    "genre_match_score",
    "decade_match_score",
    "user_movie_score_gap",
    "als_score",
    "itemcf_score",
    "embedding_score",
    "lightgcn_score",
    "content_score",
    "hot_score",
    "kg_score",
    "is_als_recall",
    "is_itemcf_recall",
    "is_embedding_recall",
    "is_lightgcn_recall",
    "is_content_recall",
    "is_hot_recall",
    "is_kg_recall",
    "recall_source_count",
    "merged_recall_score",
]

OUTPUT_COLUMNS = ["userId", "movieId", "label", *FEATURE_COLUMNS]

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export XGBoost ranking features with Spark.")
    parser.add_argument("--user-profile", default=str(DEFAULT_USER_PROFILE), help="User profile CSV.")
    parser.add_argument("--movie-profile", default=str(DEFAULT_MOVIE_PROFILE), help="Movie profile CSV.")
    parser.add_argument("--merged-recall", default=str(DEFAULT_MERGED_RECALL), help="Merged recall CSV.")
    parser.add_argument("--train-ratings", default=str(DEFAULT_TRAIN_RATINGS), help="Train ratings CSV.")
    parser.add_argument("--test-ratings", default=str(DEFAULT_TEST_RATINGS), help="Test ratings CSV.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Ranking feature output directory.")
    parser.add_argument(
        "--negative-ratio",
        type=float,
        default=3.0,
        help="Maximum negative samples as a multiple of positive samples.",
    )
    return parser.parse_args()


def require_pyspark():
    try:
        from pyspark.sql import SparkSession
        from pyspark.sql import functions as F
        from pyspark.sql import types as T
    except ImportError as exc:
        raise RuntimeError(
            "pyspark is not installed. Install dependencies with `pip install -r requirements.txt` "
            "or run `pip install pyspark` before executing spark_jobs/spark_feature_export.py."
        ) from exc
    return SparkSession, F, T


def create_spark_session(app_name: str = "MovieRecSparkFeatureExport"):
    SparkSession, _, _ = require_pyspark()
    try:
        return build_spark_session(
            SparkSession,
            app_name,
            default_shuffle_partitions=64,
        )
    except Exception as exc:
        raise RuntimeError(
            "Failed to start SparkSession. Please check that Java is installed and JAVA_HOME is set. "
            "On Windows, make sure `java -version` works in this shell. "
            f"Original error: {exc}"
        ) from exc


def write_single_csv(df, output_path: Path) -> None:
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        if output_path.is_dir():
            shutil.rmtree(output_path)
        else:
            output_path.unlink()

    tmp_dir = Path(tempfile.mkdtemp(prefix=f"{output_path.stem}_", dir=str(output_path.parent)))
    try:
        df.coalesce(1).write.mode("overwrite").option("header", True).csv(str(tmp_dir))
        part_files = sorted(tmp_dir.glob("part-*.csv"))
        if not part_files:
            raise RuntimeError(f"Spark did not produce a CSV part file for {output_path}")
        shutil.move(str(part_files[0]), str(output_path))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _require_files(*paths: Path) -> None:
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing required input files: {missing}")


def _read_header(path: Path) -> set[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        return set(next(reader, []))


def _require_columns(path: Path, required: set[str]) -> None:
    columns = _read_header(path)
    missing = sorted(required - columns)
    if missing:
        raise ValueError(f"{path} is missing required columns: {missing}")


def _pipe_array_expr(column_name: str) -> str:
    return (
        "filter("
        f"transform(split(lower(coalesce({column_name}, '')), '\\\\|'), x -> trim(x)), "
        "x -> x <> '' and x <> '(no genres listed)'"
        ")"
    )


def _read_user_profile(spark, path: Path):
    _, F, T = require_pyspark()
    schema = T.StructType(
        [
            T.StructField("userId", T.StringType(), True),
            T.StructField("user_rating_count", T.StringType(), True),
            T.StructField("user_avg_rating", T.StringType(), True),
            T.StructField("user_rating_std", T.StringType(), True),
            T.StructField("user_min_rating", T.StringType(), True),
            T.StructField("user_max_rating", T.StringType(), True),
            T.StructField("favorite_genres", T.StringType(), True),
            T.StructField("favorite_decades", T.StringType(), True),
            T.StructField("active_level", T.StringType(), True),
            T.StructField("high_rating_movie_ids", T.StringType(), True),
            T.StructField("recent_movie_ids", T.StringType(), True),
        ]
    )
    return (
        spark.read.option("header", True).schema(schema).csv(str(path))
        .withColumn("userId", F.col("userId").cast("int"))
        .withColumn("user_rating_count", F.col("user_rating_count").cast("double"))
        .withColumn("user_avg_rating", F.col("user_avg_rating").cast("double"))
        .withColumn("user_rating_std", F.col("user_rating_std").cast("double"))
        .withColumn("user_min_rating", F.col("user_min_rating").cast("double"))
        .withColumn("user_max_rating", F.col("user_max_rating").cast("double"))
        .withColumn(
            "active_level_code",
            F.when(F.lower(F.trim(F.col("active_level"))) == "low", F.lit(0.0))
            .when(F.lower(F.trim(F.col("active_level"))) == "medium", F.lit(1.0))
            .when(F.lower(F.trim(F.col("active_level"))) == "high", F.lit(2.0))
            .otherwise(F.lit(-1.0)),
        )
        .withColumn("favorite_genres_array", F.expr(_pipe_array_expr("favorite_genres")))
        .withColumn("favorite_decades_array", F.expr(_pipe_array_expr("favorite_decades")))
        .where(F.col("userId").isNotNull())
        .dropDuplicates(["userId"])
        .select(
            "userId",
            "user_rating_count",
            "user_avg_rating",
            "user_rating_std",
            "user_min_rating",
            "user_max_rating",
            "active_level_code",
            "favorite_genres_array",
            "favorite_decades_array",
        )
    )


def _read_movie_profile(spark, path: Path):
    _, F, T = require_pyspark()
    schema = T.StructType(
        [
            T.StructField("movieId", T.StringType(), True),
            T.StructField("title", T.StringType(), True),
            T.StructField("clean_title", T.StringType(), True),
            T.StructField("year", T.StringType(), True),
            T.StructField("decade", T.StringType(), True),
            T.StructField("genres", T.StringType(), True),
            T.StructField("genre_count", T.StringType(), True),
            T.StructField("movie_avg_rating", T.StringType(), True),
            T.StructField("movie_rating_count", T.StringType(), True),
            T.StructField("movie_rating_std", T.StringType(), True),
            T.StructField("movie_popularity", T.StringType(), True),
            T.StructField("tag_text", T.StringType(), True),
            T.StructField("tag_count", T.StringType(), True),
        ]
    )
    return (
        spark.read.option("header", True).schema(schema).csv(str(path))
        .withColumn("movieId", F.col("movieId").cast("int"))
        .withColumn("movie_year", F.col("year").cast("double"))
        .withColumn("genre_count", F.col("genre_count").cast("double"))
        .withColumn("movie_avg_rating", F.col("movie_avg_rating").cast("double"))
        .withColumn("movie_rating_count", F.col("movie_rating_count").cast("double"))
        .withColumn("movie_rating_std", F.col("movie_rating_std").cast("double"))
        .withColumn("movie_popularity", F.col("movie_popularity").cast("double"))
        .withColumn("tag_count", F.col("tag_count").cast("double"))
        .withColumn("_decade_digits", F.regexp_extract(F.coalesce(F.col("decade"), F.lit("")), r"(\d{4})", 1))
        .withColumn(
            "movie_decade_code",
            F.when(F.col("_decade_digits") != "", F.col("_decade_digits").cast("double"))
            .when(F.col("movie_year").isNotNull() & (F.col("movie_year") > 0), (F.floor(F.col("movie_year") / 10) * 10).cast("double"))
            .otherwise(F.lit(-1.0)),
        )
        .withColumn("movie_genres_array", F.expr(_pipe_array_expr("genres")))
        .withColumn("movie_decade_text", F.lower(F.coalesce(F.col("decade"), F.lit(""))))
        .where(F.col("movieId").isNotNull())
        .dropDuplicates(["movieId"])
        .select(
            "movieId",
            "movie_avg_rating",
            "movie_rating_count",
            "movie_rating_std",
            "movie_popularity",
            "movie_year",
            "movie_decade_code",
            "movie_decade_text",
            "genre_count",
            "tag_count",
            "movie_genres_array",
        )
    )


def _read_recall(spark, path: Path):
    _, F, T = require_pyspark()
    schema = T.StructType(
        [
            T.StructField("userId", T.StringType(), True),
            T.StructField("movieId", T.StringType(), True),
            *[T.StructField(col, T.StringType(), True) for col in RECALL_COLUMNS],
        ]
    )
    df = (
        spark.read.option("header", True).schema(schema).csv(str(path))
        .withColumn("userId", F.col("userId").cast("int"))
        .withColumn("movieId", F.col("movieId").cast("int"))
    )
    for col in RECALL_COLUMNS:
        df = df.withColumn(col, F.col(col).cast("double"))
    return (
        df.where(F.col("userId").isNotNull() & F.col("movieId").isNotNull())
        .fillna(0.0, subset=list(RECALL_COLUMNS))
        .dropDuplicates(["userId", "movieId"])
        .select("userId", "movieId", *RECALL_COLUMNS)
    )


def _read_ratings(spark, path: Path):
    _, F, T = require_pyspark()
    schema = T.StructType(
        [
            T.StructField("userId", T.StringType(), True),
            T.StructField("movieId", T.StringType(), True),
            T.StructField("rating", T.StringType(), True),
            T.StructField("rating_norm", T.StringType(), True),
            T.StructField("timestamp", T.StringType(), True),
        ]
    )
    return (
        spark.read.option("header", True).schema(schema).csv(str(path))
        .withColumn("userId", F.col("userId").cast("int"))
        .withColumn("movieId", F.col("movieId").cast("int"))
        .withColumn("rating", F.col("rating").cast("double"))
        .withColumn("rating_norm", F.col("rating_norm").cast("double"))
        .withColumn("timestamp", F.col("timestamp").cast("long"))
        .where(
            F.col("userId").isNotNull()
            & F.col("movieId").isNotNull()
            & F.col("rating").isNotNull()
            & F.col("timestamp").isNotNull()
        )
        .select("userId", "movieId", "rating", "rating_norm", "timestamp")
    )


def _add_pair_features(df):
    _, F, _ = require_pyspark()
    empty_string_array = F.expr("cast(array() as array<string>)")
    df = (
        df.withColumn(
            "favorite_genres_array",
            F.when(F.col("favorite_genres_array").isNull(), empty_string_array).otherwise(F.col("favorite_genres_array")),
        )
        .withColumn(
            "favorite_decades_array",
            F.when(F.col("favorite_decades_array").isNull(), empty_string_array).otherwise(F.col("favorite_decades_array")),
        )
        .withColumn(
            "movie_genres_array",
            F.when(F.col("movie_genres_array").isNull(), empty_string_array).otherwise(F.col("movie_genres_array")),
        )
        .withColumn("genre_count", F.coalesce(F.col("genre_count"), F.lit(0.0)))
        .withColumn(
            "genre_match_score",
            F.when(
                F.col("genre_count") > 0,
                F.size(F.array_intersect(F.col("favorite_genres_array"), F.col("movie_genres_array"))).cast("double")
                / F.col("genre_count"),
            ).otherwise(F.lit(0.0)),
        )
        .withColumn(
            "decade_match_score",
            F.when(
                F.array_contains(F.col("favorite_decades_array"), F.lower(F.coalesce(F.col("movie_decade_text"), F.lit("")))),
                F.lit(1.0),
            ).otherwise(F.lit(0.0)),
        )
        .withColumn(
            "user_movie_score_gap",
            F.abs(F.coalesce(F.col("user_avg_rating"), F.lit(0.0)) - F.coalesce(F.col("movie_avg_rating"), F.lit(0.0))),
        )
        .withColumn("label", F.coalesce(F.col("label"), F.lit(0)).cast("int"))
    )
    for col in FEATURE_COLUMNS:
        df = df.withColumn(col, F.coalesce(F.col(col), F.lit(0.0)).cast("double"))
    return df.select("userId", "movieId", "label", *FEATURE_COLUMNS)


def _assert_numeric_features(df) -> None:
    _, _, T = require_pyspark()
    non_numeric = []
    for col in FEATURE_COLUMNS:
        dtype = df.schema[col].dataType
        if not isinstance(dtype, T.NumericType):
            non_numeric.append(f"{col}:{dtype}")
    if non_numeric:
        raise ValueError(f"Feature columns must all be numeric. Non-numeric columns: {non_numeric}")


def export_rank_features(
    user_profile_path: str | Path | None = None,
    movie_profile_path: str | Path | None = None,
    merged_recall_path: str | Path | None = None,
    train_ratings_path: str | Path | None = None,
    test_ratings_path: str | Path | None = None,
    output_dir: str | Path | None = None,
    negative_ratio: float = 3.0,
) -> dict:
    _, F, _ = require_pyspark()
    user_file = Path(user_profile_path).resolve() if user_profile_path else DEFAULT_USER_PROFILE
    movie_file = Path(movie_profile_path).resolve() if movie_profile_path else DEFAULT_MOVIE_PROFILE
    recall_file = Path(merged_recall_path).resolve() if merged_recall_path else DEFAULT_MERGED_RECALL
    train_file = Path(train_ratings_path).resolve() if train_ratings_path else DEFAULT_TRAIN_RATINGS
    test_file = Path(test_ratings_path).resolve() if test_ratings_path else DEFAULT_TEST_RATINGS
    output_path = Path(output_dir).resolve() if output_dir else DEFAULT_OUTPUT_DIR
    train_output = output_path / "rank_train.csv"
    candidates_output = output_path / "rank_candidates.csv"
    feature_output = output_path / "rank_feature_columns.json"

    _require_files(user_file, movie_file, recall_file, train_file, test_file)
    _require_columns(user_file, {"userId", "user_rating_count", "user_avg_rating", "active_level"})
    _require_columns(movie_file, {"movieId", "year", "decade", "genres", "movie_avg_rating", "movie_rating_count"})
    _require_columns(recall_file, {"userId", "movieId", *RECALL_COLUMNS})
    _require_columns(train_file, {"userId", "movieId", "rating", "rating_norm", "timestamp"})
    _require_columns(test_file, {"userId", "movieId", "rating", "rating_norm", "timestamp"})

    logger.info("User profile input: %s", user_file)
    logger.info("Movie profile input: %s", movie_file)
    logger.info("Merged recall input: %s", recall_file)
    logger.info("Train ratings input: %s", train_file)
    logger.info("Test ratings input: %s", test_file)
    logger.info("Output directory: %s", output_path)
    logger.info("Negative ratio: %.2f", negative_ratio)

    spark = create_spark_session()
    try:
        users = _read_user_profile(spark, user_file).cache()
        movies = _read_movie_profile(spark, movie_file).cache()
        recall = _read_recall(spark, recall_file).cache()
        train_ratings = _read_ratings(spark, train_file).cache()
        test_ratings = _read_ratings(spark, test_file).cache()

        user_rows = users.count()
        movie_rows = movies.count()
        recall_rows = recall.count()
        train_rating_rows = train_ratings.count()
        test_rating_rows = test_ratings.count()

        positives = (
            train_ratings.where(F.col("rating") >= 4.0)
            .select("userId", "movieId")
            .withColumn("label", F.lit(1))
        )
        negatives = (
            train_ratings.where(F.col("rating") <= 3.0)
            .select("userId", "movieId")
            .withColumn("label", F.lit(0))
        )
        positive_train_samples = positives.count()
        negative_before_sample = negatives.count()
        if positive_train_samples <= 0:
            raise ValueError("No positive training samples found. Cannot train rank model.")
        max_negative_samples = int(positive_train_samples * negative_ratio)
        if negative_before_sample > max_negative_samples:
            negatives = negatives.orderBy(F.rand(seed=42)).limit(max_negative_samples)
        negative_train_samples = negatives.count()

        train_base = positives.unionByName(negatives)
        train_features = _add_pair_features(
            train_base.join(users, on="userId", how="left")
            .join(movies, on="movieId", how="left")
            .join(recall, on=["userId", "movieId"], how="left")
        ).cache()

        test_positive_labels = (
            test_ratings.where(F.col("rating") >= 4.0)
            .select("userId", "movieId")
            .dropDuplicates()
            .withColumn("label", F.lit(1))
        )
        candidate_features = _add_pair_features(
            recall.join(users, on="userId", how="left")
            .join(movies, on="movieId", how="left")
            .join(test_positive_labels, on=["userId", "movieId"], how="left")
        ).cache()

        _assert_numeric_features(train_features)
        _assert_numeric_features(candidate_features)

        rank_train_rows = train_features.count()
        rank_candidate_rows = candidate_features.count()
        candidate_positive_labels = candidate_features.where(F.col("label") == 1).count()
        candidate_negative_labels = candidate_features.where(F.col("label") == 0).count()

        if train_features.where(~F.col("label").isin(0, 1)).count():
            raise ValueError("Quality check failed: rank_train label contains values outside {0,1}.")
        if candidate_features.where(~F.col("label").isin(0, 1)).count():
            raise ValueError("Quality check failed: rank_candidates label contains values outside {0,1}.")
        if positive_train_samples <= 0:
            raise ValueError("Quality check failed: positive train samples must be greater than 0.")
        if rank_candidate_rows < int(recall_rows * 0.95) or rank_candidate_rows > int(recall_rows * 1.05) + 1:
            raise ValueError(
                "Quality check failed: rank_candidates rows are not close to merged recall rows "
                f"({rank_candidate_rows} vs {recall_rows})."
            )

        write_single_csv(train_features.select(*OUTPUT_COLUMNS), train_output)
        write_single_csv(candidate_features.select(*OUTPUT_COLUMNS), candidates_output)
        output_path.mkdir(parents=True, exist_ok=True)
        feature_output.write_text(json.dumps(FEATURE_COLUMNS, ensure_ascii=False, indent=2), encoding="utf-8")

        for path in (train_output, candidates_output, feature_output):
            if not path.exists():
                raise RuntimeError(f"Expected output was not written: {path}")

        summary = {
            "user_profile_rows": user_rows,
            "movie_profile_rows": movie_rows,
            "merged_recall_rows": recall_rows,
            "train_rating_rows": train_rating_rows,
            "test_rating_rows": test_rating_rows,
            "rank_train_rows": rank_train_rows,
            "rank_candidates_rows": rank_candidate_rows,
            "positive_train_samples": positive_train_samples,
            "negative_train_samples": negative_train_samples,
            "negative_samples_before_sampling": negative_before_sample,
            "candidate_positive_labels": candidate_positive_labels,
            "candidate_negative_labels": candidate_negative_labels,
            "feature_count": len(FEATURE_COLUMNS),
            "feature_columns": FEATURE_COLUMNS,
            "rank_train_path": str(train_output),
            "rank_candidates_path": str(candidates_output),
            "feature_columns_path": str(feature_output),
        }

        logger.info("user profile rows: %s", user_rows)
        logger.info("movie profile rows: %s", movie_rows)
        logger.info("merged recall rows: %s", recall_rows)
        logger.info("train rating rows: %s", train_rating_rows)
        logger.info("test rating rows: %s", test_rating_rows)
        logger.info("rank_train rows: %s", rank_train_rows)
        logger.info("rank_candidates rows: %s", rank_candidate_rows)
        logger.info("positive train samples: %s", positive_train_samples)
        logger.info("negative train samples: %s", negative_train_samples)
        logger.info("candidate positive labels: %s", candidate_positive_labels)
        logger.info("candidate negative labels: %s", candidate_negative_labels)
        logger.info("feature columns: %s", len(FEATURE_COLUMNS))
        logger.info("rank_train output: %s", train_output)
        logger.info("rank_candidates output: %s", candidates_output)
        logger.info("feature columns output: %s", feature_output)
        logger.info("quality validation result: success")
        return summary
    finally:
        spark.stop()


def main() -> None:
    args = parse_args()
    try:
        export_rank_features(
            args.user_profile,
            args.movie_profile,
            args.merged_recall,
            args.train_ratings,
            args.test_ratings,
            args.output_dir,
            args.negative_ratio,
        )
    except Exception as exc:
        logger.error("%s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
