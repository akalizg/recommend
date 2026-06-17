"""Lightweight conversation memory for chat recommendation."""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ConversationTurn:
    role: str
    content: str
    intent: dict[str, Any] | None = None
    response_summary: str | None = None


class ConversationMemory:
    def __init__(self, max_turns: int = 6) -> None:
        self.max_turns = max_turns
        self._store: dict[int, deque[ConversationTurn]] = defaultdict(lambda: deque(maxlen=max_turns))
        self._last_intent: dict[int, dict[str, Any]] = {}

    def append_user(self, user_id: int, content: str) -> None:
        self._store[user_id].append(ConversationTurn(role="user", content=content))

    def append_assistant(self, user_id: int, content: str, response_summary: str | None = None) -> None:
        self._store[user_id].append(ConversationTurn(role="assistant", content=content, response_summary=response_summary))

    def append_intent(self, user_id: int, intent: dict[str, Any]) -> None:
        self._last_intent[user_id] = intent
        if self._store[user_id]:
            last = self._store[user_id][-1]
            if last.role == "user":
                last.intent = intent
                return
        self._store[user_id].append(ConversationTurn(role="user", content="", intent=intent))

    def get_turns(self, user_id: int) -> list[ConversationTurn]:
        return list(self._store.get(user_id, deque()))

    def get_last_intent(self, user_id: int) -> dict[str, Any] | None:
        return self._last_intent.get(user_id)

    def set_last_intent(self, user_id: int, intent: dict[str, Any]) -> None:
        self._last_intent[user_id] = intent

    def get_recent_context(self, user_id: int) -> str:
        turns = self.get_turns(user_id)
        if not turns:
            return ""
        lines = []
        for turn in turns[-self.max_turns :]:
            if turn.role == "user":
                lines.append(f"用户：{turn.content}")
            else:
                lines.append(f"助手：{turn.content}")
        return "\n".join(lines)
