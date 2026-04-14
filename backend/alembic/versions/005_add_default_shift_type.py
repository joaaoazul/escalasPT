"""Add default_shift_type_id to users table.

Revision ID: 005
Revises: 004
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "default_shift_type_id",
            UUID(as_uuid=True),
            sa.ForeignKey("shift_types.id", ondelete="SET NULL"),
            nullable=True,
            comment="If set, user is always assigned this shift type (fixed role)",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "default_shift_type_id")
