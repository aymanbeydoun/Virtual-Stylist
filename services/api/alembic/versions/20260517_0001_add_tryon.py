"""add base_photo_key + outfit_tryons table

Virtual try-on schema: a per-profile base photo (uploaded once, reused for every
render) and an outfit_tryons history table (one outfit can have multiple renders
without rewriting the outfit row).
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260517_0001_tryon"
down_revision: str | None = "d10619eaa951"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("base_photo_key", sa.String(length=512), nullable=True))
    op.add_column(
        "family_members", sa.Column("base_photo_key", sa.String(length=512), nullable=True)
    )

    postgresql.ENUM(
        "pending", "ready", "failed", name="tryon_status"
    ).create(op.get_bind(), checkfirst=True)
    tryon_status = postgresql.ENUM(
        "pending", "ready", "failed", name="tryon_status", create_type=False
    )

    op.create_table(
        "outfit_tryons",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("outfit_id", sa.UUID(), nullable=False),
        sa.Column("base_photo_key", sa.String(length=512), nullable=False),
        sa.Column("rendered_image_key", sa.String(length=512), nullable=True),
        sa.Column("status", tryon_status, nullable=False),
        sa.Column("model_id", sa.String(length=120), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["outfit_id"], ["outfits.id"], name=op.f("fk_outfit_tryons_outfit_id_outfits"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_outfit_tryons")),
    )
    op.create_index(
        op.f("ix_outfit_tryons_outfit_id"), "outfit_tryons", ["outfit_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_outfit_tryons_outfit_id"), table_name="outfit_tryons")
    op.drop_table("outfit_tryons")
    sa.Enum(name="tryon_status").drop(op.get_bind(), checkfirst=True)
    op.drop_column("family_members", "base_photo_key")
    op.drop_column("users", "base_photo_key")
