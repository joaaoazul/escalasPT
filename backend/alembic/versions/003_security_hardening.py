"""Security hardening — active sessions, account lockout, TOTP encryption.

Revision ID: 003
Revises: 002
Create Date: 2026-04-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── User lockout fields ───────────────────────────────
    op.add_column(
        "users",
        sa.Column("failed_login_attempts", sa.Integer, nullable=False, server_default="0"),
    )
    op.add_column(
        "users",
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
    )

    # ── Rename totp_secret → totp_secret_encrypted and widen to Text
    op.alter_column(
        "users",
        "totp_secret",
        new_column_name="totp_secret_encrypted",
        type_=sa.Text,
        existing_type=sa.String(64),
        existing_nullable=True,
    )

    # ── Active Sessions table ─────────────────────────────
    op.create_table(
        "active_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", sa.String(36), nullable=False, unique=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("is_revoked", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_active_sessions_user_id", "active_sessions", ["user_id"])
    op.create_index("ix_active_sessions_session_id", "active_sessions", ["session_id"])


def downgrade() -> None:
    op.drop_table("active_sessions")
    op.alter_column(
        "users",
        "totp_secret_encrypted",
        new_column_name="totp_secret",
        type_=sa.String(64),
        existing_type=sa.Text,
        existing_nullable=True,
    )
    op.drop_column("users", "locked_until")
    op.drop_column("users", "failed_login_attempts")
