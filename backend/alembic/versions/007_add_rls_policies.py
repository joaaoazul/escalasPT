"""Add Row-Level Security policies for multi-tenant isolation.

Policies use the session variable `app.current_station_id` set by the
FastAPI RLS middleware on every request.

Tables protected: shifts, shift_types, notifications, users, stations.
Admin users (station_id IS NULL) bypass RLS via the USING clause.

Revision ID: 007
Revises: 006
"""

revision = "007"
down_revision = "006"

from alembic import op


# The database user used by the application — RLS policies apply to this role.
APP_ROLE = "app_user"


def _enable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")


def _disable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")


def upgrade() -> None:
    # ── shifts ────────────────────────────────────────────
    _enable_rls("shifts")
    op.execute("""
        CREATE POLICY shifts_station_isolation ON shifts
        USING (
            current_setting('app.current_station_id', true) = ''
            OR station_id = current_setting('app.current_station_id', true)::uuid
        )
    """)

    # ── shift_types ───────────────────────────────────────
    _enable_rls("shift_types")
    op.execute("""
        CREATE POLICY shift_types_station_isolation ON shift_types
        USING (
            current_setting('app.current_station_id', true) = ''
            OR station_id = current_setting('app.current_station_id', true)::uuid
        )
    """)

    # ── notifications ─────────────────────────────────────
    _enable_rls("notifications")
    op.execute("""
        CREATE POLICY notifications_station_isolation ON notifications
        USING (
            current_setting('app.current_station_id', true) = ''
            OR station_id = current_setting('app.current_station_id', true)::uuid
        )
    """)

    # ── users ─────────────────────────────────────────────
    # station_id is nullable (admin users have NULL), so allow those too.
    _enable_rls("users")
    op.execute("""
        CREATE POLICY users_station_isolation ON users
        USING (
            current_setting('app.current_station_id', true) = ''
            OR station_id IS NULL
            OR station_id = current_setting('app.current_station_id', true)::uuid
        )
    """)

    # ── stations ──────────────────────────────────────────
    _enable_rls("stations")
    op.execute("""
        CREATE POLICY stations_isolation ON stations
        USING (
            current_setting('app.current_station_id', true) = ''
            OR id = current_setting('app.current_station_id', true)::uuid
        )
    """)


def downgrade() -> None:
    for policy, table in [
        ("shifts_station_isolation", "shifts"),
        ("shift_types_station_isolation", "shift_types"),
        ("notifications_station_isolation", "notifications"),
        ("users_station_isolation", "users"),
        ("stations_isolation", "stations"),
    ]:
        op.execute(f"DROP POLICY IF EXISTS {policy} ON {table}")
        _disable_rls(table)
