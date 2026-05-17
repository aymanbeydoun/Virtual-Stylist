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


class BasePhotoCommit(BaseModel):
    object_key: str
    owner_kind: OwnerKind = OwnerKind.user
    owner_id: uuid.UUID | None = None


class BasePhotoOut(BaseModel):
    base_photo_key: str | None


class TryonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    outfit_id: uuid.UUID
    base_photo_key: str
    rendered_image_key: str | None
    status: TryonStatus
    model_id: str | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None
