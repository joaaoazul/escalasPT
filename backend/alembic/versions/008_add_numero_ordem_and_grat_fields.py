"""Add numero_ordem to users, location and grat_type to shifts.

Revision ID: 008
Revises: 007
"""

revision = "008"
down_revision = "007"

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    # Users: add numero_ordem (unique, nullable for existing rows)
    op.add_column("users", sa.Column(
        "numero_ordem", sa.String(10), nullable=True,
        comment="Número de ordem do militar (3-4 dígitos)",
    ))
    op.create_index("ix_users_numero_ordem", "users", ["numero_ordem"], unique=True)

    # Shifts: add location and grat_type
    op.add_column("shifts", sa.Column(
        "location", sa.String(300), nullable=True,
        comment="Localização do serviço (relevante para gratificados)",
    ))
    op.add_column("shifts", sa.Column(
        "grat_type", sa.String(100), nullable=True,
        comment="Tipo de gratificado (ex: Evento desportivo, Segurança privada)",
    ))


def downgrade() -> None:
    op.drop_column("shifts", "grat_type")
    op.drop_column("shifts", "location")
    op.drop_index("ix_users_numero_ordem", table_name="users")
    op.drop_column("users", "numero_ordem")
