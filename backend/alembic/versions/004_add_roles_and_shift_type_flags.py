"""Add adjunto/secretaria roles, is_absence and fixed_slots to shift_types.

Revision ID: 004
Revises: 003
Create Date: 2026-04-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Extend user_role enum with adjunto and secretaria ─
    op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'adjunto'")
    op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'secretaria'")

    # ── Add is_absence and fixed_slots to shift_types ─────
    op.add_column(
        "shift_types",
        sa.Column("is_absence", sa.Boolean, nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "shift_types",
        sa.Column("fixed_slots", sa.Boolean, nullable=False, server_default=sa.text("false")),
    )

    # Mark existing AT and OC types as fixed_slots=True
    op.execute("UPDATE shift_types SET fixed_slots = true WHERE code LIKE 'AT%' OR code LIKE 'OC%'")


def downgrade() -> None:
    op.drop_column("shift_types", "fixed_slots")
    op.drop_column("shift_types", "is_absence")
    # Note: PostgreSQL does not support removing enum values without dropping+recreating the type
