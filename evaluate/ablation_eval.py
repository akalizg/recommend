"""
Build ablation experiment tables from offline metrics.

The script summarizes ALS, ItemCF, merged recall, XGBoost ranking, and MMR
reranking without inventing improvements that are not present in the metrics.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_METRICS = PROJECT_ROOT / "data" / "eval" / "offline_metrics.csv"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "eval"
DEFAULT_K = 10

VARIANT_ORDER = ["ALS", "ItemCF", "ALS+ItemCF_Merged", "XGBoost_Top50", "XGBoost_MMR_Top10"]
REMOVED_MODULES = {
    "ALS": "ItemCF, merged recall, XGBoost ranking, MMR reranking",
    "ItemCF": "ALS, merged recall, XGBoost ranking, MMR reranking",
    "ALS+ItemCF_Merged": "XGBoost ranking, MMR reranking",
    "XGBoost_Top50": "MMR reranking",
    "XGBoost_MMR_Top10": "未移除模块",
}
OUTPUT_COLUMNS = [
    "variant",
    "removed_module",
    "k",
    "precision",
    "recall",
    "ndcg",
    "hit_rate",
    "coverage",
    "diversity",
    "main_observation",
]

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build ablation metrics and summary from offline metrics.")
    parser.add_argument("--metrics", default=str(DEFAULT_METRICS), help="offline_metrics.csv input.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Ablation output directory.")
    parser.add_argument("--k", type=int, default=DEFAULT_K, help="K value to summarize.")
    return parser.parse_args()


def _fmt_delta(value: float) -> str:
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.6f}"


def _get_row(metrics_at_k: pd.DataFrame, variant: str) -> pd.Series | None:
    subset = metrics_at_k[metrics_at_k["model_name"] == variant]
    if subset.empty:
        return None
    return subset.iloc[0]


def _observation(metrics_at_k: pd.DataFrame, variant: str) -> str:
    row = _get_row(metrics_at_k, variant)
    if row is None:
        return "Missing metrics for this variant; no conclusion generated."

    if variant == "ALS":
        return "ALS single-channel recall baseline."
    if variant == "ItemCF":
        return "ItemCF single-channel recall baseline for collaborative co-occurrence comparison."

    if variant == "ALS+ItemCF_Merged":
        als = _get_row(metrics_at_k, "ALS")
        if als is None:
            return "Merged recall is available, but ALS baseline is missing."
        delta = float(row["recall"]) - float(als["recall"])
        if delta > 0:
            return f"Compared with ALS, merged recall improves Recall@{int(row['k'])} by {_fmt_delta(delta)}, indicating broader candidate coverage."
        return (
            f"Compared with ALS, merged recall does not improve Recall@{int(row['k'])} "
            f"({_fmt_delta(delta)}); current candidates may be limited by sparse MovieLens small interactions."
        )

    if variant == "XGBoost_Top50":
        merged = _get_row(metrics_at_k, "ALS+ItemCF_Merged")
        if merged is None:
            return "XGBoost ranking is available, but merged recall baseline is missing."
        precision_delta = float(row["precision"]) - float(merged["precision"])
        ndcg_delta = float(row["ndcg"]) - float(merged["ndcg"])
        if precision_delta > 0 or ndcg_delta > 0:
            return (
                f"Compared with merged recall, XGBoost changes Precision@{int(row['k'])} by {_fmt_delta(precision_delta)} "
                f"and NDCG@{int(row['k'])} by {_fmt_delta(ndcg_delta)}, showing ranking quality impact."
            )
        return (
            f"Compared with merged recall, XGBoost does not improve Precision/NDCG at K={int(row['k'])} "
            f"({_fmt_delta(precision_delta)}, {_fmt_delta(ndcg_delta)}); candidate positives are sparse."
        )

    if variant == "XGBoost_MMR_Top10":
        xgb = _get_row(metrics_at_k, "XGBoost_Top50")
        if xgb is None:
            return "MMR reranking is available, but XGBoost baseline is missing."
        diversity_delta = float(row["diversity"]) - float(xgb["diversity"])
        precision_delta = float(row["precision"]) - float(xgb["precision"])
        if diversity_delta > 0:
            return (
                f"Compared with XGBoost Top50, MMR improves Diversity@{int(row['k'])} by {_fmt_delta(diversity_delta)} "
                f"with Precision change {_fmt_delta(precision_delta)}."
            )
        return (
            f"Compared with XGBoost Top50, MMR does not improve Diversity@{int(row['k'])} "
            f"({_fmt_delta(diversity_delta)}); lambda_rel or candidate diversity may need tuning."
        )

    return "No observation rule configured."


def _markdown_table(df: pd.DataFrame) -> str:
    cols = ["variant", "precision", "recall", "ndcg", "hit_rate", "coverage", "diversity"]
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in df.iterrows():
        values = []
        for col in cols:
            if col == "variant":
                values.append(str(row[col]))
            else:
                values.append(f"{float(row[col]):.6f}")
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def build_ablation_eval(
    metrics_path: str | Path | None = None,
    output_dir: str | Path | None = None,
    k: int = DEFAULT_K,
) -> dict:
    metrics_file = Path(metrics_path).resolve() if metrics_path else DEFAULT_METRICS
    output_path = Path(output_dir).resolve() if output_dir else DEFAULT_OUTPUT_DIR
    metrics_output = output_path / "ablation_metrics.csv"
    summary_output = output_path / "ablation_summary.md"

    if not metrics_file.exists():
        raise FileNotFoundError(f"offline_metrics.csv input not found: {metrics_file}")

    metrics = pd.read_csv(metrics_file)
    required = {"model_name", "k", "precision", "recall", "ndcg", "hit_rate", "coverage", "diversity"}
    missing = sorted(required - set(metrics.columns))
    if missing:
        raise ValueError(f"offline_metrics.csv missing required columns: {missing}")
    metrics_at_k = metrics[metrics["k"] == k].copy()
    if metrics_at_k.empty:
        raise ValueError(f"No metrics found for k={k}.")

    rows = []
    for variant in VARIANT_ORDER:
        row = _get_row(metrics_at_k, variant)
        if row is None:
            continue
        rows.append(
            {
                "variant": variant,
                "removed_module": REMOVED_MODULES[variant],
                "k": k,
                "precision": float(row["precision"]),
                "recall": float(row["recall"]),
                "ndcg": float(row["ndcg"]),
                "hit_rate": float(row["hit_rate"]),
                "coverage": float(row["coverage"]),
                "diversity": float(row["diversity"]),
                "main_observation": _observation(metrics_at_k, variant),
            }
        )

    if not rows:
        raise ValueError("No ablation variants could be generated.")
    ablation = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
    if ablation["main_observation"].isna().any() or (ablation["main_observation"].astype(str).str.len() == 0).any():
        raise ValueError("main_observation must not be empty.")

    output_path.mkdir(parents=True, exist_ok=True)
    ablation.to_csv(metrics_output, index=False)

    merged_obs = _observation(metrics_at_k, "ALS+ItemCF_Merged")
    xgb_obs = _observation(metrics_at_k, "XGBoost_Top50")
    mmr_obs = _observation(metrics_at_k, "XGBoost_MMR_Top10")
    summary = f"""# 消融实验说明

