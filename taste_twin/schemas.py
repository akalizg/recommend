from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class TasteTwinSettingsUpdate(BaseModel):
    is_discoverable: bool
    community_alias: Optional[str] = Field(default=None, max_length=48)
    preference_tags: List[str] = Field(default_factory=list, max_length=12)


class TasteTwinSettingsResponse(BaseModel):
    user_id: int
    is_discoverable: bool
    community_alias: Optional[str] = None
    preference_tags: List[str] = Field(default_factory=list)


class TasteTwinRecipe(BaseModel):
    movie_id: int
    title: str
    score: float = 0.0
    genres: str = ""
    avg_rating: Optional[float] = None
    rating_count: Optional[int] = None
    image_url: str = ""
    ready_in_display: str = ""
    recipe_yield_raw: str = ""
    author_name: str = ""
    user_rating: Optional[float] = None
    rated_at: Optional[int] = None
    is_collected: bool = False


class TwinMatchCard(BaseModel):
    user_id: int
    community_alias: str
    match_score: float = Field(..., ge=0.0, le=100.0)
    shared_tags: List[str] = Field(default_factory=list)
    top_preference_tags: List[str] = Field(default_factory=list)
    high_rated_recipes: List[TasteTwinRecipe] = Field(default_factory=list)
    low_rated_recipes: List[TasteTwinRecipe] = Field(default_factory=list)


class TwinProfileResponse(BaseModel):
    user_id: int
    community_alias: str
    match_score: Optional[float] = None
    top_preference_tags: List[str] = Field(default_factory=list)
    recommended_recipes: List[TasteTwinRecipe] = Field(default_factory=list)
    high_rated_recipes: List[TasteTwinRecipe] = Field(default_factory=list)
    low_rated_recipes: List[TasteTwinRecipe] = Field(default_factory=list)
    high_page: int
    low_page: int
    page_size: int
    high_total: int
    low_total: int
    high_has_more: bool
    low_has_more: bool


class CopyRecipeResponse(BaseModel):
    user_id: int
    movie_id: int
    copied: bool
    message: str


class JointMenuResponse(BaseModel):
    twin_user_id: int
    offset: int
    next_offset: int
    total_candidates: int
    recipes: List[TasteTwinRecipe] = Field(default_factory=list)


class DemoTwinsResponse(BaseModel):
    created: int
    discoverable_user_ids: List[int] = Field(default_factory=list)


class TasteTwinRecord(BaseModel):
    id: str
    user_id: int
    movie_id: int
    record_type: str
    label: str
    created_at: str
    feedback_value: Optional[float] = None
    recipe: TasteTwinRecipe


class TasteTwinRecordsResponse(BaseModel):
    user_id: int
    records: List[TasteTwinRecord] = Field(default_factory=list)
    page: int
    page_size: int
    total: int
    has_more: bool


class TasteTwinRecordMutationResponse(BaseModel):
    user_id: int
    record_id: str
    deleted: bool
    message: str
