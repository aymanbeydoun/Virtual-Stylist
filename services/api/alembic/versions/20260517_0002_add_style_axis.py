"""add preferred_style to style_profiles + outfit.style column

The Style axis (streetwear, minimal, classic, preppy, etc.) is orthogonal to
mood. We store both the per-outfit applied style and the user's saved default
in style_profiles so the AI can fall back to the profile when nothing's set.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260517_0002_style"
down_revision: str | None = "20260517_0001_tryon"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "style_profiles", sa.Column("preferred_style", sa.String(length=40), nullable=True)
    )
    op.add_column("outfits", sa.Column("style", sa.String(length=40), nullable=True))


def downgrade() -> None:
    op.drop_column("outfits", "style")
    op.drop_column("style_profiles", "preferred_style")
