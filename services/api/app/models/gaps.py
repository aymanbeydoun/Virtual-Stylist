"""Closet-gap analysis: what's missing from the user's wardrobe.

A Gap represents an actionable hole — 'you don't own a versatile black belt' —
not a generic recommendation. Each gap has a slot, a description, a severity
and a status. Affiliate suggestions live in a follow-up table (deferred to
Phase 4) so the gap finding itself stays a clean diagnostic primitive.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at_col
from app.models.users import OwnerKind


class GapSeverity(enum.StrEnum):
    """High = wardrobe doesn't function without it. Low = nice-to-have."""

    high = "high"
    medium = "medium"
    low = "low"


class GapStatus(enum.StrEnum):
    open = "open"
    dismissed = "dismissed"
    resolved = "resolved"  # item added to closet that fills this gap


class GapFinding(Base):
    __tablename__ = "gap_findings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_kind: Mapped[OwnerKind] = mapped_column(
        Enum(OwnerKind, name="owner_kind", create_type=False)
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)

    slot: Mapped[str] = mapped_column(String(40))
    category_hint: Mapped[str | None] = mapped_column(String(80))
    title: Mapped[str] = mapped_column(String(200))
    rationale: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[GapSeverity] = mapped_column(Enum(GapSeverity, name="gap_severity"))
    status: Mapped[GapStatus] = mapped_column(
        Enum(GapStatus, name="gap_status"), default=GapStatus.open
    )

    # Optional: search query hint the affiliate worker (Phase 4) will turn into
    # an actual product lookup. Stored here so the gap is self-contained.
    search_query: Mapped[str | None] = mapped_column(String(200))

    created_at: Mapped[datetime] = created_at_col()
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
