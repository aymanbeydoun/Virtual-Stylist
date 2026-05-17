import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.users import OwnerKind
from app.models.wardrobe import Pattern
from app.schemas.common import ColorTag

__all__ = [
    "ClosetInsights",
    "ColorTag",
    "ItemCorrectionIn",
    "ScanItemsRequest",
    "ScanItemsResponse",
    "ScanRegion",
    "StaleItem",
    "UploadUrlRequest",
    "UploadUrlResponse",
    "WardrobeItemCreate",
    "WardrobeItemOut",
    "WardrobeItemsBulkCreate",
]


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
    attributes: dict[str, object] = {}
    quality_tier: str = "standard"
    needs_review: bool
    status: str
    failure_reason: str | None = None
    created_at: datetime


class ItemCorrectionIn(BaseModel):
    field: str
    new_value: str


class ScanItemsRequest(BaseModel):
    """Request to run SAM 2 over an uploaded photo to find multiple garments."""

    object_key: str
    owner_kind: OwnerKind = OwnerKind.user
    owner_id: uuid.UUID | None = None


class ScanRegion(BaseModel):
    """One garment region detected by SAM 2."""

    preview_key: str  # storage key for the per-garment preview PNG
    bbox: list[int]  # [x, y, w, h] in source-image pixels
    label: str | None = None  # SAM 2 doesn't label; reserved for future


class ScanItemsResponse(BaseModel):
    regions: list[ScanRegion]


class WardrobeItemsBulkCreate(BaseModel):
    """Create N items from user-confirmed SAM 2 regions."""

    object_keys: list[str] = Field(min_length=1, max_length=12)
    owner_kind: OwnerKind = OwnerKind.user
    owner_id: uuid.UUID | None = None


class StaleItem(BaseModel):
    """One closet item the user hasn't worn in a long time."""

    item_id: uuid.UUID
    category: str | None
    thumbnail_key: str | None
    last_worn_at: datetime | None
    days_unworn: int  # days since last worn, or days since added when never worn


class ClosetInsights(BaseModel):
    """Aggregate health signals over the user's closet."""

    total_items: int
    worn_items: int  # items that have at least one 'worn' event
    never_worn_items: int  # in closet for >14 days, never worn
    stale_items: list[StaleItem]  # not worn in 60+ days, top 10
    overcrowded_categories: list[dict[str, object]]  # [{category, count, threshold}]
    underused_categories: list[dict[str, object]]  # categories you have but never wear
