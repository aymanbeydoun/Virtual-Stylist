import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, created_at_col
from app.models.users import OwnerKind


class OutfitSource(enum.StrEnum):
    ai_generated = "ai_generated"
    user_saved = "user_saved"
    manual = "manual"


class OutfitSlot(enum.StrEnum):
    top = "top"
    bottom = "bottom"
    dress = "dress"
    outerwear = "outerwear"
    shoes = "shoes"
    accessory = "accessory"
    jewelry = "jewelry"


class OutfitEventKind(enum.StrEnum):
    worn = "worn"
    skipped = "skipped"
    regenerated = "regenerated"
    saved = "saved"


class Outfit(Base):
    __tablename__ = "outfits"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_kind: Mapped[OwnerKind] = mapped_column(
        Enum(OwnerKind, name="owner_kind", create_type=False)
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)

    source: Mapped[OutfitSource] = mapped_column(
        Enum(OutfitSource, name="outfit_source"), default=OutfitSource.ai_generated
    )
    destination: Mapped[str | None] = mapped_column(String(40))
    mood: Mapped[str | None] = mapped_column(String(40))
    weather_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    rationale: Mapped[str | None] = mapped_column(Text)
    model_id: Mapped[str | None] = mapped_column(String(120))
    confidence: Mapped[float | None] = mapped_column()
    accepted: Mapped[bool | None] = mapped_column(Boolean)
    composite_image_key: Mapped[str | None] = mapped_column(String(512))

    created_at: Mapped[datetime] = created_at_col()
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    items: Mapped[list["OutfitItem"]] = relationship(
        back_populates="outfit", cascade="all, delete-orphan"
    )
    events: Mapped[list["OutfitEvent"]] = relationship(
        back_populates="outfit", cascade="all, delete-orphan"
    )


class OutfitItem(Base):
    __tablename__ = "outfit_items"

    outfit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("outfits.id", ondelete="CASCADE"), primary_key=True
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wardrobe_items.id", ondelete="CASCADE"), primary_key=True
    )
    slot: Mapped[OutfitSlot] = mapped_column(Enum(OutfitSlot, name="outfit_slot"))

    outfit: Mapped[Outfit] = relationship(back_populates="items")


class OutfitEvent(Base):
    __tablename__ = "outfit_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    outfit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("outfits.id", ondelete="CASCADE"), index=True
    )
    event_kind: Mapped[OutfitEventKind] = mapped_column(
        Enum(OutfitEventKind, name="outfit_event_kind")
    )
    occurred_at: Mapped[datetime] = created_at_col()

    outfit: Mapped[Outfit] = relationship(back_populates="events")
