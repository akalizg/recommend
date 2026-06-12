"""
Merge multi-channel recall candidates for MovieRec.

Current channels:
    - ALS recall
    - ItemCF recall
    - Lightweight LightGCN recall (optional)
    - Content-based recall (optional)
    - Hot/popular recall (optional)

Future channels can be added without changing the output contract.
"""
from __future__ import annotations

import argparse
import logging
import shutil
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ALS = PROJECT_ROOT / "data" / "recall" / "als_recall.csv"
DEFAULT_ITEMCF = PROJECT_ROOT / "data" / "recall" / "itemcf_recall.csv"
DEFAULT_LIGHTGCN = PROJECT_ROOT / "data" / "recall" / "lightgcn_recall.csv"
DEFAULT_CONTENT = PROJECT_ROOT / "data" / "recall" / "content_recall.csv"
DEFAULT_HOT = PROJECT_ROOT / "data" / "recall" / "hot_recall.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "recall" / "merged_recall_candidates.csv"
OUTPUT_COLUMNS = (
    "userId",
    "movieId",
    "als_score",
    "itemcf_score",
    "embedding_score",
    "lightgcn_score",
    "content_score",
    "hot_score",
    "is_als_recall",
    "is_itemcf_recall",
    "is_embedding_recall",
    "is_lightgcn_recall",
    "is_content_recall",
    "is_hot_recall",
    "recall_source_count",
    "merged_recall_score",
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge multi-channel recall candidates.")
    parser.add_argument("--als", default=str(DEFAULT_ALS), help="ALS recall CSV.")
    parser.add_argument("--itemcf", default=str(DEFAULT_ITEMCF), help="ItemCF recall CSV.")
    parser.add_argument("--lightgcn", default=str(DEFAULT_LIGHTGCN), help="LightGCN recall CSV.")
    parser.add_argument("--content", default=str(DEFAULT_CONTENT), help="Content recall CSV.")
    parser.add_argument("--hot", default=str(DEFAULT_HOT), help="Hot recall CSV.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Merged recall CSV output.")
    parser.add_argument("--top-n", type=int, default=100, help="Top-N merged candidates per user.")
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


def create_spark_session(app_name: str = "MovieRecSparkMergeRecall"):
    SparkSession, _, _, _ = require_pyspark()
    try:
        return (
            SparkSession.builder.appName(app_name)
            .master("local[*]")
            .config("spark.sql.session.timeZone", "UTC")
            .config("spark.ui.showConsoleProgress", "false")
            .getOrCreate()
        )
    except Exception as exc:
        raise RuntimeError(f"Failed to start SparkSession. Original error: {exc}") from exc


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


def _read_recall(spark, path: Path, expected_type: str):
    _, _, F, T = require_pyspark()
    schema = T.StructType(
        [
            T.StructField("userId", T.StringType(), True),
            T.StructField("movieId", T.StringType(), True),
            T.StructField("recall_type", T.StringType(), True),
            T.StructField("recall_score", T.StringType(), True),
        ]
    )
    return (
        spark.read.option("header", True).schema(schema).csv(str(path))
        .withColumn("userId", F.col("userId").cast("int"))
        .withColumn("movieId", F.col("movieId").cast("int"))
        .withColumn("recall_score", F.col("recall_score").cast("double"))
        .where(
            F.col("userId").isNotNull()
            & F.col("movieId").isNotNull()
            & F.col("recall_score").isNotNull()
            & (F.col("recall_type") == expected_type)
        )
        .select("userId", "movieId", "recall_score")
    )


def _normalize_by_user(df, score_col: str, output_col: str):
    _, Window, F, _ = require_pyspark()
    window = Window.partitionBy("userId")
    return (
        df.withColumn(f"{score_col}_min", F.min(score_col).over(window))
        .withColumn(f"{score_col}_max", F.max(score_col).over(window))
        .withColumn(
            output_col,
            F.when(F.col(score_col).isNull(), F.lit(0.0))
            .when(F.col(f"{score_col}_max") == F.col(f"{score_col}_min"), F.lit(1.0))
            .otherwise((F.col(score_col) - F.col(f"{score_col}_min")) / (F.col(f"{score_col}_max") - F.col(f"{score_col}_min"))),
        )
        .drop(f"{score_col}_min", f"{score_col}_max")
    )


def merge_recall(
    als_path: str | Path | None = None,
    itemcf_path: str | Path | None = None,
    output_path: str | Path | None = None,
    top_n: int = 100,
    lightgcn_path: str | Path | None = None,
    content_path: str | Path | None = None,
    hot_path: str | Path | None = None,
) -> dict:
    _, Window, F, _ = require_pyspark()
    als_file = Path(als_path).resolve() if als_path else DEFAULT_ALS
    itemcf_file = Path(itemcf_path).resolve() if itemcf_path else DEFAULT_ITEMCF
    lightgcn_file = Path(lightgcn_path).resolve() if lightgcn_path else DEFAULT_LIGHTGCN
    content_file = Path(content_path).resolve() if content_path else DEFAULT_CONTENT
    hot_file = Path(hot_path).resolve() if hot_path else DEFAULT_HOT
    output_file = Path(output_path).resolve() if output_path else DEFAULT_OUTPUT

    if not als_file.exists():
        raise FileNotFoundError(f"ALS recall input not found: {als_file}")
    if not itemcf_file.exists():
        raise FileNotFoundError(f"ItemCF recall input not found: {itemcf_file}")

    logger.info("ALS recall input: %s", als_file)
    logger.info("ItemCF recall input: %s", itemcf_file)
    logger.info("LightGCN recall input: %s", lightgcn_file if lightgcn_file.exists() else "missing; skipped")
    logger.info("Content recall input: %s", content_file if content_file.exists() else "missing; skipped")
    logger.info("Hot recall input: %s", hot_file if hot_file.exists() else "missing; skipped")
    logger.info("Output path: %s", output_file)
    logger.info("TopN per user: %s", top_n)

    spark = create_spark_session()
    try:
        als = _read_recall(spark, als_file, "als").withColumnRenamed("recall_score", "als_score")
        itemcf = _read_recall(spark, itemcf_file, "itemcf").withColumnRenamed("recall_score", "itemcf_score")
        lightgcn = (
            _read_recall(spark, lightgcn_file, "lightgcn").withColumnRenamed("recall_score", "lightgcn_score")
            if lightgcn_file.exists()
            else None
        )
        content = (
            _read_recall(spark, content_file, "content").withColumnRenamed("recall_score", "content_score")
            if content_file.exists()
            else None
        )
        hot = (
            _read_recall(spark, hot_file, "hot").withColumnRenamed("recall_score", "hot_score")
            if hot_file.exists()
            else None
        )
        als_rows = als.count()
        itemcf_rows = itemcf.count()
        lightgcn_rows = lightgcn.count() if lightgcn is not None else 0
        content_rows = content.count() if content is not None else 0
        hot_rows = hot.count() if hot is not None else 0

        merged = als.join(itemcf, on=["userId", "movieId"], how="full_outer")
        if lightgcn is not None:
            merged = merged.join(lightgcn, on=["userId", "movieId"], how="full_outer")
        if content is not None:
            merged = merged.join(content, on=["userId", "movieId"], how="full_outer")
        if hot is not None:
            merged = merged.join(hot, on=["userId", "movieId"], how="full_outer")
        merged = (
            merged.withColumn("is_als_recall", F.when(F.col("als_score").isNotNull(), F.lit(1)).otherwise(F.lit(0)))
            .withColumn("is_itemcf_recall", F.when(F.col("itemcf_score").isNotNull(), F.lit(1)).otherwise(F.lit(0)))
            .withColumn("is_lightgcn_recall", F.when(F.col("lightgcn_score").isNotNull(), F.lit(1)).otherwise(F.lit(0)) if "lightgcn_score" in merged.columns else F.lit(0))
            .withColumn("is_content_recall", F.when(F.col("content_score").isNotNull(), F.lit(1)).otherwise(F.lit(0)) if "content_score" in merged.columns else F.lit(0))
            .withColumn("is_hot_recall", F.when(F.col("hot_score").isNotNull(), F.lit(1)).otherwise(F.lit(0)) if "hot_score" in merged.columns else F.lit(0))
            .withColumn("als_score", F.coalesce(F.col("als_score"), F.lit(0.0)))
            .withColumn("itemcf_score", F.coalesce(F.col("itemcf_score"), F.lit(0.0)))
            .withColumn("lightgcn_score", F.coalesce(F.col("lightgcn_score"), F.lit(0.0)) if "lightgcn_score" in merged.columns else F.lit(0.0))
            .withColumn("content_score", F.coalesce(F.col("content_score"), F.lit(0.0)) if "content_score" in merged.columns else F.lit(0.0))
            .withColumn("hot_score", F.coalesce(F.col("hot_score"), F.lit(0.0)) if "hot_score" in merged.columns else F.lit(0.0))
            .withColumn("embedding_score", F.lit(0.0))
            .withColumn("is_embedding_recall", F.lit(0))
        )
        merged = _normalize_by_user(merged, "als_score", "normalized_als_score")
        merged = _normalize_by_user(merged, "itemcf_score", "normalized_itemcf_score")
        merged = _normalize_by_user(merged, "lightgcn_score", "normalized_lightgcn_score")
        merged = _normalize_by_user(merged, "content_score", "normalized_content_score")
        merged = _normalize_by_user(merged, "hot_score", "normalized_hot_score")
        merged = (
            merged.withColumn(
                "recall_source_count",
                F.col("is_als_recall")
                + F.col("is_itemcf_recall")
                + F.col("is_embedding_recall")
                + F.col("is_lightgcn_recall")
                + F.col("is_content_recall")
                + F.col("is_hot_recall"),
            )
            .withColumn(
                "merged_recall_score",
                F.lit(0.38) * F.col("normalized_als_score")
                + F.lit(0.25) * F.col("normalized_itemcf_score")
                + F.lit(0.12) * F.col("normalized_lightgcn_score")
                + F.lit(0.15) * F.col("normalized_content_score")
                + F.lit(0.10) * F.col("normalized_hot_score")
                + F.lit(0.1) * F.col("recall_source_count"),
            )
        )
        before_topn = merged.count()
        rank_window = Window.partitionBy("userId").orderBy(F.col("merged_recall_score").desc(), F.col("movieId").asc())
        final_df = (
            merged.withColumn("rn", F.row_number().over(rank_window))
            .where(F.col("rn") <= top_n)
            .select(*OUTPUT_COLUMNS)
        )
        after_topn = final_df.count()
        user_count = final_df.select("userId").distinct().count()
        average_candidates = final_df.groupBy("userId").count().agg(F.avg("count")).first()[0] if after_topn else 0.0

        write_single_csv(final_df, output_file)
        if not output_file.exists():
            raise RuntimeError(f"merged_recall_candidates.csv was not written: {output_file}")
        if final_df.groupBy("userId").count().where(F.col("count") > top_n).count():
            raise ValueError(f"Quality check failed: some users have more than top_n={top_n} candidates.")
        if final_df.where(F.col("recall_source_count") < 1).count():
            raise ValueError("Quality check failed: recall_source_count contains values < 1.")
        if final_df.where(
            (
                F.col("is_als_recall")
                + F.col("is_itemcf_recall")
                + F.col("is_lightgcn_recall")
                + F.col("is_content_recall")
                + F.col("is_hot_recall")
            )
            < 1
        ).count():
            raise ValueError("Quality check failed: candidates have no recall source.")
        if final_df.where(F.col("merged_recall_score").isNull()).count():
            raise ValueError("Quality check failed: merged_recall_score contains null values.")

        summary = {
            "als_recall_rows": als_rows,
            "itemcf_recall_rows": itemcf_rows,
            "lightgcn_recall_rows": lightgcn_rows,
            "content_recall_rows": content_rows,
            "hot_recall_rows": hot_rows,
            "merged_rows_before_topn": before_topn,
            "merged_rows_after_topn": after_topn,
            "user_count": user_count,
            "average_candidates_per_user": float(average_candidates or 0.0),
            "output_path": str(output_file),
        }
        logger.info("als recall rows: %s", als_rows)
        logger.info("itemcf recall rows: %s", itemcf_rows)
        logger.info("lightgcn recall rows: %s", lightgcn_rows)
        logger.info("content recall rows: %s", content_rows)
        logger.info("hot recall rows: %s", hot_rows)
        logger.info("merged rows before topN: %s", before_topn)
        logger.info("merged rows after topN: %s", after_topn)
        logger.info("user count: %s", user_count)
        logger.info("average candidates per user: %.4f", summary["average_candidates_per_user"])
        logger.info("output path: %s", output_file)
        logger.info("quality validation result: success")
        return summary
    finally:
        spark.stop()


def main() -> None:
    args = parse_args()
    try:
        merge_recall(
            args.als,
            args.itemcf,
            args.output,
            args.top_n,
            lightgcn_path=args.lightgcn,
            content_path=args.content,
            hot_path=args.hot,
        )
    except Exception as exc:
        logger.error("%s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
