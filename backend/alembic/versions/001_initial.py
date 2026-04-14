"""Initial migration — all core tables.

Revision ID: 001
Revises: None
Create Date: 2026-04-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Stations ──────────────────────────────────────────
    op.create_table(
        "stations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("code", sa.String(20), nullable=False, unique=True),
        sa.Column("address", sa.String(500), nullable=True),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_stations_code", "stations", ["code"])

    # ── Users ─────────────────────────────────────────────
    # Create enum type first
    user_role = sa.Enum("admin", "comandante", "militar", name="user_role", create_type=True)

    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("username", sa.String(50), nullable=False, unique=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("nip", sa.String(20), nullable=False, unique=True),
        sa.Column("role", user_role, nullable=False, server_default="militar"),
        sa.Column("station_id", UUID(as_uuid=True), sa.ForeignKey("stations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("totp_secret", sa.String(64), nullable=True),
        sa.Column("totp_enabled", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_username", "users", ["username"])
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_nip", "users", ["nip"])
    op.create_index("ix_users_station_id", "users", ["station_id"])

    # ── Refresh Tokens ────────────────────────────────────
    op.create_table(
        "refresh_tokens",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(255), nullable=False, unique=True),
        sa.Column("family_id", UUID(as_uuid=True), nullable=False),
        sa.Column("is_revoked", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_family_id", "refresh_tokens", ["family_id"])

    # ── Shift Types ───────────────────────────────────────
    op.create_table(
        "shift_types",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("station_id", UUID(as_uuid=True), sa.ForeignKey("stations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("start_time", sa.Time, nullable=False),
        sa.Column("end_time", sa.Time, nullable=False),
        sa.Column("color", sa.String(7), nullable=False, server_default="#3B82F6"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_shift_types_station_id", "shift_types", ["station_id"])

    # ── Shifts ────────────────────────────────────────────
    shift_status = sa.Enum("draft", "published", "cancelled", name="shift_status", create_type=True)

    op.create_table(
        "shifts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("station_id", UUID(as_uuid=True), sa.ForeignKey("stations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("shift_type_id", UUID(as_uuid=True), sa.ForeignKey("shift_types.id", ondelete="SET NULL"), nullable=True),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("start_datetime", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_datetime", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", shift_status, nullable=False, server_default="draft"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_shifts_user_id", "shifts", ["user_id"])
    op.create_index("ix_shifts_station_id", "shifts", ["station_id"])
    op.create_index("ix_shifts_shift_type_id", "shifts", ["shift_type_id"])
    op.create_index("ix_shifts_date", "shifts", ["date"])
    op.create_index("ix_shifts_status", "shifts", ["status"])

    # ── Shift Swap Requests ───────────────────────────────
    swap_status = sa.Enum(
        "pending_target", "pending_approval", "approved", "rejected", "cancelled",
        name="swap_status", create_type=True,
    )

    op.create_table(
        "shift_swap_requests",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("requester_shift_id", UUID(as_uuid=True), sa.ForeignKey("shifts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_shift_id", UUID(as_uuid=True), sa.ForeignKey("shifts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("requester_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", swap_status, nullable=False, server_default="pending_target"),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_shift_swap_requester_id", "shift_swap_requests", ["requester_id"])
    op.create_index("ix_shift_swap_target_id", "shift_swap_requests", ["target_id"])

    # ── Notifications ─────────────────────────────────────
    notification_type = sa.Enum(
        "shift_published", "shift_updated", "shift_cancelled",
        "swap_requested", "swap_accepted", "swap_approved", "swap_rejected",
        "general",
        name="notification_type", create_type=True,
    )

    op.create_table(
        "notifications",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("station_id", UUID(as_uuid=True), sa.ForeignKey("stations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", notification_type, nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("is_read", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("data", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_station_id", "notifications", ["station_id"])

    # ── Audit Logs ────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=False),
        sa.Column("resource_id", sa.String(36), nullable=True),
        sa.Column("old_data", JSONB, nullable=True),
        sa.Column("new_data", JSONB, nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_resource_type", "audit_logs", ["resource_type"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])

    # ── RLS Policies ──────────────────────────────────────
    # Enable RLS on multi-tenant tables
    op.execute("ALTER TABLE shifts ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE notifications ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE shift_types ENABLE ROW LEVEL SECURITY")

    # RLS policies — filter by current_setting('app.current_station_id')
    op.execute("""
        CREATE POLICY shifts_station_isolation ON shifts
        FOR ALL
        USING (station_id::text = current_setting('app.current_station_id', true))
    """)
    op.execute("""
        CREATE POLICY notifications_station_isolation ON notifications
        FOR ALL
        USING (station_id::text = current_setting('app.current_station_id', true))
    """)
    op.execute("""
        CREATE POLICY shift_types_station_isolation ON shift_types
        FOR ALL
        USING (station_id::text = current_setting('app.current_station_id', true))
    """)

    # ── Audit Log Protection ──────────────────────────────
    # Revoke destructive operations from app user on audit_logs
    op.execute("REVOKE UPDATE, DELETE ON audit_logs FROM gnr_app")
    # Grant only INSERT and SELECT
    op.execute("GRANT SELECT, INSERT ON audit_logs TO gnr_app")


def downgrade() -> None:
    # Drop policies
    op.execute("DROP POLICY IF EXISTS shifts_station_isolation ON shifts")
    op.execute("DROP POLICY IF EXISTS notifications_station_isolation ON notifications")
    op.execute("DROP POLICY IF EXISTS shift_types_station_isolation ON shift_types")

    # Disable RLS
    op.execute("ALTER TABLE shifts DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE notifications DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE shift_types DISABLE ROW LEVEL SECURITY")

    # Drop tables in reverse dependency order
    op.drop_table("audit_logs")
    op.drop_table("notifications")
    op.drop_table("shift_swap_requests")
    op.drop_table("shifts")
    op.drop_table("shift_types")
    op.drop_table("refresh_tokens")
    op.drop_table("users")
    op.drop_table("stations")

    # Drop enum types
    sa.Enum(name="user_role").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="shift_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="swap_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="notification_type").drop(op.get_bind(), checkfirst=True)
