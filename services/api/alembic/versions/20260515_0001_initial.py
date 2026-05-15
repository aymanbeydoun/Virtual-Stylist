"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-15

"""
from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    user_role = postgresql.ENUM("adult", "guardian", name="user_role")
    user_role.create(op.get_bind(), checkfirst=True)
    owner_kind = postgresql.ENUM("user", "family_member", name="owner_kind")
    owner_kind.create(op.get_bind(), checkfirst=True)
    fam_kind = postgresql.ENUM("adult", "teen", "kid", name="family_member_kind")
    fam_kind.create(op.get_bind(), checkfirst=True)
    consent_method = postgresql.ENUM("card_check", "signed_id", "kba", name="consent_method")
    consent_method.create(op.get_bind(), checkfirst=True)
    pattern = postgresql.ENUM(
        "solid", "stripe", "floral", "graphic", "plaid", "other", name="pattern"
    )
    pattern.create(op.get_bind(), checkfirst=True)
    outfit_source = postgresql.ENUM(
        "ai_generated", "user_saved", "manual", name="outfit_source"
    )
    outfit_source.create(op.get_bind(), checkfirst=True)
    outfit_slot = postgresql.ENUM(
        "top", "bottom", "dress", "outerwear", "shoes", "accessory", "jewelry", name="outfit_slot"
    )
    outfit_slot.create(op.get_bind(), checkfirst=True)
    outfit_event_kind = postgresql.ENUM(
        "worn", "skipped", "regenerated", "saved", name="outfit_event_kind"
    )
    outfit_event_kind.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("auth_provider_id", sa.String(255)),
        sa.Column("role", user_role, nullable=False, server_default="adult"),
        sa.Column("display_name", sa.String(120)),
        sa.Column("locale", sa.String(10), nullable=False, server_default="en-US"),
        sa.Column("birth_year", sa.SmallInteger),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.UniqueConstraint("auth_provider_id", name="uq_users_auth_provider_id"),
    )

    op.create_table(
        "style_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_kind", owner_kind, nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("sizes", postgresql.JSONB, server_default="{}"),
        sa.Column("style_vector", Vector(768)),
        sa.Column("preferred_colors", postgresql.ARRAY(sa.String()), server_default="{}"),
        sa.Column("disliked_categories", postgresql.ARRAY(sa.String()), server_default="{}"),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "family_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "guardian_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("display_name", sa.String(60), nullable=False),
        sa.Column("kind", fam_kind, nullable=False, server_default="kid"),
        sa.Column("birth_year", sa.SmallInteger),
        sa.Column("kid_mode", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "kid_consents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "family_member_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("family_members.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "guardian_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("consent_method", consent_method, nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "wardrobe_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_kind", owner_kind, nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("raw_image_key", sa.String(512), nullable=False),
        sa.Column("cutout_image_key", sa.String(512)),
        sa.Column("thumbnail_key", sa.String(512)),
        sa.Column("category", sa.String(120), index=True),
        sa.Column("subcategory_path", sa.String(255)),
        sa.Column("colors", postgresql.JSONB, server_default="[]"),
        sa.Column("pattern", pattern),
        sa.Column("formality", sa.SmallInteger),
        sa.Column("seasonality", postgresql.ARRAY(sa.String()), server_default="{}"),
        sa.Column("material_guess", sa.String(60)),
        sa.Column("embedding", Vector(768)),
        sa.Column("confidence_scores", postgresql.JSONB, server_default="{}"),
        sa.Column("needs_review", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("coppa_protected", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_wardrobe_items_owner",
        "wardrobe_items",
        ["owner_kind", "owner_id", "category"],
    )
    op.execute(
        "CREATE INDEX ix_wardrobe_items_embedding ON wardrobe_items "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )

    op.create_table(
        "item_corrections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("wardrobe_items.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("field", sa.String(60), nullable=False),
        sa.Column("old_value", sa.Text),
        sa.Column("new_value", sa.Text, nullable=False),
        sa.Column("corrected_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "outfits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_kind", owner_kind, nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("source", outfit_source, nullable=False, server_default="ai_generated"),
        sa.Column("destination", sa.String(40)),
        sa.Column("mood", sa.String(40)),
        sa.Column("weather_snapshot", postgresql.JSONB),
        sa.Column("rationale", sa.Text),
        sa.Column("model_id", sa.String(120)),
        sa.Column("confidence", sa.Float),
        sa.Column("accepted", sa.Boolean),
        sa.Column("composite_image_key", sa.String(512)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "outfit_items",
        sa.Column(
            "outfit_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("outfits.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("wardrobe_items.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("slot", outfit_slot, nullable=False),
    )

    op.create_table(
        "outfit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "outfit_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("outfits.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("event_kind", outfit_event_kind, nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("outfit_events")
    op.drop_table("outfit_items")
    op.drop_table("outfits")
    op.drop_table("item_corrections")
    op.drop_table("wardrobe_items")
    op.drop_table("kid_consents")
    op.drop_table("family_members")
    op.drop_table("style_profiles")
    op.drop_table("users")
    for name in [
        "outfit_event_kind",
        "outfit_slot",
        "outfit_source",
        "pattern",
        "consent_method",
        "family_member_kind",
        "owner_kind",
        "user_role",
    ]:
        op.execute(f"DROP TYPE IF EXISTS {name}")
