"""add gender preference to style_profiles

Closet seeding pulls in items of both genders, and Claude tagging happily
assigns "mens." or "womens." prefixes accordingly. For try-on to render
the correct person we need a hard gender filter on candidate selection.
Auto-detection from closet majority works when there's a clear majority
(>= 70%) but breaks on mixed/seeded data — hence this explicit setting.

Value vocabulary: 'mens' | 'womens' | 'unspecified' (treated as None →
falls back to auto-detection). Free-text rather than enum so we can
expand the taxonomy later (e.g. nonbinary) without another migration.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260517_0008_gender"
down_revision: str | None = "20260517_0007_multiangle"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "style_profiles",
        sa.Column("gender", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("style_profiles", "gender")
