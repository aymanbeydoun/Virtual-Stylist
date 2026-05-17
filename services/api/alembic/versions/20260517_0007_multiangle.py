"""add multi-angle base photos + per-render angle label

Adds the schema needed for "VERY REAL" multi-angle try-on:
  - users.base_photo_keys: JSONB map {angle: storage_key}
  - family_members.base_photo_keys: same
  - outfit_tryons.angle: which view this render represents

The existing `base_photo_key` column is kept for backward compatibility —
it's mirrored as the "front" angle in the new dict, so old code paths still
work.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260517_0007_multiangle"
down_revision: str | None = "20260517_0006_rls"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "base_photo_keys",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "family_members",
        sa.Column(
            "base_photo_keys",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "outfit_tryons",
        sa.Column("angle", sa.String(length=20), nullable=True),
    )
    # Backfill: copy existing base_photo_key into the new dict as the "front"
    # angle, so users who already uploaded a photo don't have to redo it.
    op.execute(
        """
        UPDATE users
           SET base_photo_keys = jsonb_build_object('front', base_photo_key)
         WHERE base_photo_key IS NOT NULL
           AND (base_photo_keys = '{}'::jsonb OR base_photo_keys IS NULL)
        """
    )
    op.execute(
        """
        UPDATE family_members
           SET base_photo_keys = jsonb_build_object('front', base_photo_key)
         WHERE base_photo_key IS NOT NULL
           AND (base_photo_keys = '{}'::jsonb OR base_photo_keys IS NULL)
        """
    )


def downgrade() -> None:
    op.drop_column("outfit_tryons", "angle")
    op.drop_column("family_members", "base_photo_keys")
    op.drop_column("users", "base_photo_keys")
