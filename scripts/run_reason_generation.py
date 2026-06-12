from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from reason.generate_reasons import DEFAULT_OUTPUT, generate_reasons, parse_bool
from reason.llm_reason_generator import DEFAULT_LOCAL_LLM_PATH


logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local Qwen recommendation reason generation.")
    parser.add_argument("--use-llm", default="true", choices=["true", "false"], help="Whether to use local Qwen.")
    parser.add_argument("--model-path", default=DEFAULT_LOCAL_LLM_PATH, help="Local Qwen model directory.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output recommendations_with_reasons CSV.")
    parser.add_argument("--limit", type=int, default=None, help="Optional row limit for smoke runs.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    use_llm = parse_bool(args.use_llm)
    model_path = Path(args.model_path)

    logger.info("是否启用 LLM/Qwen: %s", use_llm)
    logger.info("本地模型路径: %s", model_path)
    logger.info("模型路径是否存在: %s", model_path.exists())

    summary = generate_reasons(
        use_llm=use_llm,
        model_path=str(model_path),
        output_path=args.output,
        limit=args.limit,
    )
    qwen_status = summary["qwen_status"]

    logger.info("是否成功加载 Qwen: %s", qwen_status["model_loaded"])
    logger.info("使用设备: %s", qwen_status["device"])
    if qwen_status["load_error"]:
        logger.info("失败原因: %s", qwen_status["load_error"])
    logger.info("是否回退模板: %s", summary["fallback_to_template"])
    logger.info("recommendations_with_reasons.csv 行数: %s", summary["output_rows"])
    logger.info("reason_source 分布: %s", summary["reason_source_distribution"])
    logger.info("输出文件: %s", summary["output_path"])
    logger.info("推荐理由示例 10 条:")
    for index, sample in enumerate(summary["samples"], start=1):
        logger.info(
            "%s. userId=%s movieId=%s title=%s source=%s reason=%s",
            index,
            sample.get("userId"),
            sample.get("movieId"),
            sample.get("movie_title"),
            sample.get("reason_source"),
            sample.get("final_reason"),
        )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        logger.error("%s", exc)
        sys.exit(1)
