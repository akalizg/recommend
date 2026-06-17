from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.routes import get_state
from .schemas import (
    CopyRecipeResponse,
    DemoTwinsResponse,
    JointMenuResponse,
    TasteTwinRecordMutationResponse,
    TasteTwinRecordsResponse,
    TasteTwinSettingsResponse,
    TasteTwinSettingsUpdate,
    TwinMatchCard,
    TwinProfileResponse,
)
from .service import TasteTwinService

router = APIRouter(prefix="/taste-twin", tags=["Taste Twin"])


def get_taste_twin_service(state=Depends(get_state)) -> TasteTwinService:
    service = getattr(state, "taste_twin_service", None)
    if service is None:
        from taste_twin.service import TasteTwinService
        service = TasteTwinService.create_default()
        setattr(state, "taste_twin_service", service)
        asyncio.create_task(asyncio.to_thread(service.initialize))
    return service


@router.get("/settings/{user_id}", response_model=TasteTwinSettingsResponse)
async def taste_twin_settings(user_id: int, service: TasteTwinService = Depends(get_taste_twin_service)) -> TasteTwinSettingsResponse:
    return await service.get_settings(user_id)


@router.patch("/settings/{user_id}", response_model=TasteTwinSettingsResponse)
async def update_taste_twin_settings(user_id: int, payload: TasteTwinSettingsUpdate, service: TasteTwinService = Depends(get_taste_twin_service)) -> TasteTwinSettingsResponse:
    return await service.update_settings(user_id, payload)


@router.get("/{user_id}/matches", response_model=list[TwinMatchCard])
async def taste_twin_matches(user_id: int, limit: int = Query(default=10, ge=1, le=20), service: TasteTwinService = Depends(get_taste_twin_service)) -> list[TwinMatchCard]:
    return await service.match_twins(user_id, limit)


@router.get("/{user_id}/profiles/{twin_user_id}", response_model=TwinProfileResponse)
async def taste_twin_profile(
    user_id: int,
    twin_user_id: int,
    high_page: int = Query(default=1, ge=1),
    low_page: int = Query(default=1, ge=1),
    page_size: int = Query(default=12, ge=1, le=12),
    service: TasteTwinService = Depends(get_taste_twin_service),
) -> TwinProfileResponse:
    return await service.get_profile(user_id, twin_user_id, high_page, low_page, page_size)


@router.post("/{user_id}/copy/{movie_id}", response_model=CopyRecipeResponse)
async def copy_taste_twin_recipe(user_id: int, movie_id: int, service: TasteTwinService = Depends(get_taste_twin_service)) -> CopyRecipeResponse:
    return await service.copy_recipe(user_id, movie_id)


@router.get("/{user_id}/joint-menu/{twin_user_id}", response_model=JointMenuResponse)
async def taste_twin_joint_menu(user_id: int, twin_user_id: int, offset: int = Query(default=0, ge=0), service: TasteTwinService = Depends(get_taste_twin_service)) -> JointMenuResponse:
    return await service.joint_menu(user_id, twin_user_id, offset)


@router.post("/{user_id}/demo-twins", response_model=DemoTwinsResponse)
async def create_demo_taste_twins(user_id: int, count: int = Query(default=5, ge=1, le=10), service: TasteTwinService = Depends(get_taste_twin_service)) -> DemoTwinsResponse:
    return await service.create_demo_twins(user_id, count)


@router.get("/{user_id}/records", response_model=TasteTwinRecordsResponse)
async def taste_twin_records(
    user_id: int,
    record_type: str = Query(default="all", pattern="^(all|collection|like|dislike|not_interested|rating)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=12, ge=1, le=24),
    service: TasteTwinService = Depends(get_taste_twin_service),
) -> TasteTwinRecordsResponse:
    return await service.get_records(user_id, record_type, page, page_size)


@router.delete("/{user_id}/records", response_model=TasteTwinRecordMutationResponse)
async def delete_taste_twin_record(
    user_id: int,
    record_id: str = Query(..., min_length=1),
    service: TasteTwinService = Depends(get_taste_twin_service),
) -> TasteTwinRecordMutationResponse:
    return await service.delete_record(user_id, record_id)
