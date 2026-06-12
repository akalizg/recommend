from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path
from typing import Mapping

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from reason.template_reason_generator import build_template_reason


DEFAULT_LOCAL_LLM_PATH = r"D:\Javatest\pythonweb\movierec\qwen_model"

logger = logging.getLogger(__name__)


PROMPT_TEMPLATE = """你是电影推荐系统的解释模块。请根据给定的用户偏好、电影特征和推荐证据，生成一句简洁、可信、自然的中文推荐理由。

要求：
1. 不要编造导演、演员、剧情等没有提供的信息。
2. 不要超过 60 个中文字符。
3. 不要出现“模型分数”“数据字段”“召回通道”等技术词。
4. 只输出推荐理由本身，不要输出解释过程。
5. 理由要让普通用户能看懂。

用户偏好类型：{favorite_genres}
电影类型：{movie_genres}
电影平均评分：{movie_avg_rating}
类型匹配度：{genre_match_score}
基础理由：{template_reason}

推荐理由："""

SYSTEM_PROMPT = "你是一个电影推荐系统的推荐理由生成助手。"
FALLBACK_REASON = "这部电影和你的历史偏好有一定匹配，值得一看。"

FORBIDDEN_TECHNICAL_TERMS = (
    "模型分数",
    "数据字段",
    "召回通道",
    "rank_score",
    "mmr_score",
    "genre_match_score",
)
UNSUPPORTED_FACT_TERMS = ("导演", "演员", "主演", "剧情")


class QwenReasonGenerator:
    """Generate recommendation reasons with a local Qwen model, falling back safely."""

    def __init__(self, model_path: str | Path | None = None) -> None:
        self.model_path = str(model_path or DEFAULT_LOCAL_LLM_PATH)
        self.tokenizer = None
        self.model = None
        self.load_attempted = False
        self.load_error = ""
        self.device = "unknown"

    @property
    def model_path_exists(self) -> bool:
        return Path(self.model_path).exists()

    @property
    def model_loaded(self) -> bool:
        return self.model is not None and self.tokenizer is not None

    def status(self) -> dict[str, object]:
        return {
            "model_path": self.model_path,
            "model_path_exists": self.model_path_exists,
            "load_attempted": self.load_attempted,
            "model_loaded": self.model_loaded,
            "device": self.device,
            "load_error": self.load_error,
        }

    def load_model(self) -> bool:
        if self.load_attempted:
            return self.model_loaded

        self.load_attempted = True
        model_dir = Path(self.model_path)
        if not model_dir.exists():
            self.load_error = f"Local Qwen model path does not exist: {model_dir}"
            logger.warning(self.load_error)
            return False

        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except Exception as exc:  # pragma: no cover - depends on local environment
            self.load_error = f"transformers is unavailable: {exc}"
            logger.exception("Failed to import transformers; falling back to template reasons.")
            return False

        try:
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_path,
                trust_remote_code=True,
                local_files_only=True,
            )
            self.model = self._load_causal_lm(AutoModelForCausalLM)
            self.model.eval()
            self.device = self._detect_device()
            logger.info("Loaded local Qwen model from %s on %s", self.model_path, self.device)
            return True
        except Exception as exc:
            self.tokenizer = None
            self.model = None
            self.load_error = f"{type(exc).__name__}: {exc}"
            logger.exception("Failed to load local Qwen model; falling back to template reasons.")
            return False

    def _load_causal_lm(self, model_cls):
        torch = _try_import_torch()
        if torch is not None and not torch.cuda.is_available():
            return model_cls.from_pretrained(
                self.model_path,
                torch_dtype="auto",
                trust_remote_code=True,
                local_files_only=True,
            )

        try:
            return model_cls.from_pretrained(
                self.model_path,
                torch_dtype="auto",
                device_map="auto",
                trust_remote_code=True,
                local_files_only=True,
            )
        except Exception as first_exc:
            logger.warning(
                "Qwen load with device_map=auto failed, retrying local CPU-compatible load: %s",
                first_exc,
            )
            return model_cls.from_pretrained(
                self.model_path,
                torch_dtype="auto",
                trust_remote_code=True,
                local_files_only=True,
            )

    def _detect_device(self) -> str:
        if self.model is None:
            return "unknown"

        hf_device_map = getattr(self.model, "hf_device_map", None)
        if isinstance(hf_device_map, dict) and hf_device_map:
            devices = {str(device) for device in hf_device_map.values()}
            if any("cuda" in device.lower() or device.isdigit() for device in devices):
                return "gpu"
            if any("cpu" in device.lower() for device in devices):
                return "cpu"
            return ",".join(sorted(devices))

        device = getattr(self.model, "device", None)
        if device is not None:
            return _normalize_device(str(device))

        try:
            return _normalize_device(str(next(self.model.parameters()).device))
        except Exception:
            return "unknown"

    def generate(self, row: Mapping[str, object], use_llm: bool = True) -> dict[str, str]:
        template_reason = _text(row.get("template_reason")) or build_template_reason(row)
        if not use_llm:
            return _template_result(template_reason)

        if not self.load_model():
            return _template_result(template_reason)

        try:
            prompt = _build_prompt(row, template_reason)
            raw_response = self._generate_raw(prompt)
            llm_reason = clean_llm_reason(raw_response)
            if not is_valid_reason(llm_reason, row):
                return _template_result(template_reason)
            return {
                "llm_reason": llm_reason,
                "final_reason": llm_reason,
                "reason_source": "qwen",
            }
        except Exception as exc:
            self.load_error = f"generation failed: {type(exc).__name__}: {exc}"
            logger.exception("Qwen generation failed; falling back to template reason.")
            return _template_result(template_reason)

    def _generate_raw(self, prompt: str) -> str:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        if hasattr(self.tokenizer, "apply_chat_template"):
            text = self.tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )
        else:
            text = prompt

        inputs = self.tokenizer([text], return_tensors="pt")
        target_device = getattr(self.model, "device", None)
        if target_device is None:
            try:
                target_device = next(self.model.parameters()).device
            except Exception:
                target_device = None
        if target_device is not None and hasattr(inputs, "to"):
            inputs = inputs.to(target_device)

        outputs = self.model.generate(
            **inputs,
            max_new_tokens=60,
            do_sample=False,
            repetition_penalty=1.1,
        )
        input_length = inputs.input_ids.shape[-1]
        return self.tokenizer.decode(outputs[0][input_length:], skip_special_tokens=True)


