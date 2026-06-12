"""Shared Spark configuration helpers.

Spark jobs default to local mode, but can be pointed at a standalone Spark
cluster by setting SPARK_MASTER_URL, for example spark://192.168.56.101:7077.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def build_spark_session(
    spark_session_cls,
    app_name: str,
    *,
    default_master: str = "local[*]",
    default_driver_memory: str | None = None,
    default_executor_memory: str | None = None,
    default_shuffle_partitions: str | int | None = None,
    default_parallelism: str | int | None = None,
    extra_configs: Mapping[str, str | int | float | bool] | None = None,
):
    """Build a SparkSession from .env/environment configuration."""
    _load_dotenv()

    master = _env("SPARK_MASTER_URL") or _env("SPARK_MASTER") or default_master
    builder = spark_session_cls.builder.appName(app_name).master(master)

    configs: dict[str, str] = {
        "spark.sql.session.timeZone": _env("SPARK_SQL_TIMEZONE", "UTC") or "UTC",
        "spark.ui.showConsoleProgress": _env("SPARK_UI_SHOW_CONSOLE_PROGRESS", "false") or "false",
    }

    driver_memory = _env("SPARK_DRIVER_MEMORY", default_driver_memory)
    executor_memory = _env("SPARK_EXECUTOR_MEMORY", default_executor_memory)
    shuffle_partitions = _env("SPARK_SQL_SHUFFLE_PARTITIONS", str(default_shuffle_partitions) if default_shuffle_partitions is not None else None)
    default_parallelism_value = _env("SPARK_DEFAULT_PARALLELISM", str(default_parallelism) if default_parallelism is not None else None)

    if driver_memory:
        configs["spark.driver.memory"] = driver_memory
    if executor_memory:
        configs["spark.executor.memory"] = executor_memory
    if shuffle_partitions:
        configs["spark.sql.shuffle.partitions"] = shuffle_partitions
    if default_parallelism_value:
        configs["spark.default.parallelism"] = default_parallelism_value

    optional_env_configs = {
        "SPARK_EXECUTOR_CORES": "spark.executor.cores",
        "SPARK_EXECUTOR_INSTANCES": "spark.executor.instances",
        "SPARK_DRIVER_HOST": "spark.driver.host",
        "SPARK_DRIVER_BIND_ADDRESS": "spark.driver.bindAddress",
        "SPARK_LOCAL_DIR": "spark.local.dir",
        "SPARK_JARS": "spark.jars",
        "SPARK_PY_FILES": "spark.submit.pyFiles",
    }
    for env_name, config_name in optional_env_configs.items():
        value = _env(env_name)
        if value:
            configs[config_name] = value

    if extra_configs:
        configs.update({key: str(value) for key, value in extra_configs.items()})

    for key, value in configs.items():
        builder = builder.config(key, value)

    return builder.getOrCreate()

