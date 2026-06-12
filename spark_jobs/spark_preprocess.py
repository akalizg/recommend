"""
Spark offline preprocessing job for MovieRec.

This job is a side-path offline output. It does not modify the current
pandas FeaturePipeline, FastAPI routes, Vue frontend, FAISS index, or models.
"""
from __future__ import annotations

import argparse
import logging
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT_DIR = PROJECT_ROOT / "data" / "ml-latest-small"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "processed"
REQUIRED_FILES = ("ratings.csv", "movies.csv", "tags.csv", "links.csv")

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preprocess MovieLens data with Spark.")
    parser.add_argument("--input-dir", default=str(DEFAULT_INPUT_DIR), help="Raw MovieLens data directory.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Processed data output directory.")
    return parser.parse_args()


def _candidate_data_dirs(explicit_dir: Path) -> Iterable[Path]:
    yield explicit_dir
    yield DEFAULT_INPUT_DIR
    yield PROJECT_ROOT
    yield Path.cwd()
    yield PROJECT_ROOT / "data"

    data_root = PROJECT_ROOT / "data"
    if data_root.exists():
        for child in data_root.iterdir():
            if child.is_dir():
                yield child


def detect_input_dir(input_dir: str | Path) -> Path:
    """Find the directory containing MovieLens ratings/movies/tags/links CSV files."""
    seen: set[Path] = set()
    for candidate in _candidate_data_dirs(Path(input_dir)):
        candidate = candidate.resolve()
        if candidate in seen:
            continue
        seen.add(candidate)
        if all((candidate / file_name).exists() for file_name in REQUIRED_FILES):
            return candidate

    checked = ", ".join(str(path) for path in seen)
    raise FileNotFoundError(
        "Could not find MovieLens CSV files ratings.csv, movies.csv, tags.csv, links.csv. "
        f"Checked: {checked}"
    )


def require_pyspark():
    try:
        from pyspark.sql import SparkSession
        from pyspark.sql import functions as F
        from pyspark.sql import types as T
    except ImportError as exc:
        raise RuntimeError(
            "pyspark is not installed. Install dependencies with `pip install -r requirements.txt` "
            "or run `pip install pyspark` before executing spark_jobs/spark_preprocess.py."
        ) from exc

    return SparkSession, F, T


def create_spark_session(app_name: str = "MovieRecSparkPreprocess"):
    SparkSession, _, _ = require_pyspark()
    try:
        return (
            SparkSession.builder.appName(app_name)
            .master("local[*]")
            .config("spark.sql.session.timeZone", "UTC")
            .config("spark.ui.showConsoleProgress", "false")
            .getOrCreate()
        )
    except Exception as exc:
        raise RuntimeError(
            "Failed to start SparkSession. Please check that Java is installed and JAVA_HOME is set. "
            "On Windows, install a compatible JDK and make sure `java -version` works in this shell. "
            f"Original error: {exc}"
        ) from exc


def write_single_csv(df, output_path: Path) -> None:
    """
    Write a Spark DataFrame as one CSV file at output_path.

    Spark writes CSV datasets as directories. This helper writes to a temporary
    directory, moves the single part file to the requested *.csv path, and
    removes temporary metadata files.
    """
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


