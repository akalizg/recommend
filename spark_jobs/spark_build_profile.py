"""
Spark profile building job for MovieRec.

Builds user_profile.csv and movie_profile.csv from offline processed data.
User profiles are built only from train_ratings.csv to avoid test leakage.
"""
from __future__ import annotations

import argparse
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
DEFAULT_TRAIN = PROJECT_ROOT / "data" / "processed" / "train_ratings.csv"
DEFAULT_MOVIES = PROJECT_ROOT / "data" / "processed" / "movies_clean.csv"
DEFAULT_TAGS = PROJECT_ROOT / "data" / "processed" / "movie_tags.csv"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "features"
DEFAULT_MAX_TAGS_PER_MOVIE = 50
USER_PROFILE_COLUMNS = (
    "userId",
    "user_rating_count",
    "user_avg_rating",
    "user_rating_std",
    "user_min_rating",
    "user_max_rating",
    "favorite_genres",
    "favorite_decades",
    "active_level",
    "high_rating_movie_ids",
    "recent_movie_ids",
)
MOVIE_PROFILE_COLUMNS = (
    "movieId",
    "title",
    "clean_title",
    "year",
    "decade",
    "genres",
    "genre_count",
    "movie_avg_rating",
    "movie_rating_count",
    "movie_rating_std",
    "movie_popularity",
    "tag_text",
    "tag_count",
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build MovieRec user/movie profiles with Spark.")
    parser.add_argument("--train", default=str(DEFAULT_TRAIN), help="Train ratings CSV.")
    parser.add_argument("--movies", default=str(DEFAULT_MOVIES), help="Clean movies CSV.")
    parser.add_argument("--tags", default=str(DEFAULT_TAGS), help="Movie tags CSV.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Profile output directory.")
    parser.add_argument("--top-n", type=int, default=20, help="Top-N movie IDs stored in user profile lists.")
    parser.add_argument("--max-tags-per-movie", type=int, default=DEFAULT_MAX_TAGS_PER_MOVIE, help="Maximum tag tokens kept in each movie profile.")
    return parser.parse_args()


def require_pyspark():
    try:
        from pyspark.sql import SparkSession
        from pyspark.sql import Window
        from pyspark.sql import functions as F
        from pyspark.sql import types as T
    except ImportError as exc:
        raise RuntimeError(
            "pyspark is not installed. Install dependencies with `pip install -r requirements.txt` "
            "or run `pip install pyspark` before executing spark_jobs/spark_build_profile.py."
        ) from exc
    return SparkSession, Window, F, T


def create_spark_session(app_name: str = "MovieRecSparkBuildProfile"):
    SparkSession, _, _, _ = require_pyspark()
    try:
        return build_spark_session(
            SparkSession,
            app_name,
            default_driver_memory="6g",
            default_executor_memory="6g",
            default_shuffle_partitions=64,
        )
    except Exception as exc:
        raise RuntimeError(
            "Failed to start SparkSession. Please check that Java is installed and JAVA_HOME is set. "
            "On Windows, install a compatible JDK and make sure `java -version` works in this shell. "
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


def _ordered_list_agg(F, value_col: str, output_col: str):
    return F.expr(
        f"array_join(transform(sort_array(collect_list(named_struct('rn', rn, 'value', {value_col}))), x -> x.value), '|')"
    ).alias(output_col)


def _top_value_profile(df, partition_col: str, value_col: str, count_col: str, output_col: str, limit: int):
    _, Window, F, _ = require_pyspark()
    window = Window.partitionBy(partition_col).orderBy(F.col(count_col).desc(), F.col(value_col).asc())
    ranked = df.withColumn("rn", F.row_number().over(window)).where(F.col("rn") <= limit)
    return ranked.groupBy(partition_col).agg(_ordered_list_agg(F, value_col, output_col))


def build_profiles(
    train_path: str | Path | None = None,
    movies_path: str | Path | None = None,
    tags_path: str | Path | None = None,
    output_dir: str | Path | None = None,
    top_n: int = 20,
    max_tags_per_movie: int = DEFAULT_MAX_TAGS_PER_MOVIE,
) -> dict:
    """Build user and movie profile CSV files and return summary metrics."""
    _, Window, F, T = require_pyspark()
    train_file = Path(train_path).resolve() if train_path else DEFAULT_TRAIN
    movies_file = Path(movies_path).resolve() if movies_path else DEFAULT_MOVIES
    tags_file = Path(tags_path).resolve() if tags_path else DEFAULT_TAGS
    output_path = Path(output_dir).resolve() if output_dir else DEFAULT_OUTPUT_DIR
    user_output = output_path / "user_profile.csv"
    movie_output = output_path / "movie_profile.csv"
    _require_files(train_file, movies_file, tags_file)
    if max_tags_per_movie < 1:
        raise ValueError("max_tags_per_movie must be positive.")

    logger.info("Train ratings input: %s", train_file)
    logger.info("Movies input: %s", movies_file)
    logger.info("Tags input: %s", tags_file)
    logger.info("Output directory: %s", output_path)

    spark = create_spark_session()
    try:
        train_schema = T.StructType(
            [
                T.StructField("userId", T.StringType(), True),
                T.StructField("movieId", T.StringType(), True),
                T.StructField("rating", T.StringType(), True),
                T.StructField("rating_norm", T.StringType(), True),
                T.StructField("timestamp", T.StringType(), True),
            ]
        )
        movie_schema = T.StructType(
            [
                T.StructField("movieId", T.StringType(), True),
                T.StructField("title", T.StringType(), True),
                T.StructField("clean_title", T.StringType(), True),
                T.StructField("year", T.StringType(), True),
                T.StructField("genres", T.StringType(), True),
                T.StructField("genre_count", T.StringType(), True),
            ]
        )
        tag_schema = T.StructType(
            [
                T.StructField("movieId", T.StringType(), True),
                T.StructField("tag", T.StringType(), True),
                T.StructField("tag_type", T.StringType(), True),
            ]
        )

        train = (
            spark.read.option("header", True).schema(train_schema).csv(str(train_file))
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
        movies = (
            spark.read.option("header", True).schema(movie_schema).csv(str(movies_file))
            .withColumn("movieId", F.col("movieId").cast("int"))
            .withColumn("year", F.col("year").cast("int"))
            .withColumn("genre_count", F.col("genre_count").cast("int"))
            .where(F.col("movieId").isNotNull())
            .withColumn(
                "genres_array",
                F.when(F.col("genres").isNull() | (F.trim(F.col("genres")) == ""), F.from_json(F.lit("[]"), "array<string>"))
                .otherwise(F.split(F.col("genres"), r"\|")),
            )
            .withColumn(
                "decade",
                F.when(F.col("year").isNotNull(), F.concat((F.floor(F.col("year") / 10) * 10).cast("int").cast("string"), F.lit("s"))).otherwise(F.lit("")),
            )
        )
        tags = (
            spark.read.option("header", True).schema(tag_schema).csv(str(tags_file))
            .withColumn("movieId", F.col("movieId").cast("int"))
            .withColumn("tag", F.lower(F.trim(F.col("tag"))))
            .where(F.col("movieId").isNotNull() & F.col("tag").isNotNull() & (F.col("tag") != ""))
            .select("movieId", "tag", "tag_type")
            .dropDuplicates(["movieId", "tag", "tag_type"])
        )

        train_rows = train.count()
        movies_rows = movies.count()
        tags_rows = tags.count()
        valid_users = train.select("userId").distinct().count()
        valid_movies = train.select("movieId").distinct().count()

        user_stats = (
            train.groupBy("userId")
            .agg(
                F.count("*").alias("user_rating_count"),
                F.avg("rating").alias("user_avg_rating"),
                F.stddev_samp("rating").alias("user_rating_std"),
                F.min("rating").alias("user_min_rating"),
                F.max("rating").alias("user_max_rating"),
            )
            .fillna({"user_rating_std": 0.0})
            .withColumn(
                "active_level",
                F.when(F.col("user_rating_count") < 20, F.lit("low"))
                .when(F.col("user_rating_count") < 80, F.lit("medium"))
                .otherwise(F.lit("high")),
            )
        )

        train_with_movie = train.join(movies.select("movieId", "genres_array", "decade"), on="movieId", how="left")
        high_ratings = train_with_movie.where(F.col("rating") >= 4.0)

        genre_counts = (
            high_ratings.select("userId", F.explode_outer("genres_array").alias("genre"))
            .where(F.col("genre").isNotNull() & (F.col("genre") != ""))
            .groupBy("userId", "genre")
            .count()
            .withColumnRenamed("count", "genre_hits")
        )
        favorite_genres = _top_value_profile(genre_counts, "userId", "genre", "genre_hits", "favorite_genres", 5)

        decade_counts = (
            high_ratings.where(F.col("decade") != "")
            .groupBy("userId", "decade")
            .count()
            .withColumnRenamed("count", "decade_hits")
        )
        favorite_decades = _top_value_profile(decade_counts, "userId", "decade", "decade_hits", "favorite_decades", 5)

        high_movie_window = Window.partitionBy("userId").orderBy(
            F.col("rating").desc(), F.col("timestamp").desc(), F.col("movieId").desc()
        )
        high_movie_ids = (
            train.where(F.col("rating") >= 4.0)
            .withColumn("rn", F.row_number().over(high_movie_window))
            .where(F.col("rn") <= top_n)
            .withColumn("movie_value", F.col("movieId").cast("string"))
            .groupBy("userId")
            .agg(_ordered_list_agg(F, "movie_value", "high_rating_movie_ids"))
        )

        recent_window = Window.partitionBy("userId").orderBy(F.col("timestamp").desc(), F.col("movieId").desc())
        recent_movie_ids = (
            train.withColumn("rn", F.row_number().over(recent_window))
            .where(F.col("rn") <= top_n)
            .withColumn("movie_value", F.col("movieId").cast("string"))
            .groupBy("userId")
            .agg(_ordered_list_agg(F, "movie_value", "recent_movie_ids"))
        )

        user_profile = (
            user_stats.join(favorite_genres, on="userId", how="left")
            .join(favorite_decades, on="userId", how="left")
            .join(high_movie_ids, on="userId", how="left")
            .join(recent_movie_ids, on="userId", how="left")
            .fillna(
                {
                    "favorite_genres": "",
                    "favorite_decades": "",
                    "high_rating_movie_ids": "",
                    "recent_movie_ids": "",
                }
            )
            .select(*USER_PROFILE_COLUMNS)
        )

        movie_stats = (
            train.groupBy("movieId")
            .agg(
                F.avg("rating").alias("movie_avg_rating"),
                F.count("*").alias("movie_rating_count"),
                F.stddev_samp("rating").alias("movie_rating_std"),
            )
            .fillna({"movie_rating_std": 0.0})
            .withColumn("movie_popularity", F.col("movie_avg_rating") * F.log(F.col("movie_rating_count") + F.lit(1.0)))
        )
        tag_window = Window.partitionBy("movieId").orderBy(
            F.when(F.col("tag_type") == "recipe_tag", F.lit(0))
            .when(F.col("tag_type") == "genre", F.lit(1))
            .otherwise(F.lit(2)),
            F.col("tag").asc(),
        )
        limited_tags = (
            tags.withColumn("tag_rn", F.row_number().over(tag_window))
            .where(F.col("tag_rn") <= max_tags_per_movie)
            .drop("tag_rn")
        )
        tag_profile = limited_tags.groupBy("movieId").agg(
            F.concat_ws("|", F.sort_array(F.collect_set("tag"))).alias("tag_text"),
            F.countDistinct("tag").alias("tag_count"),
        )
        movie_profile = (
            movies.join(movie_stats, on="movieId", how="left")
            .join(tag_profile, on="movieId", how="left")
            .fillna(
                {
                    "movie_avg_rating": 0.0,
                    "movie_rating_count": 0,
                    "movie_rating_std": 0.0,
                    "movie_popularity": 0.0,
                    "tag_text": "",
                    "tag_count": 0,
                    "genres": "",
                    "genre_count": 0,
                    "decade": "",
                }
            )
            .select(*MOVIE_PROFILE_COLUMNS)
        )

        user_profile_rows = user_profile.count()
        movie_profile_rows = movie_profile.count()
        avg_user_rating_count = user_profile.agg(F.avg("user_rating_count")).first()[0]
        avg_movie_rating_count = movie_profile.agg(F.avg("movie_rating_count")).first()[0]
        top_genres = (
            tags.where(F.col("tag_type") == "genre")
            .groupBy("tag")
            .count()
            .orderBy(F.col("count").desc(), F.col("tag").asc())
            .limit(10)
            .collect()
        )
        top_genres = [{"tag": row["tag"], "count": row["count"]} for row in top_genres]

        write_single_csv(user_profile, user_output)
        write_single_csv(movie_profile, movie_output)

        if not user_output.exists():
            raise RuntimeError(f"user_profile.csv was not written: {user_output}")
        if not movie_output.exists():
            raise RuntimeError(f"movie_profile.csv was not written: {movie_output}")
        if user_profile.where(F.col("userId").isNull()).count() > 0:
            raise ValueError("Quality check failed: user_profile contains null userId.")
        if movie_profile.where(F.col("movieId").isNull()).count() > 0:
            raise ValueError("Quality check failed: movie_profile contains null movieId.")
        if user_profile_rows != valid_users:
            raise ValueError(
                f"Quality check failed: user_profile rows {user_profile_rows} != valid users {valid_users}."
            )
        if movie_profile_rows < movies_rows:
            raise ValueError(
                f"Quality check failed: movie_profile rows {movie_profile_rows} < movies_clean rows {movies_rows}."
            )

        summary = {
            "train_rows": train_rows,
            "movies_rows": movies_rows,
            "tags_rows": tags_rows,
            "max_tags_per_movie": max_tags_per_movie,
            "user_profile_rows": user_profile_rows,
            "movie_profile_rows": movie_profile_rows,
            "valid_users": valid_users,
            "valid_movies": valid_movies,
            "average_user_rating_count": float(avg_user_rating_count or 0.0),
            "average_movie_rating_count": float(avg_movie_rating_count or 0.0),
            "top_genres": top_genres,
            "user_profile_path": str(user_output),
            "movie_profile_path": str(movie_output),
        }

        logger.info("train ratings rows: %s", train_rows)
        logger.info("movies rows: %s", movies_rows)
        logger.info("tags rows: %s", tags_rows)
        logger.info("max tags per movie profile: %s", max_tags_per_movie)
        logger.info("user profile rows: %s", user_profile_rows)
        logger.info("movie profile rows: %s", movie_profile_rows)
        logger.info("valid users: %s", valid_users)
        logger.info("valid movies: %s", valid_movies)
        logger.info("average user rating count: %.4f", summary["average_user_rating_count"])
        logger.info("average movie rating count: %.4f", summary["average_movie_rating_count"])
        logger.info("top genres: %s", top_genres)
        logger.info("output paths: %s, %s", user_output, movie_output)
        logger.info("quality validation result: success")
        return summary
    finally:
        spark.stop()


def main() -> None:
    args = parse_args()
    try:
        build_profiles(args.train, args.movies, args.tags, args.output_dir, args.top_n, args.max_tags_per_movie)
    except Exception as exc:
        logger.error("%s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
