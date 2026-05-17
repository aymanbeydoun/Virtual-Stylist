import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.users import OwnerKind
from app.schemas.common import WeatherSnapshot
from app.schemas.wardrobe import WardrobeItemOut

Destination = Literal[
    "office", "date", "brunch", "gym", "playground", "school",
    "travel", "formal_event", "casual", "mall",
]
Mood = Literal["confident", "cozy", "edgy", "playful", "minimal", "romantic"]
# Aesthetic / style preference — orthogonal to mood (emotional state). Mood is
# 'how I want to feel', Style is 'what tradition/era I'm dressing within'.
Style = Literal[
    "streetwear",
    "minimal",
    "classic",
    "preppy",
    "bohemian",
    "athleisure",
    "avant_garde",
    "smart_casual",
]


class GenerateOutfitRequest(BaseModel):
    destination: Destination
    mood: Mood | None = None
    style: Style | None = None
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
    style: str | None = None
    rationale: str | None
    confidence: float | None
    composite_image_key: str | None
    items: list[OutfitItemOut]
    created_at: datetime


class GenerateOutfitResponse(BaseModel):
    outfits: list[OutfitOut]
    weather: WeatherSnapshot | None = None
