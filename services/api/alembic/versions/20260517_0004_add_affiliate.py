"""add affiliate_suggestions + affiliate_clicks for Phase 4 monetisation"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260517_0004_affiliate"
down_revision: str | None = "20260517_0003_messages"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    postgresql.ENUM(
        "stub", "brands_for_less", "ounass", "amazon", name="affiliate_provider"
    ).create(op.get_bind(), checkfirst=True)
    provider = postgresql.ENUM(
        "stub", "brands_for_less", "ounass", "amazon",
        name="affiliate_provider", create_type=False,
    )

    op.create_table(
        "affiliate_suggestions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("gap_finding_id", sa.UUID(), nullable=False),
        sa.Column("provider", provider, nullable=False),
        sa.Column("external_id", sa.String(length=200), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("brand", sa.String(length=120), nullable=True),
        sa.Column("image_url", sa.String(length=1024), nullable=True),
        sa.Column("price_minor", sa.Integer(), nullable=True),
        sa.Column("price_currency", sa.String(length=3), nullable=True),
        sa.Column("affiliate_url", sa.String(length=1024), nullable=False),
        sa.Column("attribution_token", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["gap_finding_id"], ["gap_findings.id"],
            name=op.f("fk_affiliate_suggestions_gap_finding_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_affiliate_suggestions")),
    )
    op.create_index(
        op.f("ix_affiliate_suggestions_gap_finding_id"),
        "affiliate_suggestions",
        ["gap_finding_id"],
        unique=False,
    )

    op.create_table(
        "affiliate_clicks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("suggestion_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["suggestion_id"], ["affiliate_suggestions.id"],
            name=op.f("fk_affiliate_clicks_suggestion_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_affiliate_clicks")),
    )
    op.create_index(
        op.f("ix_affiliate_clicks_suggestion_id"),
        "affiliate_clicks",
        ["suggestion_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_affiliate_clicks_user_id"), "affiliate_clicks", ["user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_affiliate_clicks_user_id"), table_name="affiliate_clicks")
    op.drop_index(op.f("ix_affiliate_clicks_suggestion_id"), table_name="affiliate_clicks")
    op.drop_table("affiliate_clicks")
    op.drop_index(
        op.f("ix_affiliate_suggestions_gap_finding_id"), table_name="affiliate_suggestions"
    )
    op.drop_table("affiliate_suggestions")
    sa.Enum(name="affiliate_provider").drop(op.get_bind(), checkfirst=True)
