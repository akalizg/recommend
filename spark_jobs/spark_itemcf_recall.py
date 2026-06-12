"""
Spark ItemCF recall job for MovieRec.

Computes item-item similarity from high-rating co-occurrence in train ratings
and exports user-level ItemCF recall candidates.
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
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "recall" / "itemcf_recall.csv"
REQUIRED_COLUMNS = ("userId", "movieId", "recall_type", "recall_score")

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build ItemCF recall candidates with Spark.")
    parser.add_argument("--train", default=str(DEFAULT_TRAIN), help="Train ratings input.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="ItemCF recall CSV output.")
    parser.add_argument("--top-sim", type=int, default=50, help="Top similar items kept per item.")
    parser.add_argument("--top-n", type=int, default=50, help="Top ItemCF candidates kept per user.")
    parser.add_argument("--min-rating", type=float, default=4.0, help="Minimum rating treated as liked.")
    parser.add_argument(
        "--max-liked-per-user",
        type=int,
        default=100,
        help="Performance guard: keep at most this many liked movies per user when building co-occurrence pairs.",
    )
    return parser.parse_args()


def require_pyspark():
    try:
        from pyspark.sql import SparkSession
        from pyspark.sql import Window
        from pyspark.sql import functions as F
        from pyspark.sql import types as T
    except ImportError as exc:
        raise RuntimeError(
            "pyspark is not installed. Install dependencies with `pip install -r requirements.txt`."
        ) from exc
    return SparkSession, Window, F, T


def create_spark_session(app_name: str = "MovieRecSparkItemCF"):
    SparkSession, _, _, _ = require_pyspark()
    try:
        return build_spark_session(
            SparkSession,
            app_name,
            default_driver_memory="4g",
            default_executor_memory="4g",
            default_shuffle_partitions=64,
            default_parallelism=64,
        )
    except Exception as exc:
        raise RuntimeError(
            "Failed to start SparkSession. Please check Java/JAVA_HOME. "
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


def build_itemcf_recall(
    train_path: str | Path | None = None,
    output_path: str | Path | None = None,
    top_sim: int = 50,
    top_n: int = 50,
    min_rating: float = 4.0,
    max_liked_per_user: int = 100,
) -> dict:
    _, Window, F, T = require_pyspark()
    train_file = Path(train_path).resolve() if train_path else DEFAULT_TRAIN
    output_file = Path(output_path).resolve() if output_path else DEFAULT_OUTPUT
    if not train_file.exists():
        raise FileNotFoundError(f"Train ratings input not found: {train_file}")

    logger.info("Train ratings input: %s", train_file)
    logger.info("Output path: %s", output_file)
    logger.info(
        "Params: top_sim=%s top_n=%s min_rating=%s max_liked_per_user=%s",
        top_sim,
        top_n,
        min_rating,
        max_liked_per_user,
    )

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
        train = (
            spark.read.option("header", True).schema(schema).csv(str(train_file))
            .withColumn("userId", F.col("userId").cast("int"))
            .withColumn("movieId", F.col("movieId").cast("int"))
            .withColumn("rating", F.col("rating").cast("double"))
            .withColumn("timestamp", F.col("timestamp").cast("long"))
            .where(
                F.col("userId").isNotNull()
                & F.col("movieId").isNotNull()
                & F.col("rating").isNotNull()
                & F.col("timestamp").isNotNull()
            )
            .select("userId", "movieId", "rating", "timestamp")
        )
        train_rows = train.count()
        valid_users = train.select("userId").distinct().count()

        liked_window = Window.partitionBy("userId").orderBy(
            F.col("rating").desc(), F.col("timestamp").desc(), F.col("movieId").desc()
        )
        liked = (
            train.where(F.col("rating") >= min_rating)
            .withColumn("rn", F.row_number().over(liked_window))
            .where(F.col("rn") <= max_liked_per_user)
            .select("userId", "movieId")
            .dropDuplicates()
            .cache()
        )
        liked_interactions = liked.count()
        movie_count = liked.select("movieId").distinct().count()

        item_user_counts = liked.groupBy("movieId").agg(F.countDistinct("userId").alias("user_count"))
        a = liked.select("userId", F.col("movieId").alias("movie_i"))
        b = liked.select("userId", F.col("movieId").alias("movie_j"))
        pairs = a.join(b, on="userId").where(F.col("movie_i") != F.col("movie_j"))
        cooc = pairs.groupBy("movie_i", "movie_j").agg(F.countDistinct("userId").alias("common_users"))
        cooc_pair_count = cooc.count()

        item_i_counts = item_user_counts.select(F.col("movieId").alias("movie_i"), F.col("user_count").alias("count_i"))
        item_j_counts = item_user_counts.select(F.col("movieId").alias("movie_j"), F.col("user_count").alias("count_j"))
        sim = (
            cooc.join(item_i_counts, on="movie_i", how="inner")
            .join(item_j_counts, on="movie_j", how="inner")
            .withColumn("sim_score", F.col("common_users") / F.sqrt(F.col("count_i") * F.col("count_j")))
        )
        sim_window = Window.partitionBy("movie_i").orderBy(F.col("sim_score").desc(), F.col("movie_j").asc())
        top_sim_items = (
            sim.withColumn("rn", F.row_number().over(sim_window))
            .where(F.col("rn") <= top_sim)
            .select("movie_i", F.col("movie_j").alias("candidate_movieId"), "sim_score")
        )
        item_similarity_rows = top_sim_items.count()

        liked_for_join = liked.select("userId", F.col("movieId").alias("movie_i"))
        raw_candidates = liked_for_join.join(top_sim_items, on="movie_i", how="inner")
        rated_pairs = train.select("userId", "movieId").dropDuplicates()
        itemcf_scores = (
            raw_candidates.groupBy("userId", F.col("candidate_movieId").alias("movieId"))
            .agg(F.sum("sim_score").alias("recall_score"))
            .join(rated_pairs, on=["userId", "movieId"], how="left_anti")
            .where(F.col("recall_score").isNotNull())
        )
        recall_window = Window.partitionBy("userId").orderBy(F.col("recall_score").desc(), F.col("movieId").asc())
        itemcf_recall = (
            itemcf_scores.withColumn("rn", F.row_number().over(recall_window))
            .where(F.col("rn") <= top_n)
            .withColumn("recall_type", F.lit("itemcf"))
            .select(*REQUIRED_COLUMNS)
        )
        itemcf_recall_rows = itemcf_recall.count()
        average_recall_per_user = (
            itemcf_recall.groupBy("userId").count().agg(F.avg("count")).first()[0] if itemcf_recall_rows else 0.0
        )

        write_single_csv(itemcf_recall, output_file)
        if not output_file.exists():
            raise RuntimeError(f"itemcf_recall.csv was not written: {output_file}")
        if itemcf_recall.where(F.col("recall_type") != "itemcf").count():
            raise ValueError("Quality check failed: recall_type contains non-itemcf values.")
        if itemcf_recall.groupBy("userId").count().where(F.col("count") > top_n).count():
            raise ValueError(f"Quality check failed: some users have more than top_n={top_n} candidates.")
        if itemcf_recall.where(F.col("recall_score").isNull()).count():
            raise ValueError("Quality check failed: recall_score contains null values.")
        leaked = itemcf_recall.join(rated_pairs, on=["userId", "movieId"], how="inner").count()
        if leaked:
            raise ValueError("Quality check failed: itemcf recall contains train-rated movies.")

        summary = {
            "train_rows": train_rows,
            "valid_users": valid_users,
            "liked_interactions": liked_interactions,
            "movie_count": movie_count,
            "cooccurrence_pair_count": cooc_pair_count,
            "item_similarity_rows": item_similarity_rows,
            "itemcf_recall_rows": itemcf_recall_rows,
            "average_recall_per_user": float(average_recall_per_user or 0.0),
            "output_path": str(output_file),
            "max_liked_per_user": max_liked_per_user,
        }
        logger.info("train rows: %s", train_rows)
        logger.info("valid users: %s", valid_users)
        logger.info("liked interactions: %s", liked_interactions)
        logger.info("movie count: %s", movie_count)
        logger.info("co-occurrence pair count: %s", cooc_pair_count)
        logger.info("item similarity rows: %s", item_similarity_rows)
        logger.info("itemcf recall rows: %s", itemcf_recall_rows)
        logger.info("average recall per user: %.4f", summary["average_recall_per_user"])
        logger.info("output path: %s", output_file)
        logger.info("quality validation result: success")
        return summary
    finally:
        spark.stop()


def main() -> None:
    args = parse_args()
    try:
        build_itemcf_recall(
            args.train,
            args.output,
            args.top_sim,
            args.top_n,
            args.min_rating,
            args.max_liked_per_user,
        )
    except Exception as exc:
        logger.error("%s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
