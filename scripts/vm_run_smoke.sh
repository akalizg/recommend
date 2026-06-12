#!/usr/bin/env bash
set -euo pipefail

export SPARK_HOME="${SPARK_HOME:-/export/server/spark-3.1.2-bin-hadoop3.2}"
export PATH="$SPARK_HOME/bin:$SPARK_HOME/sbin:$PATH"

cd "${MOVIEREC_HOME:-/root/movierec}"

"$SPARK_HOME/bin/spark-submit" \
  --master "${SPARK_MASTER:-spark://node1:7077}" \
  --driver-memory "${SPARK_DRIVER_MEMORY:-1g}" \
  --executor-memory "${SPARK_EXECUTOR_MEMORY:-1g}" \
  --executor-cores "${SPARK_EXECUTOR_CORES:-1}" \
  --num-executors "${SPARK_EXECUTOR_INSTANCES:-3}" \
  --conf spark.eventLog.enabled=false \
  --conf spark.hadoop.fs.defaultFS=file:/// \
  scripts/vm_spark_smoke.py
