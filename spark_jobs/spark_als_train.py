"""
Spark MLlib ALS training job for MovieRec.

Trains an offline ALS model from train_ratings.csv, exports user/movie factors,
and writes ALS recall candidates. This does not replace the current online
FAISS index or train XGBoost.
"""
from __future__ import annotations

import argparse
import logging
import shutil
import sys
import tempfile
import types
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TRAIN = PROJECT_ROOT / "data" / "processed" / "train_ratings.csv"
DEFAULT_FACTORS_DIR = PROJECT_ROOT / "data" / "factors"
DEFAULT_RECALL_DIR = PROJECT_ROOT / "data" / "recall"
DEFAULT_MODEL_DIR = PROJECT_ROOT / "models" / "spark_als"

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train Spark ALS factors for MovieRec.")
    parser.add_argument("--train", default=str(DEFAULT_TRAIN), help="Train ratings input.")
    parser.add_argument("--factors-dir", default=str(DEFAULT_FACTORS_DIR), help="Factor output directory.")
    parser.add_argument("--recall-dir", default=str(DEFAULT_RECALL_DIR), help="ALS recall output directory.")
    parser.add_argument("--model-dir", default=str(DEFAULT_MODEL_DIR), help="Spark ALS model output directory.")
    parser.add_argument("--rank", type=int, default=64, help="ALS factor dimension.")
    parser.add_argument("--max-iter", type=int, default=15, help="ALS max iterations.")
    parser.add_argument("--reg-param", type=float, default=0.1, help="ALS regularization.")
    parser.add_argument("--top-n", type=int, default=100, help="Top-N ALS recall candidates per user.")
    return parser.parse_args()


def require_pyspark():
    try:
        # PySpark 3.5 still imports distutils.version.LooseVersion in parts of
        # pyspark.ml. Python 3.13 removed distutils, so provide the tiny piece it
        # needs without changing the rest of the environment.
        if "distutils.version" not in sys.modules:
            from packaging.version import Version

            distutils_module = sys.modules.setdefault("distutils", types.ModuleType("distutils"))
            version_module = types.ModuleType("distutils.version")

            class LooseVersion:
                def __init__(self, value):
                    self.value = str(value)
                    self._version = Version(self.value)

                def _coerce(self, other):
                    return other._version if isinstance(other, LooseVersion) else Version(str(other))

                def __lt__(self, other):
                    return self._version < self._coerce(other)

                def __le__(self, other):
                    return self._version <= self._coerce(other)

                def __eq__(self, other):
                    return self._version == self._coerce(other)

                def __ge__(self, other):
                    return self._version >= self._coerce(other)

                def __gt__(self, other):
                    return self._version > self._coerce(other)

                def __repr__(self):
                    return f"LooseVersion({self.value!r})"

            version_module.LooseVersion = LooseVersion
            distutils_module.version = version_module
            sys.modules["distutils.version"] = version_module

        from pyspark.ml.recommendation import ALS
        from pyspark.sql import SparkSession
        from pyspark.sql import Window
        from pyspark.sql import functions as F
        from pyspark.sql import types as T
    except ImportError as exc:
        raise RuntimeError(
            "Failed to import pyspark MLlib. Ensure pyspark is installed with `pip install -r requirements.txt`. "
            f"Original error: {exc}"
        ) from exc
    return ALS, SparkSession, Window, F, T


def create_spark_session(app_name: str = "MovieRecSparkALSTrain"):
    _, SparkSession, _, _, _ = require_pyspark()
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


