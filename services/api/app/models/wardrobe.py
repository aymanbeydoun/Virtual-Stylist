import enum
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.json_types import PydanticJSON
from app.models.base import Base, created_at_col
from app.models.users import OwnerKind
from app.schemas.common import ColorTag, ConfidenceScores


class Pattern(enum.StrEnum):
    solid = "solid"
    stripe = "stripe"
    floral = "floral"
    graphic = "graphic"
    plaid = "plaid"
    other = "other"


class WardrobeItem(Base):
    __tablename__ = "wardrobe_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_kind: Mapped[OwnerKind] = mapped_column(
        Enum(OwnerKind, name="owner_kind", create_type=False)
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)

    raw_image_key: Mapped[str] = mapped_column(String(512))
    cutout_image_key: Mapped[str | None] = mapped_column(String(512))
    thumbnail_key: Mapped[str | None] = mapped_column(String(512))

    category: Mapped[str | None] = mapped_column(String(120), index=True)
    subcategory_path: Mapped[str | None] = mapped_column(String(255))
    colors: Mapped[list[ColorTag]] = mapped_column(
        PydanticJSON(list[ColorTag]), default=list
    )
    pattern: Mapped[Pattern | None] = mapped_column(Enum(Pattern, name="pattern"))
    formality: Mapped[int | None] = mapped_column(SmallInteger)
    seasonality: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    material_guess: Mapped[str | None] = mapped_column(String(60))

    embedding: Mapped[list[float] | None] = mapped_column(Vector(768))
    confidence_scores: Mapped[ConfidenceScores] = mapped_column(
        PydanticJSON(ConfidenceScores), default=lambda: ConfidenceScores(root={})
    )
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)
    coppa_protected: Mapped[bool] = mapped_column(Boolean, default=False)

    status: Mapped[str] = mapped_column(String(20), default="pending")

    created_at: Mapped[datetime] = created_at_col()
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    corrections: Mapped[list["ItemCorrection"]] = relationship(
        back_populates="item", cascade="all, delete-orphan"
    )


class ItemCorrection(Base):
    __tablename__ = "item_corrections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wardrobe_items.id", ondelete="CASCADE"), index=True
    )
    field: Mapped[str] = mapped_column(String(60))
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str] = mapped_column(Text)
    corrected_at: Mapped[datetime] = created_at_col()

    item: Mapped[WardrobeItem] = relationship(back_populates="corrections")
