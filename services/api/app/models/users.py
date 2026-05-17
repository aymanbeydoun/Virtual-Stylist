import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Enum, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.json_types import PydanticJSON
from app.models.base import Base, created_at_col, updated_at_col
from app.schemas.common import SizeMap

if TYPE_CHECKING:
    from app.models.family import FamilyMember
    from app.models.outfits import Outfit
    from app.models.wardrobe import WardrobeItem


class UserRole(enum.StrEnum):
    adult = "adult"
    guardian = "guardian"


class OwnerKind(enum.StrEnum):
    user = "user"
    family_member = "family_member"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    auth_provider_id: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"), default=UserRole.adult)
    display_name: Mapped[str | None] = mapped_column(String(120))
    locale: Mapped[str] = mapped_column(String(10), default="en-US")
    birth_year: Mapped[int | None] = mapped_column(SmallInteger)
    base_photo_key: Mapped[str | None] = mapped_column(String(512))

    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    family_members: Mapped[list["FamilyMember"]] = relationship(
        back_populates="guardian", cascade="all, delete-orphan"
    )
    wardrobe_items: Mapped[list["WardrobeItem"]] = relationship(
        primaryjoin=(
            "and_(User.id == foreign(WardrobeItem.owner_id), "
            "WardrobeItem.owner_kind == 'user')"
        ),
        viewonly=True,
    )
    outfits: Mapped[list["Outfit"]] = relationship(
        primaryjoin=(
            "and_(User.id == foreign(Outfit.owner_id), Outfit.owner_kind == 'user')"
        ),
        viewonly=True,
    )


class StyleProfile(Base):
    __tablename__ = "style_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_kind: Mapped[OwnerKind] = mapped_column(Enum(OwnerKind, name="owner_kind"))
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)

    sizes: Mapped[SizeMap] = mapped_column(
        PydanticJSON(SizeMap), default=lambda: SizeMap(root={})
    )
    style_vector: Mapped[list[float] | None] = mapped_column(Vector(768))
    preferred_colors: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    disliked_categories: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    notes: Mapped[str | None] = mapped_column(Text)
    # Aesthetic default applied to every stylist call unless the per-request
    # `style` field overrides it. Free-text rather than enum so we can evolve
    # the taxonomy without migrations.
    preferred_style: Mapped[str | None] = mapped_column(String(40))

    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()
