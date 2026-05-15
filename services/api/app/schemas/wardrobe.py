import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.users import OwnerKind
from app.models.wardrobe import Pattern


class UploadUrlRequest(BaseModel):
    content_type: str = Field(default="image/jpeg")
    owner_kind: OwnerKind = OwnerKind.user
    owner_id: uuid.UUID | None = None


class UploadUrlResponse(BaseModel):
    upload_url: str
    object_key: str
    expires_at: datetime


class WardrobeItemCreate(BaseModel):
    object_key: str
    owner_kind: OwnerKind = OwnerKind.user
    owner_id: uuid.UUID | None = None


class ColorTag(BaseModel):
    name: str
    hex: str
    weight: float


class WardrobeItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_kind: OwnerKind
    owner_id: uuid.UUID
    raw_image_key: str
    cutout_image_key: str | None
    thumbnail_key: str | None
    category: str | None
    colors: list[ColorTag] = []
    pattern: Pattern | None
    formality: int | None
    seasonality: list[str] = []
    needs_review: bool
    status: str
    created_at: datetime


class ItemCorrectionIn(BaseModel):
    field: str
    new_value: str
