"""Affiliate suggestion + click tracking schema.

Each Gap finding can have multiple AffiliateSuggestion rows — one per
provider product the user could buy to fill the gap. Click tracking is a
separate append-only table; we record a signed attribution token at create
time so revenue attribution can be reconciled later.

Provider integrations (Brands For Less, Ounass, Amazon affiliate, etc.) live
behind the AffiliateProvider Protocol in services/affiliate.py — the database
schema is deliberately provider-agnostic so we can add networks without
migrations.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at_col


class AffiliateProviderKind(enum.StrEnum):
    """Known affiliate networks. Add a value when wiring a new provider."""

    stub = "stub"
    brands_for_less = "brands_for_less"
    ounass = "ounass"
    amazon = "amazon"


class AffiliateSuggestion(Base):
    __tablename__ = "affiliate_suggestions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    gap_finding_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("gap_findings.id", ondelete="CASCADE"),
        index=True,
    )
    provider: Mapped[AffiliateProviderKind] = mapped_column(
        Enum(AffiliateProviderKind, name="affiliate_provider")
    )
    external_id: Mapped[str] = mapped_column(String(200))  # provider's product ID/SKU
    title: Mapped[str] = mapped_column(String(200))
    brand: Mapped[str | None] = mapped_column(String(120))
    image_url: Mapped[str | None] = mapped_column(String(1024))
    price_minor: Mapped[int | None] = mapped_column(Integer)  # AED fils, USD cents, etc.
    price_currency: Mapped[str | None] = mapped_column(String(3))  # ISO 4217
    affiliate_url: Mapped[str] = mapped_column(String(1024))
    # Signed attribution token — opaque to us; the provider can verify it on
    # callback. Stored so we can rotate signing keys without breaking history.
    attribution_token: Mapped[str | None] = mapped_column(String(255))

    created_at: Mapped[datetime] = created_at_col()


class AffiliateClick(Base):
    """Append-only click log for revenue reconciliation."""

    __tablename__ = "affiliate_clicks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    suggestion_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("affiliate_suggestions.id", ondelete="CASCADE"),
        index=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    user_agent: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = created_at_col()
