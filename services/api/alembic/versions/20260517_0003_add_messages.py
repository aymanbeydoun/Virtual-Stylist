"""add outfit_messages for per-outfit AI chat refinement"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260517_0003_messages"
down_revision: str | None = "20260517_0002_style"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    postgresql.ENUM("user", "assistant", name="message_role").create(
        op.get_bind(), checkfirst=True
    )
    role = postgresql.ENUM(
        "user", "assistant", name="message_role", create_type=False
    )
    op.create_table(
        "outfit_messages",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("outfit_id", sa.UUID(), nullable=False),
        sa.Column("role", role, nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["outfit_id"], ["outfits.id"], name=op.f("fk_outfit_messages_outfit_id_outfits"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_outfit_messages")),
    )
    op.create_index(
        op.f("ix_outfit_messages_outfit_id"), "outfit_messages", ["outfit_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_outfit_messages_outfit_id"), table_name="outfit_messages")
    op.drop_table("outfit_messages")
    sa.Enum(name="message_role").drop(op.get_bind(), checkfirst=True)
