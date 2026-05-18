"""add deep attributes JSONB + quality_tier + body_shape

Adds the schema needed for breakthrough-quality tagging:
  - wardrobe_items.attributes: free-form JSONB bag (neckline, sleeve_length,
    fabric, fit, pattern_subtype, weight_class, etc.)
  - wardrobe_items.quality_tier: which bg-removal pipeline this item used.
  - style_profiles.body_shape: hourglass / pear / apple / rectangle / etc.
    Drives personalised stylist prompts.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260517_0005_attrs"
down_revision: str | None = "20260517_0004_affiliate"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "wardrobe_items",
        sa.Column(
            "attributes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "wardrobe_items",
        sa.Column(
            "quality_tier",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'standard'"),
        ),
    )
    # GIN index on attributes so queries like
    #   WHERE attributes @> '{"sleeve_length": "long"}'
    # stay fast as the closet grows.
    op.create_index(
        "ix_wardrobe_items_attributes_gin",
        "wardrobe_items",
        ["attributes"],
        unique=False,
        postgresql_using="gin",
    )

    op.add_column(
        "style_profiles",
        sa.Column("body_shape", sa.String(length=30), nullable=True),
    )

    # Human-readable reason surfaced to the mobile when an item fails to tag.
    op.add_column(
        "wardrobe_items",
        sa.Column("failure_reason", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("wardrobe_items", "failure_reason")
    op.drop_column("style_profiles", "body_shape")
    op.drop_index("ix_wardrobe_items_attributes_gin", table_name="wardrobe_items")
    op.drop_column("wardrobe_items", "quality_tier")
    op.drop_column("wardrobe_items", "attributes")