def preprocess(input_dir: str | Path | None = None, output_dir: str | Path | None = None) -> dict:
    """Run Spark preprocessing and return summary metrics."""
    _, F, T = require_pyspark()

    requested_input = Path(input_dir) if input_dir else DEFAULT_INPUT_DIR
    detected_input = detect_input_dir(requested_input)
    output_path = Path(output_dir).resolve() if output_dir else DEFAULT_OUTPUT_DIR
    output_path.mkdir(parents=True, exist_ok=True)

    logger.info("Input directory: %s", detected_input)
    if detected_input != requested_input.resolve():
        logger.info("Requested input directory was %s; auto-detected %s", requested_input.resolve(), detected_input)
    logger.info("Output directory: %s", output_path)

    spark = create_spark_session()
    try:
        ratings_schema = T.StructType(
            [
                T.StructField("userId", T.StringType(), True),
                T.StructField("movieId", T.StringType(), True),
                T.StructField("rating", T.StringType(), True),
                T.StructField("timestamp", T.StringType(), True),
            ]
        )
        movies_schema = T.StructType(
            [
                T.StructField("movieId", T.StringType(), True),
                T.StructField("title", T.StringType(), True),
                T.StructField("genres", T.StringType(), True),
            ]
        )
        tags_schema = T.StructType(
            [
                T.StructField("userId", T.StringType(), True),
                T.StructField("movieId", T.StringType(), True),
                T.StructField("tag", T.StringType(), True),
                T.StructField("timestamp", T.StringType(), True),
            ]
        )

        ratings_raw = spark.read.option("header", True).schema(ratings_schema).csv(str(detected_input / "ratings.csv"))
        movies_raw = spark.read.option("header", True).schema(movies_schema).csv(str(detected_input / "movies.csv"))
        tags_raw = spark.read.option("header", True).schema(tags_schema).csv(str(detected_input / "tags.csv"))

        ratings_raw_count = ratings_raw.count()
        movies_raw_count = movies_raw.count()

        ratings_clean = (
            ratings_raw.dropDuplicates(["userId", "movieId", "rating", "timestamp"])
            .where(F.col("userId").isNotNull() & F.col("movieId").isNotNull() & F.col("rating").isNotNull())
            .withColumn("userId", F.col("userId").cast("int"))
            .withColumn("movieId", F.col("movieId").cast("int"))
            .withColumn("rating", F.col("rating").cast("double"))
            .withColumn("timestamp", F.col("timestamp").cast("long"))
            .where(F.col("userId").isNotNull() & F.col("movieId").isNotNull() & F.col("rating").isNotNull())
            .withColumn("rating_norm", F.col("rating") / F.lit(5.0))
            .select("userId", "movieId", "rating", "rating_norm", "timestamp")
        )

        year_expr = F.regexp_extract(F.col("title"), r"\((\d{4})\)\s*$", 1)
        clean_title_expr = F.trim(F.regexp_replace(F.col("title"), r"\s*\(\d{4}\)\s*$", ""))
        empty_genres = F.from_json(F.lit("[]"), "array<string>")
        genre_array_expr = F.when(
            F.col("genres").isNull() | (F.col("genres") == "") | (F.col("genres") == "(no genres listed)"),
            empty_genres,
        ).otherwise(F.split(F.col("genres"), r"\|"))

        movies_clean = (
            movies_raw.dropDuplicates(["movieId"])
            .where(F.col("movieId").isNotNull() & F.col("title").isNotNull())
            .withColumn("movieId", F.col("movieId").cast("int"))
            .where(F.col("movieId").isNotNull())
            .withColumn("year", F.when(year_expr != "", year_expr.cast("int")).otherwise(F.lit(None).cast("int")))
            .withColumn("clean_title", clean_title_expr)
            .withColumn("genres", genre_array_expr)
            .withColumn("genre_count", F.size(F.col("genres")))
            .select("movieId", "title", "clean_title", "year", "genres", "genre_count")
        )

        genre_tags = (
            movies_clean.select("movieId", F.explode_outer("genres").alias("tag"))
            .where(F.col("tag").isNotNull() & (F.trim(F.col("tag")) != ""))
            .withColumn("tag", F.lower(F.trim(F.col("tag"))))
            .withColumn("tag_type", F.lit("genre"))
        )

        user_tags = (
            tags_raw.where(F.col("movieId").isNotNull() & F.col("tag").isNotNull())
            .withColumn("movieId", F.col("movieId").cast("int"))
            .withColumn("tag", F.lower(F.trim(F.col("tag"))))
            .where(F.col("movieId").isNotNull() & (F.col("tag") != ""))
            .withColumn("tag_type", F.lit("user_tag"))
            .select("movieId", "tag", "tag_type")
        )

        movie_tags = genre_tags.unionByName(user_tags).dropDuplicates(["movieId", "tag", "tag_type"])

        ratings_clean_count = ratings_clean.count()
        movies_clean_count = movies_clean.count()
        movie_tags_count = movie_tags.count()
        rating_stats = ratings_clean.agg(F.min("rating").alias("min_rating"), F.max("rating").alias("max_rating")).first()
        user_count = ratings_clean.select("userId").distinct().count()
        movie_count = movies_clean.select("movieId").distinct().count()

        ratings_output = output_path / "ratings_clean.csv"
        movies_output = output_path / "movies_clean.csv"
        tags_output = output_path / "movie_tags.csv"

        movies_output_df = movies_clean.withColumn("genres", F.concat_ws("|", F.col("genres")))

        write_single_csv(ratings_clean, ratings_output)
        write_single_csv(movies_output_df, movies_output)
        write_single_csv(movie_tags, tags_output)

        files_written = all(path.exists() and path.is_file() for path in [ratings_output, movies_output, tags_output])

        summary = {
            "input_dir": str(detected_input),
            "output_dir": str(output_path),
            "ratings_raw_count": ratings_raw_count,
            "ratings_clean_count": ratings_clean_count,
            "movies_raw_count": movies_raw_count,
            "movies_clean_count": movies_clean_count,
            "movie_tags_count": movie_tags_count,
            "min_rating": None if rating_stats is None else rating_stats["min_rating"],
            "max_rating": None if rating_stats is None else rating_stats["max_rating"],
            "user_count": user_count,
            "movie_count": movie_count,
            "files_written": files_written,
        }

        logger.info("ratings raw rows: %s", ratings_raw_count)
        logger.info("ratings clean rows: %s", ratings_clean_count)
        logger.info("movies raw rows: %s", movies_raw_count)
        logger.info("movies clean rows: %s", movies_clean_count)
        logger.info("movie_tags rows: %s", movie_tags_count)
        logger.info("rating range: %s - %s", summary["min_rating"], summary["max_rating"])
        logger.info("user count: %s", user_count)
        logger.info("movie count: %s", movie_count)
        logger.info("wrote ratings_clean.csv: %s", ratings_output.exists())
        logger.info("wrote movies_clean.csv: %s", movies_output.exists())
        logger.info("wrote movie_tags.csv: %s", tags_output.exists())
        logger.info("all outputs written successfully: %s", files_written)

        return summary
    finally:
        spark.stop()


def main() -> None:
    args = parse_args()
    try:
        preprocess(args.input_dir, args.output_dir)
    except Exception as exc:
        logger.error("%s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
