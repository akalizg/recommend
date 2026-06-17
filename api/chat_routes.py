"""Chat-based recommendation API."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from llm.chat_service import ChatRecommendationService

router = APIRouter(prefix="/chat", tags=["chat"])
_service: ChatRecommendationService | None = None


def get_chat_service() -> ChatRecommendationService:
    global _service
    if _service is None:
        _service = ChatRecommendationService()
    return _service


class ChatRequest(BaseModel):
    user_id: int = Field(..., description="Logged-in recipe user id")
    message: str = Field(..., description="User natural language request")


@router.post("/recommend")
async def chat_recommend(request: ChatRequest):
    try:
        result = get_chat_service().recommend(request.user_id, request.message, top_n=20)
        return {
            "summary": result.response.get("summary", ""),
            "recommendations": result.response.get("recommendations", []),
            "intent": result.intent,
            "llm_enabled": result.llm_enabled,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