def train_als(
    train_path: str | Path | None = None,
    factors_dir: str | Path | None = None,
    recall_dir: str | Path | None = None,
    model_dir: str | Path | None = None,
    rank: int = 64,
    max_iter: int = 15,
    reg_param: float = 0.1,
    top_n: int = 100,
) -> dict:
    """Train Spark ALS and export factors/recall files."""
    ALS, _, Window, F, T = require_pyspark()
    train_file = Path(train_path).resolve() if train_path else DEFAULT_TRAIN
    factors_path = Path(factors_dir).resolve() if factors_dir else DEFAULT_FACTORS_DIR
    recall_path = Path(recall_dir).resolve() if recall_dir else DEFAULT_RECALL_DIR
    model_path = Path(model_dir).resolve() if model_dir else DEFAULT_MODEL_DIR
    user_factor_output = factors_path / "user_factors.csv"
    movie_factor_output = factors_path / "movie_factors.csv"
    recall_output = recall_path / "als_recall.csv"

    if not train_file.exists():
        raise FileNotFoundError(f"Train ratings input not found: {train_file}")

    logger.info("Train ratings input: %s", train_file)
    logger.info("Factors directory: %s", factors_path)
    logger.info("Recall directory: %s", recall_path)
    logger.info("Model directory: %s", model_path)
    logger.info(
        "ALS params: rank=%s, maxIter=%s, regParam=%s, topN=%s, coldStartStrategy=drop",
        rank,
        max_iter,
        reg_param,
        top_n,
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
            .where(F.col("userId").isNotNull() & F.col("movieId").isNotNull() & F.col("rating").isNotNull())
            .select("userId", "movieId", "rating")
        )
        train_rows = train.count()
        user_count = train.select("userId").distinct().count()
        movie_count = train.select("movieId").distinct().count()

        als = ALS(
            userCol="userId",
            itemCol="movieId",
            ratingCol="rating",
            rank=rank,
            maxIter=max_iter,
            regParam=reg_param,
            coldStartStrategy="drop",
            nonnegative=False,
            implicitPrefs=False,
        )
        model = als.fit(train)

        if model_path.exists():
            shutil.rmtree(model_path)
        model.write().overwrite().save(str(model_path))

        features_expr = F.concat_ws("|", F.expr("transform(features, x -> cast(x as string))")).alias("features")
        user_factors = model.userFactors.select(F.col("id").cast("int").alias("userId"), features_expr)
        movie_factors = model.itemFactors.select(F.col("id").cast("int").alias("movieId"), features_expr)
        user_factor_rows = user_factors.count()
        movie_factor_rows = movie_factors.count()

        raw_recall = (
            model.recommendForAllUsers(top_n + 100)
            .select(F.col("userId"), F.explode("recommendations").alias("rec"))
            .select(
                F.col("userId").cast("int"),
                F.col("rec.movieId").cast("int").alias("movieId"),
                F.col("rec.rating").cast("double").alias("recall_score"),
            )
            .where(F.col("recall_score").isNotNull())
        )
        rated_pairs = train.select("userId", "movieId").dropDuplicates()
        filtered_recall = raw_recall.join(rated_pairs, on=["userId", "movieId"], how="left_anti")
        recall_window = Window.partitionBy("userId").orderBy(F.col("recall_score").desc(), F.col("movieId").asc())
        als_recall = (
            filtered_recall.withColumn("rn", F.row_number().over(recall_window))
            .where(F.col("rn") <= top_n)
            .withColumn("recall_type", F.lit("als"))
            .select("userId", "movieId", "recall_type", "recall_score")
        )
        als_recall_rows = als_recall.count()
        average_recall_per_user = (
            als_recall.groupBy("userId").count().agg(F.avg("count").alias("avg_recall")).first()["avg_recall"]
            if als_recall_rows
            else 0.0
        )

        write_single_csv(user_factors, user_factor_output)
        write_single_csv(movie_factors, movie_factor_output)
        write_single_csv(als_recall, recall_output)

        if not user_factor_output.exists():
            raise RuntimeError(f"user_factors.csv was not written: {user_factor_output}")
        if not movie_factor_output.exists():
            raise RuntimeError(f"movie_factors.csv was not written: {movie_factor_output}")
        if not recall_output.exists():
            raise RuntimeError(f"als_recall.csv was not written: {recall_output}")
        if not model_path.exists():
            raise RuntimeError(f"Spark ALS model was not saved: {model_path}")

        factor_dim_check = (
            movie_factors.limit(10)
            .withColumn("factor_dim", F.size(F.split(F.col("features"), r"\|")))
            .where(F.col("factor_dim") != rank)
            .count()
        )
        if factor_dim_check:
            raise ValueError(f"Quality check failed: some movie factors do not have rank dimension {rank}.")
        recall_type_bad = als_recall.where(F.col("recall_type") != "als").count()
        if recall_type_bad:
            raise ValueError("Quality check failed: als_recall contains recall_type values other than 'als'.")
        recall_over_top_n = als_recall.groupBy("userId").count().where(F.col("count") > top_n).count()
        if recall_over_top_n:
            raise ValueError(f"Quality check failed: some users have more than top_n={top_n} recall rows.")
        null_scores = als_recall.where(F.col("recall_score").isNull()).count()
        if null_scores:
            raise ValueError("Quality check failed: als_recall contains null recall_score.")
        leaked_rated_pairs = als_recall.join(rated_pairs, on=["userId", "movieId"], how="inner").count()
        if leaked_rated_pairs:
            raise ValueError("Quality check failed: als_recall contains movies already rated in train set.")

        summary = {
            "train_rows": train_rows,
            "user_count": user_count,
            "movie_count": movie_count,
            "rank": rank,
            "max_iter": max_iter,
            "reg_param": reg_param,
            "top_n": top_n,
            "user_factor_rows": user_factor_rows,
            "movie_factor_rows": movie_factor_rows,
            "als_recall_rows": als_recall_rows,
            "average_recall_per_user": float(average_recall_per_user or 0.0),
            "model_path": str(model_path),
            "user_factors_path": str(user_factor_output),
            "movie_factors_path": str(movie_factor_output),
            "als_recall_path": str(recall_output),
        }

        logger.info("train rows: %s", train_rows)
        logger.info("user count: %s", user_count)
        logger.info("movie count: %s", movie_count)
        logger.info("user factors rows: %s", user_factor_rows)
        logger.info("movie factors rows: %s", movie_factor_rows)
        logger.info("als recall rows: %s", als_recall_rows)
        logger.info("average recall per user: %.4f", summary["average_recall_per_user"])
        logger.info("model path: %s", model_path)
        logger.info("output paths: %s, %s, %s", user_factor_output, movie_factor_output, recall_output)
        logger.info("quality validation result: success")
        return summary
    finally:
        spark.stop()


def main() -> None:
    args = parse_args()
    try:
        train_als(
            args.train,
            args.factors_dir,
            args.recall_dir,
            args.model_dir,
            args.rank,
            args.max_iter,
            args.reg_param,
            args.top_n,
        )
    except Exception as exc:
        logger.error("%s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
