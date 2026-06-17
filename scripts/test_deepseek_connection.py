"""Quick DeepSeek connection test."""
from __future__ import annotations

import json

from llm.deepseek_client import is_available, chat, chat_json


def main() -> None:
    print(f"DeepSeek available: {is_available()}")
    if not is_available():
        print("DeepSeek API key not configured. Set DEEPSEEK_API_KEY and try again.")
        return

    prompt = "请用 JSON 返回：{\"hello\": \"world\", \"model\": \"deepseek\"}"
    try:
        raw = chat(prompt, temperature=0.0)
        print("RAW RESPONSE:")
        print(raw)
        parsed = chat_json(prompt, temperature=0.0)
        print("PARSED JSON:")
        print(json.dumps(parsed, ensure_ascii=False, indent=2))
    except Exception as exc:
        print(f"DeepSeek test failed: {exc}")


if __name__ == "__main__":
    main()
