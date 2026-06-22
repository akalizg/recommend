"""DeepSeek LLM client helpers.

Uses OpenAI-compatible DeepSeek API for entity extraction and recommendation generation.
Set DEEPSEEK_API_KEY in environment variables. If absent, callers should fall back to
rule-based parsing and template-style explanation generation.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - runtime dependency fallback
    OpenAI = None  # type: ignore[assignment]

DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
DEEPSEEK_API_KEY = "sk-6a2163270b6a476a851951e09aaa1487"
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")


def _build_client() -> OpenAI | None:
    if OpenAI is None:
        return None
    api_key = DEEPSEEK_API_KEY or os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        return None
    return OpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL)


@lru_cache(maxsize=1)
def get_client() -> OpenAI | None:
    return _build_client()


def is_available() -> bool:
    return get_client() is not None


def chat(prompt: str, temperature: float = 0.3, model: str | None = None) -> str:
    client = get_client()
    if client is None:
        raise RuntimeError("DeepSeek API is not configured. Set DEEPSEEK_API_KEY.")
    response = client.chat.completions.create(
        model=model or DEEPSEEK_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
    )
    return response.choices[0].message.content or ""


def _extract_json_block(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError(f"LLM output is not valid JSON: {text}")
    return stripped[start : end + 1]


def chat_json(prompt: str, temperature: float = 0.0, model: str | None = None) -> dict[str, Any]:
    text = chat(prompt, temperature=temperature, model=model)
    try:
        return json.loads(text)
    except Exception:
        try:
            return json.loads(_extract_json_block(text))
        except Exception as exc:
            raise ValueError(f"LLM output is not valid JSON: {text}") from exc