def _normalize_device(device: str) -> str:
    lowered = device.lower()
    if "cuda" in lowered:
        return "gpu"
    if "cpu" in lowered:
        return "cpu"
    return device


def _try_import_torch():
    try:
        import torch

        return torch
    except Exception:
        return None


def _text(value: object, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "<na>"}:
        return default
    return text


def _template_result(template_reason: str) -> dict[str, str]:
    reason = (_text(template_reason) or FALLBACK_REASON)[:80]
    return {
        "llm_reason": "",
        "final_reason": reason,
        "reason_source": "template",
    }


def _build_prompt(row: Mapping[str, object], template_reason: str) -> str:
    return PROMPT_TEMPLATE.format(
        favorite_genres=_text(row.get("favorite_genres"), "未知"),
        movie_genres=_text(row.get("movie_genres") or row.get("genres"), "未知"),
        movie_avg_rating=_text(row.get("movie_avg_rating"), "未知"),
        genre_match_score=_text(row.get("genre_match_score"), "未知"),
        template_reason=template_reason,
    )


def clean_llm_reason(text: object) -> str:
    cleaned = _text(text)
    cleaned = re.sub(r"[\r\n\t]+", "，", cleaned)
    cleaned = re.sub(r"\s+", "", cleaned)
    cleaned = cleaned.strip(" \"'“”‘’")
    cleaned = re.sub(r"^(推荐理由|理由|回答|输出)[:：]", "", cleaned)
    cleaned = cleaned.strip(" \"'“”‘’")
    return cleaned[:80]


def is_valid_reason(reason: str, row: Mapping[str, object] | None = None) -> bool:
    if not reason:
        return False
    if len(reason) > 80:
        return False
    if not re.search(r"[\u4e00-\u9fff]", reason):
        return False
    if any(term.lower() in reason.lower() for term in FORBIDDEN_TECHNICAL_TERMS):
        return False

    row = row or {}
    evidence_text = " ".join(
        _text(row.get(key))
        for key in ("director", "actors", "cast", "plot", "overview", "description")
    ).strip()
    if not evidence_text and any(term in reason for term in UNSUPPORTED_FACT_TERMS):
        return False

    if _has_obvious_repetition(reason):
        return False

    chinese_chars = re.findall(r"[\u4e00-\u9fff]", reason)
    if len(chinese_chars) < 6:
        return False

    return True


def _has_obvious_repetition(text: str) -> bool:
    compact = re.sub(r"[，。！？、,.!?;；\s]", "", text)
    if re.search(r"(.{2,8})\1{2,}", compact):
        return True

    tokens = re.split(r"[，。！？、,.!?;；]", text)
    tokens = [token for token in tokens if token]
    return len(tokens) >= 3 and len(set(tokens)) <= max(1, len(tokens) // 2)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate one sample recommendation reason with local Qwen.")
    parser.add_argument("--model-path", default=DEFAULT_LOCAL_LLM_PATH, help="Local Qwen model directory.")
    parser.add_argument("--use-llm", default="true", choices=["true", "false"], help="Whether to use local Qwen.")
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    args = parse_args()
    row = {
        "favorite_genres": "Drama|Comedy",
        "movie_genres": "Drama|Romance",
        "movie_avg_rating": 4.1,
        "genre_match_score": 0.5,
    }
    row["template_reason"] = build_template_reason(row)
    generator = QwenReasonGenerator(args.model_path)
    result = generator.generate(row, use_llm=args.use_llm == "true")
    print({**generator.status(), **result})


if __name__ == "__main__":
    main()
