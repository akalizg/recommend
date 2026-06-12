"""Check whether the project can create a SparkSession.

The script reads Spark settings from .env/environment variables. It defaults
to local mode and switches to standalone cluster mode when SPARK_MASTER_URL is
set, for example spark://192.168.56.101:7077.
"""
from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from spark_jobs.spark_utils import build_spark_session


def main() -> None:
    try:
        from pyspark.sql import SparkSession
    except ImportError as exc:
        raise RuntimeError("pyspark is not installed. Run `pip install -r requirements.txt`.") from exc

    spark = build_spark_session(
        SparkSession,
        "RecipeRecSparkConnectionCheck",
        default_driver_memory="1g",
        default_executor_memory="1g",
        default_shuffle_partitions=4,
        default_parallelism=4,
    )
    try:
        count_value = spark.range(0, 1000).repartition(4).count()
        sc = spark.sparkContext
        print("Spark connection OK")
        print(f"master={sc.master}")
        print(f"app_id={sc.applicationId}")
        print(f"spark_version={spark.version}")
        print(f"default_parallelism={sc.defaultParallelism}")
        print(f"web_ui={sc.uiWebUrl}")
        print(f"test_count={count_value}")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()

