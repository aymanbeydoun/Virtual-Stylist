"""Schemas for the affiliate suggestion + click endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.affiliate import AffiliateProviderKind


class AffiliateSuggestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    gap_finding_id: uuid.UUID
    provider: AffiliateProviderKind
    external_id: str
    title: str
    brand: str | None
    image_url: str | None
    price_minor: int | None
    price_currency: str | None
    affiliate_url: str
    created_at: datetime
