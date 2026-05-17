"""Pydantic schemas for the gap-analysis API."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.gaps import GapSeverity, GapStatus
from app.models.users import OwnerKind


class GapAnalyseRequest(BaseModel):
    owner_kind: OwnerKind = OwnerKind.user
    owner_id: uuid.UUID | None = None


class GapFindingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slot: str
    category_hint: str | None
    title: str
    rationale: str | None
    severity: GapSeverity
    status: GapStatus
    search_query: str | None
    created_at: datetime
