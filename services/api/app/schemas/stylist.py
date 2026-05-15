import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.users import OwnerKind
from app.schemas.wardrobe import WardrobeItemOut

Destination = Literal[
    "office", "date", "brunch", "gym", "playground", "school", "travel", "formal_event", "casual"
]
Mood = Literal["confident", "cozy", "edgy", "playful", "minimal", "romantic"]


class GenerateOutfitRequest(BaseModel):
    destination: Destination
    mood: Mood
    notes: str | None = Field(default=None, max_length=500)
    owner_kind: OwnerKind = OwnerKind.user
    owner_id: uuid.UUID | None = None


class OutfitItemOut(BaseModel):
    slot: str
    item: WardrobeItemOut


class OutfitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    destination: str | None
    mood: str | None
    rationale: str | None
    confidence: float | None
    composite_image_key: str | None
    items: list[OutfitItemOut]
    created_at: datetime


class GenerateOutfitResponse(BaseModel):
    outfits: list[OutfitOut]
    weather: dict | None = None
