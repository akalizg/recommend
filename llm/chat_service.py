"""LLM + KG recipe chat recommendation service."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from llm.conversation_memory import ConversationMemory
from llm.deepseek_client import chat_json, is_available
from llm.prompts import ENTITY_EXTRACTION_PROMPT, RECOMMENDATION_PROMPT
from llm.recipe_context import RecipeContextBuilder
from recall.kg_recall import KGRecall


@dataclass
class ChatRecommendationResult:
    intent: dict[str, Any]
    candidates: list[dict[str, Any]]
    response: dict[str, Any]
    llm_enabled: bool


class ChatRecommendationService:
    def __init__(self) -> None:
        self.kg = KGRecall()
        self.context_builder = RecipeContextBuilder()
        self.memory = ConversationMemory(max_turns=8)

    def close(self) -> None:
        self.kg.close()

    def _is_followup_question(self, message: str) -> bool:
        text = message.strip().lower()
        followup_keywords = ["再来", "再推荐", "再推荐两道", "多推荐", "换一批", "继续", "还有吗", "再给我", "多来几个", "加两道", "再来两道"]
        return any(keyword in message or keyword in text for keyword in followup_keywords)

    def _merge_intent(self, base: dict[str, Any] | None, delta: dict[str, Any]) -> dict[str, Any]:
        if not base:
            return delta
        merged = dict(base)
        for key in ["ingredients", "tags"]:
            base_items = list(merged.get(key) or [])
            delta_items = list(delta.get(key) or [])
            merged[key] = list(dict.fromkeys([*base_items, *delta_items]))
        for key in ["max_calories", "min_protein", "max_minutes"]:
            if delta.get(key) is not None:
                merged[key] = delta.get(key)
        if delta.get("intent_summary"):
            merged["intent_summary"] = delta.get("intent_summary")
        return self._normalize_intent(merged)

    def _extract_intent(self, message: str, user_id: int) -> dict[str, Any]:
        prompt = ENTITY_EXTRACTION_PROMPT.format(message=message)
        if is_available():
            try:
                intent = chat_json(prompt, temperature=0.0)
                return self._normalize_intent(intent)
            except Exception:
                pass
        return self._fallback_extract_intent(message, user_id)

    def _fallback_extract_intent(self, message: str, user_id: int) -> dict[str, Any]:
        text = message.lower()
        ingredients: list[str] = []
        tags: list[str] = []
        if "鸡" in message or "chicken" in text:
            ingredients.append("chicken")
        if "蛋" in message or "egg" in text:
            ingredients.append("egg")
        if "素" in message or "vegetarian" in text:
            tags.append("vegetarian")
        if "低卡" in message or "low calorie" in text:
            tags.append("healthy")
        if "快" in message or "quick" in text or "30" in text:
            tags.append("quick")
        if "晚餐" in message or "dinner" in text:
            tags.append("dinner")
        history = self.memory.get_recent_context(user_id)
        if "不要辣" in message or "no spicy" in text:
            tags.append("non-spicy")
        return {
            "ingredients": ingredients,
            "tags": tags,
            "max_calories": 700 if "低卡" in message else 1000,
            "min_protein": 15 if "高蛋白" in message else 0,
            "max_minutes": 30 if ("30" in text or "快" in message) else None,
            "intent_summary": f"基于关键词的兜底解析。{('参考上下文：' + history) if history else ''}".strip(),
        }

    @staticmethod
    def _normalize_intent(intent: dict[str, Any]) -> dict[str, Any]:
        return {
            "ingredients": [str(x).strip().lower() for x in intent.get("ingredients", []) if str(x).strip()],
            "tags": [str(x).strip().lower() for x in intent.get("tags", []) if str(x).strip()],
            "max_calories": intent.get("max_calories"),
            "min_protein": intent.get("min_protein"),
            "max_minutes": intent.get("max_minutes"),
            "intent_summary": intent.get("intent_summary", ""),
        }

    def _build_candidates(self, user_id: int, intent: dict[str, Any], top_n: int = 20) -> list[dict[str, Any]]:
        candidates = self.kg.hybrid_recall(
            ingredients=intent.get("ingredients") or [],
            tags=intent.get("tags") or [],
            max_calories=intent.get("max_calories"),
            min_protein=intent.get("min_protein"),
            top_n=max(top_n, 10),
        )
        items: list[dict[str, Any]] = []
        for recipe_id, score in candidates[:top_n]:
            title = self._get_title(recipe_id)
            items.append(
                {
                    "recipe_id": int(recipe_id),
                    "score": float(score),
                    "title": title,
                    "image_url": self._get_recipe_field(recipe_id, ["image_url", "poster_url", "backdrop_url"]),
                    "ready_in_display": self._get_recipe_field(recipe_id, ["ready_in_display", "runtime"]),
                    "rating_count": self._get_recipe_field(recipe_id, ["rating_count", "movie_rating_count"]),
                    "avg_rating": self._get_recipe_field(recipe_id, ["avg_rating", "movie_avg_rating"]),
                    "genres": self._get_recipe_field(recipe_id, ["genres", "movie_genres", "tags"]),
                    "movie_id": int(recipe_id),
                    "match_points": self._build_match_points(intent, recipe_id),
                    "context": self.context_builder.build_recipe_context([recipe_id], max_items=1),
                }
            )
        if not items:
            return self._fallback_candidates(user_id, top_n)
        return items

    def _fallback_candidates(self, user_id: int, top_n: int) -> list[dict[str, Any]]:
        recs = self.kg.hybrid_recall(top_n=top_n)
        items = []
        for recipe_id, score in recs:
            items.append(
                {
                    "recipe_id": int(recipe_id),
                    "score": float(score),
                    "title": self._get_title(recipe_id),
                    "match_points": ["fallback"],
                    "context": self.context_builder.build_recipe_context([recipe_id], max_items=1),
                }
            )
        return items

    def _build_match_points(self, intent: dict[str, Any], recipe_id: int) -> list[str]:
        points: list[str] = []
        title = self._get_title(recipe_id)
        if intent.get("ingredients"):
            points.extend(intent.get("ingredients", [])[:2])
        if intent.get("tags"):
            points.extend(intent.get("tags", [])[:2])
        if intent.get("max_calories") is not None:
            points.append(f"热量≤{intent['max_calories']}")
        if intent.get("min_protein") is not None:
            points.append(f"蛋白质≥{intent['min_protein']}")
        if title:
            points.append(title[:20])
        return list(dict.fromkeys(points))

    def _get_recipe_field(self, recipe_id: int, candidates: list[str]) -> Any:
        # 对话页图片只统一从 movie_profile.csv 读取，确保与推荐图源一致
        profile = self.context_builder.movie_profile
        if "movieId" not in profile.columns:
            return None
        row = profile[pd.to_numeric(profile["movieId"], errors="coerce") == recipe_id]
        if row.empty:
            return None
        for col in candidates:
            if col in row.columns:
                value = row.iloc[0].get(col)
                if value is not None and str(value).strip():
                    return value
        return None

    def _get_recipe_image(self, recipe_id: int) -> str | None:
        image = self._get_recipe_field(recipe_id, ["image_url"])
        return str(image) if image else None

    def _get_title(self, recipe_id: int) -> str:
        title = self._get_recipe_field(recipe_id, ["title", "name"])
        return str(title).strip() if title else f"Recipe {recipe_id}"

    def _build_llm_prompt(self, message: str, intent: dict[str, Any], candidates: list[dict[str, Any]], user_context: str) -> str:
        candidates = candidates[:10]
        candidates_text = "\n\n".join(
            [
                f"候选 {idx + 1}:\n{item['context']}\nscore: {item['score']:.4f}\nmatch_points: {', '.join(item['match_points'])}"
                for idx, item in enumerate(candidates)
            ]
        )
        return RECOMMENDATION_PROMPT.format(
            message=message,
            intent_json={**intent, "conversation_context": user_context},
            candidates_text=candidates_text,
        )

    def _normalize_response(self, response: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
        recs = response.get("recommendations", [])
        normalized = []
        for idx, item in enumerate(recs):
            if not isinstance(item, dict):
                continue
            rid = item.get("recipe_id")
            candidate = next((c for c in candidates if c["recipe_id"] == rid), candidates[min(idx, len(candidates) - 1)] if candidates else {})
            normalized.append(
                {
                    "recipe_id": int(rid or candidate.get("recipe_id", 0)),
                    "title": str(item.get("title") or candidate.get("title") or f"Recipe {rid}"),
                    "score": float(candidate.get("score", 0.0)),
                    "reason": str(item.get("reason") or "与用户意图和知识图谱条件匹配。"),
                    "match_points": item.get("match_points") if isinstance(item.get("match_points"), list) else candidate.get("match_points", []),
                }
            )
        if not normalized and candidates:
            for item in candidates[:5]:
                normalized.append(
                    {
                        "recipe_id": item["recipe_id"],
                        "title": item["title"],
                        "score": item["score"],
                        "reason": "与用户意图和知识图谱条件匹配。",
                        "match_points": item.get("match_points", []),
                    }
                )
        return {
            "summary": response.get("summary") or "已根据你的描述生成推荐结果。",
            "recommendations": normalized,
        }

    def _generate_response(self, message: str, intent: dict[str, Any], candidates: list[dict[str, Any]], user_context: str) -> dict[str, Any]:
        if not candidates:
            return {
                "summary": "没有找到足够匹配的菜谱，建议你换一种描述方式或补充更多条件。",
                "recommendations": [],
            }
        prompt = self._build_llm_prompt(message, intent, candidates, user_context)
        if is_available():
            try:
                response = chat_json(prompt, temperature=0.2)
                return self._normalize_response(response, candidates)
            except Exception:
                pass
        natural_reasons = [
            "这道菜的鸡胸肉做法比较直接，热量控制得住，同时蛋白质也能跟上，适合你要的低卡高蛋白方向。",
            "它不是那种重油重酱的做法，整体更清爽一些，但食材搭配还能保留一点风味。",
            "从营养目标看，这道菜更偏向高蛋白、低负担，比较适合当作正餐主菜。",
            "如果你想兼顾口感和控卡，它会比很多重口味做法更稳妥。",
            "这道菜属于比较实用的鸡胸肉方案，既不太寡淡，也不会偏离你的健康目标。",
        ]
        fallback_recs = []
        for idx, item in enumerate(candidates[:5]):
            fallback_recs.append(
                {
                    "recipe_id": item["recipe_id"],
                    "title": item["title"],
                    "reason": natural_reasons[idx % len(natural_reasons)],
                    "match_points": item.get("match_points", []),
                }
            )
        fallback_summary = intent.get("intent_summary") or "我给你挑了几款更贴合当前需求的菜谱，尽量兼顾风味、营养和做法难度。"
        return self._normalize_response(
            {
                "summary": fallback_summary,
                "recommendations": fallback_recs,
            },
            candidates,
        )

    def recommend(self, user_id: int, message: str, top_n: int = 20) -> ChatRecommendationResult:
        self.memory.append_user(user_id, message)
        user_context = self.memory.get_recent_context(user_id)
        extracted_intent = self._extract_intent(message, user_id)
        last_intent = self.memory.get_last_intent(user_id)
        if self._is_followup_question(message):
            intent = self._merge_intent(last_intent, extracted_intent)
            if last_intent:
                intent["intent_summary"] = f"基于上一轮条件继续推荐：{last_intent.get('intent_summary', '')}".strip()
        else:
            intent = extracted_intent
        self.memory.append_intent(user_id, intent)
        candidates = self._build_candidates(user_id, intent, top_n=top_n)
        if self._is_followup_question(message) and "再" in message:
            candidates = candidates[: max(5, min(top_n, len(candidates)))]
        response = self._generate_response(message, intent, candidates, user_context)
        self.memory.append_assistant(user_id, response.get("summary", ""), response.get("summary", ""))
        self.memory.set_last_intent(user_id, intent)
        return ChatRecommendationResult(
            intent=intent,
            candidates=candidates,
            response=response,
            llm_enabled=is_available(),
        )