## 实验目的

对比 ALS、ItemCF、多路召回融合、XGBoost 精排和 MMR 重排在离线测试集上的表现，判断各模块对推荐效果的贡献。

## 对比模型

```text
ALS
ItemCF
ALS+ItemCF_Merged
XGBoost_Top50
XGBoost_MMR_Top10
```

## 核心指标表

{_markdown_table(ablation)}

## 多路召回效果分析

{merged_obs}

## XGBoost 精排效果分析

{xgb_obs}

## MMR 重排效果分析

{mmr_obs}

## 当前不足

MovieLens small 测试集每个用户只保留一条最新评分，且候选集正样本较少，因此 Precision、Recall、NDCG 的绝对值可能偏低。当前结果适合用于比较链路变化，不应直接等同于线上真实效果。

## 下一步优化方向

1. 扩展离线评估协议，例如留多法或时间窗口评估。
2. 调整 MMR 的 `lambda_rel`，观察相关性和多样性的权衡。
3. 在保持离线旁路的前提下增加推荐理由和前端评估页面。
"""
    summary_output.write_text(summary, encoding="utf-8")

    if not metrics_output.exists():
        raise RuntimeError(f"ablation_metrics.csv was not written: {metrics_output}")
    if not summary_output.exists():
        raise RuntimeError(f"ablation_summary.md was not written: {summary_output}")
    missing_variants = sorted(set(VARIANT_ORDER) - set(ablation["variant"]))
    if missing_variants:
        logger.warning("Some ablation variants were not available: %s", missing_variants)

    logger.info("ablation metrics output: %s", metrics_output)
    logger.info("ablation summary output: %s", summary_output)
    logger.info("variants: %s", list(ablation["variant"]))
    logger.info("quality validation result: success")
    return {
        "ablation_metrics_path": str(metrics_output),
        "ablation_summary_path": str(summary_output),
        "rows": int(len(ablation)),
        "variants": list(ablation["variant"]),
    }


def main() -> None:
    args = parse_args()
    try:
        build_ablation_eval(args.metrics, args.output_dir, args.k)
    except Exception as exc:
        logger.error("%s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
