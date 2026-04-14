"""Add min_staff column to shift_types.

Revision ID: 002
Revises: 001
Create Date: 2026-04-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "shift_types",
        sa.Column("min_staff", sa.Integer, nullable=False, server_default="1"),
    )


def downgrade() -> None:
    op.drop_column("shift_types", "min_staff")
