"""Per-outfit conversation history for AI refinement.

The user can chat with the stylist about any outfit ("swap the bomber",
"make it less formal"). Each message becomes a row; the gateway reads the
full thread when generating the next refinement so context accumulates.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at_col


class MessageRole(enum.StrEnum):
    user = "user"
    assistant = "assistant"


class OutfitMessage(Base):
    __tablename__ = "outfit_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    outfit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("outfits.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[MessageRole] = mapped_column(Enum(MessageRole, name="message_role"))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_col()
