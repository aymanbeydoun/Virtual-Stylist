"""Virtual try-on renders.

One outfit can have multiple tryon renders — for retries, different base photos,
or future per-pose variants. Keeping them as a separate table (instead of a
single column on outfits) means we keep a history without rewriting the outfit
row, and renders can be invalidated independently of the outfit itself.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at_col


class TryonStatus(enum.StrEnum):
    pending = "pending"
    ready = "ready"
    failed = "failed"


class OutfitTryon(Base):
    __tablename__ = "outfit_tryons"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    outfit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("outfits.id", ondelete="CASCADE"), index=True
    )
    base_photo_key: Mapped[str] = mapped_column(String(512))
    rendered_image_key: Mapped[str | None] = mapped_column(String(512))
    status: Mapped[TryonStatus] = mapped_column(
        Enum(TryonStatus, name="tryon_status"), default=TryonStatus.pending
    )
    model_id: Mapped[str | None] = mapped_column(String(120))
    error_message: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = created_at_col()
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
