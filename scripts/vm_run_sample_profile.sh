#!/usr/bin/env bash
set -euo pipefail

export SPARK_HOME="${SPARK_HOME:-/export/server/spark-3.1.2-bin-hadoop3.2}"
export PATH="$SPARK_HOME/bin:$SPARK_HOME/sbin:$PATH"

cd "${MOVIEREC_HOME:-/root/movierec}"

mkdir -p data/sample_processed data/features_sample
head -n 20001 data/processed/train_ratings.csv > data/sample_processed/train_ratings_sample_20k.csv
head -n 200001 data/processed/movie_tags.csv > data/sample_processed/movie_tags_sample_200k.csv

"$SPARK_HOME/bin/spark-submit" \
  --master "${SPARK_MASTER:-spark://node1:7077}" \
  --driver-memory "${SPARK_DRIVER_MEMORY:-1g}" \
  --executor-memory "${SPARK_EXECUTOR_MEMORY:-1g}" \
  --executor-cores "${SPARK_EXECUTOR_CORES:-1}" \
  --num-executors "${SPARK_EXECUTOR_INSTANCES:-3}" \
  --conf spark.eventLog.enabled=false \
  --conf spark.hadoop.fs.defaultFS=file:/// \
  spark_jobs/spark_build_profile.py \
  --train /root/movierec/data/sample_processed/train_ratings_sample_20k.csv \
  --movies /root/movierec/data/processed/movies_clean.csv \
  --tags /root/movierec/data/sample_processed/movie_tags_sample_200k.csv \
  --output-dir /root/movierec/data/features_sample \
  --max-tags-per-movie 20
