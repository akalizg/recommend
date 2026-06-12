"""
Spark leave-one-out train/test split job for MovieRec.

This job reads data/processed/ratings_clean.csv and writes side-path offline
outputs for later Spark jobs. It does not modify the online recommendation
path, FastAPI routes, Vue frontend, FAISS index, or XGBoost model.
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
DEFAULT_INPUT = PROJECT_ROOT / "data" / "processed" / "ratings_clean.csv"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "processed"
REQUIRED_COLUMNS = ("userId", "movieId", "rating", "rating_norm", "timestamp")

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create per-user leave-one-out splits with Spark.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Clean ratings CSV input.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory for train/test CSV outputs.")
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
            "or run `pip install pyspark` before executing spark_jobs/spark_train_test_split.py."
        ) from exc

    return SparkSession, Window, F, T


def create_spark_session(app_name: str = "MovieRecSparkTrainTestSplit"):
    SparkSession, _, _, _ = require_pyspark()
    try:
        return build_spark_session(SparkSession, app_name)
    except Exception as exc:
        raise RuntimeError(
            "Failed to start SparkSession. Please check that Java is installed and JAVA_HOME is set. "
            "On Windows, install a compatible JDK and make sure `java -version` works in this shell. "
            f"Original error: {exc}"
        ) from exc


def write_single_csv(df, output_path: Path) -> None:
    """Write a Spark DataFrame to a single CSV file with header."""
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


def _validate_columns(columns: list[str], path: Path) -> None:
    missing = [column for column in REQUIRED_COLUMNS if column not in columns]
    if missing:
        raise ValueError(f"{path} is missing required columns: {missing}")


def split_train_test(input_path: str | Path | None = None, output_dir: str | Path | None = None) -> dict:
    """Run leave-one-out train/test split and return summary metrics."""
    _, Window, F, T = require_pyspark()

    source = Path(input_path).resolve() if input_path else DEFAULT_INPUT
    output_path = Path(output_dir).resolve() if output_dir else DEFAULT_OUTPUT_DIR
    train_output = output_path / "train_ratings.csv"
    test_output = output_path / "test_ratings.csv"

    if not source.exists():
        raise FileNotFoundError(
            f"Input file not found: {source}. Run spark_jobs/spark_preprocess.py first."
        )

    logger.info("Input file: %s", source)
    logger.info("Output directory: %s", output_path)

    spark = create_spark_session()
    try:
        schema = T.StructType(
            [
                T.StructField("userId", T.StringType(), True),
                T.StructField("movieId", T.StringType(), True),
                T.StructField("rating", T.StringType(), True),
                T.StructField("rating_norm", T.StringType(), True),
                T.StructField("timestamp", T.StringType(), True),
            ]
        )
        ratings_raw = spark.read.option("header", True).schema(schema).csv(str(source))
        _validate_columns(ratings_raw.columns, source)

        raw_count = ratings_raw.count()

        ratings = (
            ratings_raw.where(
                F.col("userId").isNotNull()
                & F.col("movieId").isNotNull()
                & F.col("rating").isNotNull()
                & F.col("rating_norm").isNotNull()
                & F.col("timestamp").isNotNull()
            )
            .withColumn("userId", F.col("userId").cast("int"))
            .withColumn("movieId", F.col("movieId").cast("int"))
            .withColumn("rating", F.col("rating").cast("double"))
            .withColumn("rating_norm", F.col("rating_norm").cast("double"))
            .withColumn("timestamp", F.col("timestamp").cast("long"))
            .where(
                F.col("userId").isNotNull()
                & F.col("movieId").isNotNull()
                & F.col("rating").isNotNull()
                & F.col("rating_norm").isNotNull()
                & F.col("timestamp").isNotNull()
            )
            .select(*REQUIRED_COLUMNS)
        )

        user_counts = ratings.groupBy("userId").agg(F.count("*").alias("user_rating_count"))
        valid_users = user_counts.where(F.col("user_rating_count") >= 2).select("userId")
        filtered_users = user_counts.where(F.col("user_rating_count") < 2).count()
        valid_user_count = valid_users.count()

        filtered_ratings = ratings.join(valid_users, on="userId", how="inner")
        filtered_count = filtered_ratings.count()

        window = Window.partitionBy("userId").orderBy(F.col("timestamp").desc(), F.col("movieId").desc())
        ranked = filtered_ratings.withColumn("rn", F.row_number().over(window))
        test = ranked.where(F.col("rn") == 1).select(*REQUIRED_COLUMNS)
        train = ranked.where(F.col("rn") > 1).select(*REQUIRED_COLUMNS)

        train_count = train.count()
        test_count = test.count()
        train_user_count = train.select("userId").distinct().count()
        test_user_count = test.select("userId").distinct().count()
        train_movie_count = train.select("movieId").distinct().count()
        test_movie_count = test.select("movieId").distinct().count()

        overlap_count = (
            train.select("userId", "movieId", "timestamp")
            .intersect(test.select("userId", "movieId", "timestamp"))
            .count()
        )
        duplicate_exists = overlap_count > 0

        test_users_with_multiple = test.groupBy("userId").count().where(F.col("count") > 1).count()
        test_max_one_per_user = test_users_with_multiple == 0

        test_users_missing_from_train = (
            test.select("userId").distinct()
            .join(train.select("userId").distinct(), on="userId", how="left_anti")
            .count()
        )

        train_columns_ok = set(REQUIRED_COLUMNS).issubset(set(train.columns))
        test_columns_ok = set(REQUIRED_COLUMNS).issubset(set(test.columns))
        row_count_ok = train_count + test_count == filtered_count

        if duplicate_exists:
            raise ValueError("Quality check failed: train and test contain duplicate userId+movieId+timestamp rows.")
        if not test_max_one_per_user:
            raise ValueError("Quality check failed: test set contains more than one row for at least one user.")
        if test_users_missing_from_train:
            raise ValueError("Quality check failed: some test users are missing from train set.")
        if not train_columns_ok or not test_columns_ok:
            raise ValueError("Quality check failed: train/test outputs are missing required columns.")
        if not row_count_ok:
            raise ValueError(
                "Quality check failed: train rows + test rows does not equal filtered rating rows."
            )

        write_single_csv(train, train_output)
        write_single_csv(test, test_output)

        outputs_written = train_output.exists() and test_output.exists()
        if not outputs_written:
            raise RuntimeError("Quality check failed: train/test output files were not written.")

        summary = {
            "input": str(source),
            "output_dir": str(output_path),
            "raw_count": raw_count,
            "valid_user_count": valid_user_count,
            "filtered_user_count": filtered_users,
            "filtered_rating_count": filtered_count,
            "train_count": train_count,
            "test_count": test_count,
            "train_user_count": train_user_count,
            "test_user_count": test_user_count,
            "train_movie_count": train_movie_count,
            "test_movie_count": test_movie_count,
            "duplicate_exists": duplicate_exists,
            "test_max_one_per_user": test_max_one_per_user,
            "test_users_missing_from_train": test_users_missing_from_train,
            "row_count_ok": row_count_ok,
            "outputs_written": outputs_written,
        }

        logger.info("raw rating rows: %s", raw_count)
        logger.info("valid users: %s", valid_user_count)
        logger.info("filtered low-activity users: %s", filtered_users)
        logger.info("filtered rating rows: %s", filtered_count)
        logger.info("train rows: %s", train_count)
        logger.info("test rows: %s", test_count)
        logger.info("train users: %s", train_user_count)
        logger.info("test users: %s", test_user_count)
        logger.info("train movies: %s", train_movie_count)
        logger.info("test movies: %s", test_movie_count)
        logger.info("train/test duplicate userId+movieId+timestamp exists: %s", duplicate_exists)
        logger.info("test has at most one rating per user: %s", test_max_one_per_user)
        logger.info("all test users exist in train: %s", test_users_missing_from_train == 0)
        logger.info("train rows + test rows = filtered rows: %s", row_count_ok)
        logger.info("wrote train_ratings.csv: %s", train_output.exists())
        logger.info("wrote test_ratings.csv: %s", test_output.exists())

        return summary
    finally:
        spark.stop()


def main() -> None:
    args = parse_args()
    try:
        split_train_test(args.input, args.output_dir)
    except Exception as exc:
        logger.error("%s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
