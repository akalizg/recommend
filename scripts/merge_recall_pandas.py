"""
Merge multi-channel recall CSV files with pandas.

This is a local fallback for larger Food.com official-split runs where Spark's
window sort can exceed the available JVM heap. The output schema matches
spark_jobs/spark_merge_recall.py.
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ALS = PROJECT_ROOT / "data" / "recall" / "als_recall.csv"
DEFAULT_ITEMCF = PROJECT_ROOT / "data" / "recall" / "itemcf_recall.csv"
DEFAULT_EMBEDDING = PROJECT_ROOT / "data" / "recall" / "faiss_hnsw_recall.csv"
DEFAULT_LIGHTGCN = PROJECT_ROOT / "data" / "recall" / "lightgcn_recall.csv"
DEFAULT_CONTENT = PROJECT_ROOT / "data" / "recall" / "content_recall.csv"
DEFAULT_HOT = PROJECT_ROOT / "data" / "recall" / "hot_recall.csv"
DEFAULT_KG = PROJECT_ROOT / "data" / "recall" / "kg_recall.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "recall" / "merged_recall_candidates.csv"

OUTPUT_COLUMNS = [
    "userId",
    "movieId",
    "als_score",
    "itemcf_score",
    "embedding_score",
    "lightgcn_score",
    "content_score",
    "hot_score",
    "kg_score",
    "is_als_recall",
    "is_itemcf_recall",
    "is_embedding_recall",
    "is_lightgcn_recall",
    "is_content_recall",
    "is_hot_recall",
    "is_kg_recall",
    "recall_source_count",
    "merged_recall_score",
]

CHANNELS = [
    ("als", "als_score", "is_als_recall", 0.28),
    ("itemcf", "itemcf_score", "is_itemcf_recall", 0.20),
    ("embedding", "embedding_score", "is_embedding_recall", 0.15),
    ("lightgcn", "lightgcn_score", "is_lightgcn_recall", 0.11),
    ("content", "content_score", "is_content_recall", 0.10),
    ("hot", "hot_score", "is_hot_recall", 0.08),
    ("kg", "kg_score", "is_kg_recall", 0.08),
]

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge recall CSVs with pandas.")
    parser.add_argument("--als", default=str(DEFAULT_ALS))
    parser.add_argument("--itemcf", default=str(DEFAULT_ITEMCF))
    parser.add_argument("--embedding", default=str(DEFAULT_EMBEDDING))
    parser.add_argument("--lightgcn", default=str(DEFAULT_LIGHTGCN))
    parser.add_argument("--content", default=str(DEFAULT_CONTENT))
    parser.add_argument("--hot", default=str(DEFAULT_HOT))
    parser.add_argument("--kg", default=str(DEFAULT_KG))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--top-n", type=int, default=100)
    return parser.parse_args()


def _read_channel(path: Path, recall_type: str, score_col: str, flag_col: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"{recall_type} recall input not found: {path}")
    usecols = ["userId", "movieId", "recall_type", "recall_score"]
    if recall_type == "kg":
        usecols = ["userId", "movieId", "recall_type", "recall_score"]
    df = pd.read_csv(path, usecols=usecols)
    df["userId"] = pd.to_numeric(df["userId"], errors="coerce")
    df["movieId"] = pd.to_numeric(df["movieId"], errors="coerce")
    df["recall_score"] = pd.to_numeric(df["recall_score"], errors="coerce")
    df = df[
        df["userId"].notna()
        & df["movieId"].notna()
        & df["recall_score"].notna()
        & (df["recall_type"] == recall_type)
    ].copy()
    df["userId"] = df["userId"].astype("int32")
    df["movieId"] = df["movieId"].astype("int32")
    df[score_col] = df["recall_score"].astype("float32")
    df[flag_col] = 1
    df = df.groupby(["userId", "movieId"], as_index=False).agg({score_col: "max", flag_col: "max"})
    logger.info("%s rows after aggregation: %s", recall_type, len(df))
    return df


def _normalize_by_user(df: pd.DataFrame, score_col: str, output_col: str) -> None:
    values = df[score_col].astype("float32")
    mins = values.groupby(df["userId"], sort=False).transform("min")
    maxs = values.groupby(df["userId"], sort=False).transform("max")
    denom = maxs - mins
    normalized = (values - mins) / denom.where(denom != 0)
    df[output_col] = normalized.fillna(1.0).astype("float32")


def merge_recall_pandas(
    als_path: str | Path = DEFAULT_ALS,
    itemcf_path: str | Path = DEFAULT_ITEMCF,
    embedding_path: str | Path = DEFAULT_EMBEDDING,
    lightgcn_path: str | Path = DEFAULT_LIGHTGCN,
    content_path: str | Path = DEFAULT_CONTENT,
    hot_path: str | Path = DEFAULT_HOT,
    kg_path: str | Path = DEFAULT_KG,
    output_path: str | Path = DEFAULT_OUTPUT,
    top_n: int = 100,
) -> dict:
    if top_n <= 0:
        raise ValueError("top_n must be positive.")
    paths = {
        "als": Path(als_path).resolve(),
        "itemcf": Path(itemcf_path).resolve(),
        "embedding": Path(embedding_path).resolve(),
        "lightgcn": Path(lightgcn_path).resolve(),
        "content": Path(content_path).resolve(),
        "hot": Path(hot_path).resolve(),
        "kg": Path(kg_path).resolve(),
    }
    output_file = Path(output_path).resolve()

    frames = []
    input_rows: dict[str, int] = {}
    for recall_type, score_col, flag_col, _ in CHANNELS:
        frame = _read_channel(paths[recall_type], recall_type, score_col, flag_col)
        input_rows[f"{recall_type}_recall_rows"] = int(len(frame))
        frames.append(frame)

    merged = pd.concat(frames, ignore_index=True, sort=False)
    aggregations = {}
    for _, score_col, flag_col, _ in CHANNELS:
        aggregations[score_col] = "max"
        aggregations[flag_col] = "max"
    merged = merged.groupby(["userId", "movieId"], as_index=False, sort=False).agg(aggregations)

    for _, score_col, flag_col, _ in CHANNELS:
        merged[score_col] = pd.to_numeric(merged[score_col], errors="coerce").fillna(0.0).astype("float32")
        merged[flag_col] = pd.to_numeric(merged[flag_col], errors="coerce").fillna(0).astype("int8")
        _normalize_by_user(merged, score_col, f"normalized_{score_col}")

    flag_cols = [flag_col for _, _, flag_col, _ in CHANNELS]
    merged["recall_source_count"] = merged[flag_cols].sum(axis=1).astype("int8")
    merged["merged_recall_score"] = 0.1 * merged["recall_source_count"].astype("float32")
    for _, score_col, _, weight in CHANNELS:
        merged["merged_recall_score"] += weight * merged[f"normalized_{score_col}"]

    before_topn = int(len(merged))
    merged = merged.sort_values(["userId", "merged_recall_score", "movieId"], ascending=[True, False, True])
    final = merged.groupby("userId", sort=False).head(top_n).copy()
    final = final[OUTPUT_COLUMNS]
    final["userId"] = final["userId"].astype("int32")
    final["movieId"] = final["movieId"].astype("int32")
    final["merged_recall_score"] = final["merged_recall_score"].astype("float32")

    output_file.parent.mkdir(parents=True, exist_ok=True)
    final.to_csv(output_file, index=False)
    if final.empty:
        raise ValueError("Merged recall output is empty.")
    if final.groupby("userId").size().max() > top_n:
        raise ValueError(f"Quality check failed: some users have more than top_n={top_n} candidates.")
    if (final["recall_source_count"] < 1).any():
        raise ValueError("Quality check failed: recall_source_count contains values < 1.")

    summary = {
        **input_rows,
        "merged_rows_before_topn": before_topn,
        "merged_rows_after_topn": int(len(final)),
        "user_count": int(final["userId"].nunique()),
        "average_candidates_per_user": float(final.groupby("userId").size().mean()),
        "output_path": str(output_file),
    }
    logger.info("Pandas merge summary: %s", summary)
    return summary


def main() -> None:
    args = parse_args()
    merge_recall_pandas(
        args.als,
        args.itemcf,
        args.embedding,
        args.lightgcn,
        args.content,
        args.hot,
        args.kg,
        args.output,
        args.top_n,
    )


if __name__ == "__main__":
    main()
