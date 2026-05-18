"""add gap_findings

Adds the gap_findings table that backs the Closet-Gap analysis feature.
Affiliate suggestions land in a follow-up migration (Phase 4).
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "d10619eaa951"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # owner_kind enum already exists from 0001_initial. Use postgresql.ENUM with
    # create_type=False so the type isn't re-emitted.
    bind = op.get_bind()
    # Create the new gap_* enums up-front, then use create_type=False on the column
    # types so create_table doesn't try to redeclare them.
    postgresql.ENUM("high", "medium", "low", name="gap_severity").create(
        bind, checkfirst=True
    )
    postgresql.ENUM("open", "dismissed", "resolved", name="gap_status").create(
        bind, checkfirst=True
    )
    owner_kind = postgresql.ENUM(
        "user", "family_member", name="owner_kind", create_type=False
    )
    severity = postgresql.ENUM(
        "high", "medium", "low", name="gap_severity", create_type=False
    )
    status = postgresql.ENUM(
        "open", "dismissed", "resolved", name="gap_status", create_type=False
    )

    op.create_table(
        "gap_findings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("owner_kind", owner_kind, nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("slot", sa.String(length=40), nullable=False),
        sa.Column("category_hint", sa.String(length=80), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("severity", severity, nullable=False),
        sa.Column("status", status, nullable=False),
        sa.Column("search_query", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_gap_findings")),
    )
    op.create_index(
        op.f("ix_gap_findings_owner_id"), "gap_findings", ["owner_id"], unique=False
    )
    # Partial index for the common 'show me my open gaps' query.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_gap_findings_open ON gap_findings (owner_id) "
        "WHERE status = 'open'"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_gap_findings_open")
    op.drop_index(op.f("ix_gap_findings_owner_id"), table_name="gap_findings")
    op.drop_table("gap_findings")
    sa.Enum(name="gap_severity").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="gap_status").drop(op.get_bind(), checkfirst=True)
