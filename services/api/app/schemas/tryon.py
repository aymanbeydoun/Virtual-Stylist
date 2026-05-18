"""Schemas for the base-photo + try-on endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.tryons import TryonStatus
from app.models.users import OwnerKind


class BasePhotoUploadUrlRequest(BaseModel):
    content_type: str = Field(default="image/jpeg")
    owner_kind: OwnerKind = OwnerKind.user
    owner_id: uuid.UUID | None = None


class BasePhotoUploadUrlResponse(BaseModel):
    upload_url: str
    object_key: str
    expires_at: datetime


# The four base-photo angles we render. Order matters — this is the playback
# order in the mobile carousel: front → 3/4-left → back → 3/4-right → loop.
ANGLES = ("front", "left_3q", "back", "right_3q")
Angle = str  # constrained at runtime via ANGLES; keeping str loose for JSON dicts


class BasePhotoCommit(BaseModel):
    object_key: str
    owner_kind: OwnerKind = OwnerKind.user
    owner_id: uuid.UUID | None = None
    # When set, the photo is filed under this angle in `base_photo_keys`.
    # When None, behaves like the legacy single-photo upload (writes to
    # `base_photo_key` and mirrors as "front" in the dict).
    angle: str | None = None


class BasePhotoOut(BaseModel):
    """Single-photo view kept for back-compat with the old mobile flow."""

    base_photo_key: str | None


class BasePhotoSetOut(BaseModel):
    """Multi-angle view — returns every uploaded angle keyed by ANGLES."""

    base_photo_keys: dict[str, str] = Field(default_factory=dict)


class TryonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    outfit_id: uuid.UUID
    base_photo_key: str
    angle: str | None = None
    rendered_image_key: str | None
    status: TryonStatus
    model_id: str | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None


class TryonSetOut(BaseModel):
    """All renders for a single try-on request, one per angle."""

    renders: list[TryonOut]
