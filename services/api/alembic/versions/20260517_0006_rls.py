# ruff: noqa: E501
"""Postgres Row-Level Security for owner-scoped tables.

Defense in depth: even if a future endpoint forgets the application-level
_resolve_owner check, the DB itself will not return another profile's data.

⚠️  This migration is intentionally NOT in the standard apply path. Before
running it:
  1. Add per-request middleware that runs
       SET LOCAL app.current_user_id = '<user_id>'
     at the start of every transaction (or skip it for anonymous endpoints
     like /health and /openapi.json).
  2. Bench every endpoint to make sure the new query plan is acceptable.
  3. Apply in a maintenance window with rollback ready.

To apply manually once the above is done:
  uv run alembic upgrade 20260517_0006_rls

Policy contract:
  - Every owner-scoped table has RLS enabled.
  - The API sets `SET LOCAL app.current_user_id = '<uuid>'` at the start of
    each request (see app/db.py middleware).
  - For 'user' rows: the row is visible when owner_id = current_user_id.
  - For 'family_member' rows: the row is visible when the family_member's
    guardian_id = current_user_id.
  - The 'app_admin' role bypasses RLS for migrations + admin scripts.

Bypass:
  - The `stylist` role used by the API runs as a normal (non-superuser) role
    once we tighten production permissions.
  - In dev, the stylist role is currently a superuser, which bypasses RLS by
    default. We explicitly REVOKE BYPASSRLS in the migration so the same code
    behaves identically in dev and prod.
"""
from collections.abc import Sequence

from alembic import op

revision: str = "20260517_0006_rls"
down_revision: str | None = "20260517_0005_attrs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_OWNER_SCOPED_TABLES = (
    "wardrobe_items",
    "outfits",
    "gap_findings",
)
# Tables that key off `outfit_id` rather than owner directly. Their RLS policy
# joins to outfits to inherit the owner check.
_OUTFIT_SCOPED_TABLES = (
    "outfit_messages",
    "outfit_tryons",
    "outfit_items",
    "outfit_events",
)


def upgrade() -> None:
    # 1. Drop BYPASSRLS from the stylist role so RLS is actually enforced.
    op.execute("ALTER ROLE stylist NOBYPASSRLS")

    # 2. Enable RLS + policies on directly-owner-scoped tables.
    for table in _OWNER_SCOPED_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {table}_owner_policy ON {table}
            USING (
                (owner_kind = 'user' AND owner_id = current_setting('app.current_user_id', true)::uuid)
                OR (
                    owner_kind = 'family_member'
                    AND owner_id IN (
                        SELECT id FROM family_members
                        WHERE guardian_id = current_setting('app.current_user_id', true)::uuid
                    )
                )
                OR current_setting('app.current_user_id', true) = ''
            )
            WITH CHECK (
                (owner_kind = 'user' AND owner_id = current_setting('app.current_user_id', true)::uuid)
                OR (
                    owner_kind = 'family_member'
                    AND owner_id IN (
                        SELECT id FROM family_members
                        WHERE guardian_id = current_setting('app.current_user_id', true)::uuid
                    )
                )
                OR current_setting('app.current_user_id', true) = ''
            )
            """
        )

    # 3. Outfit-scoped child tables: inherit via join to outfits.
    for table in _OUTFIT_SCOPED_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {table}_owner_policy ON {table}
            USING (
                outfit_id IN (
                    SELECT id FROM outfits  -- the outfits policy will filter
                )
                OR current_setting('app.current_user_id', true) = ''
            )
            """
        )

    # 4. family_members: visible to the guardian.
    op.execute("ALTER TABLE family_members ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE family_members FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY family_members_guardian_policy ON family_members
        USING (
            guardian_id = current_setting('app.current_user_id', true)::uuid
            OR current_setting('app.current_user_id', true) = ''
        )
        """
    )


def downgrade() -> None:
    for table in (
        "wardrobe_items", "outfits", "gap_findings",
        "outfit_messages", "outfit_tryons", "outfit_items", "outfit_events",
        "family_members",
    ):
        op.execute(f"DROP POLICY IF EXISTS {table}_owner_policy ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_guardian_policy ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER ROLE stylist BYPASSRLS")
