from __future__ import annotations

from typing import Mapping


FALLBACK_TEMPLATE_REASON = "这道食谱和你的历史口味有一定匹配，适合加入备选菜单。"


def _text(value: object, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "<na>"}:
        return default
    return text


def _number(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _split_genres(value: object) -> list[str]:
    text = _text(value)
    if not text or text == "(no genres listed)":
        return []
    return [item.strip() for item in text.split("|") if item.strip()]


def build_template_reason(row: Mapping[str, object]) -> str:
    """Build a concise Chinese recommendation reason from available evidence."""
    favorite_genres = _split_genres(row.get("favorite_genres"))
    movie_genres = _split_genres(row.get("movie_genres") or row.get("genres"))
    matched = [genre for genre in movie_genres if genre in set(favorite_genres)]
    avg_rating = _number(row.get("movie_avg_rating"))
    genre_match_score = _number(row.get("genre_match_score"))

    if matched:
        reason = f"这道食谱带有你常选的{matched[0]}标签，和你的口味偏好比较匹配。"
    elif movie_genres:
        reason = f"这道食谱属于{movie_genres[0]}方向，适合作为新的用餐选择。"
    else:
        reason = FALLBACK_TEMPLATE_REASON

    if avg_rating >= 4.2:
        reason = reason.rstrip("。") + "，用户评分也很高。"
    elif avg_rating >= 3.8:
        reason = reason.rstrip("。") + "，整体评价较稳定。"
    elif genre_match_score >= 0.5 and not matched:
        reason = reason.rstrip("。") + "，标签匹配度较高。"

    return reason[:80] or FALLBACK_TEMPLATE_REASON


def generate_template_reason(row: Mapping[str, object]) -> dict[str, str]:
    reason = build_template_reason(row)
    return {
        "template_reason": reason,
        "llm_reason": "",
        "final_reason": reason,
        "reason_source": "template",
    }
