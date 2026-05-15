import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, SmallInteger, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, created_at_col


class FamilyMemberKind(enum.StrEnum):
    adult = "adult"
    teen = "teen"
    kid = "kid"


class ConsentMethod(enum.StrEnum):
    card_check = "card_check"
    signed_id = "signed_id"
    kba = "kba"


class FamilyMember(Base):
    __tablename__ = "family_members"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    guardian_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    display_name: Mapped[str] = mapped_column(String(60))
    kind: Mapped[FamilyMemberKind] = mapped_column(
        Enum(FamilyMemberKind, name="family_member_kind"), default=FamilyMemberKind.kid
    )
    birth_year: Mapped[int | None] = mapped_column(SmallInteger)
    kid_mode: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = created_at_col()
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    guardian: Mapped["object"] = relationship("User", back_populates="family_members")
    consents: Mapped[list["KidConsent"]] = relationship(
        back_populates="family_member", cascade="all, delete-orphan"
    )


class KidConsent(Base):
    __tablename__ = "kid_consents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("family_members.id", ondelete="CASCADE"), index=True
    )
    guardian_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    consent_method: Mapped[ConsentMethod] = mapped_column(
        Enum(ConsentMethod, name="consent_method")
    )
    granted_at: Mapped[datetime] = created_at_col()
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    family_member: Mapped[FamilyMember] = relationship(back_populates="consents")
