"""Add comando_territorial and destacamento to stations.

GNR hierarchy: Comando Territorial → Destacamento → Posto
numero_ordem is unique per Comando Territorial (not globally).

Revision ID: 009
Revises: 008
"""

revision = "009"
down_revision = "008"

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    # Add hierarchy fields to stations
    op.add_column("stations", sa.Column(
        "comando_territorial", sa.String(200), nullable=True,
        comment="Comando Territorial (e.g. CT Porto)",
    ))
    op.add_column("stations", sa.Column(
        "destacamento", sa.String(200), nullable=True,
        comment="Destacamento Territorial (e.g. DT Vila Nova de Gaia)",
    ))

    # Backfill existing stations with placeholder values
    op.execute("UPDATE stations SET comando_territorial = 'CT Porto' WHERE comando_territorial IS NULL")
    op.execute("UPDATE stations SET destacamento = 'DT Vila Nova de Gaia' WHERE destacamento IS NULL")

    # Now make them NOT NULL
    op.alter_column("stations", "comando_territorial", nullable=False)
    op.alter_column("stations", "destacamento", nullable=False)

    op.create_index("ix_stations_comando_territorial", "stations", ["comando_territorial"])
    op.create_index("ix_stations_destacamento", "stations", ["destacamento"])

    # Change numero_ordem: drop global unique, keep index
    op.drop_index("ix_users_numero_ordem", table_name="users")
    op.create_index("ix_users_numero_ordem", "users", ["numero_ordem"], unique=False)

    # Shrink nip column to 7 chars and numero_ordem to 4 chars
    op.alter_column("users", "nip",
        type_=sa.String(7),
        comment="NIM — Número de Identificação Militar (7 dígitos, único nacional)",
    )
    op.alter_column("users", "numero_ordem",
        type_=sa.String(4),
        comment="Número de ordem do militar (1-4 dígitos, único por Comando Territorial)",
    )


def downgrade() -> None:
    op.alter_column("users", "numero_ordem",
        type_=sa.String(10),
        comment="Número de ordem do militar (3-4 dígitos)",
    )
    op.alter_column("users", "nip",
        type_=sa.String(20),
        comment="Número de Identificação Pessoal",
    )

    op.drop_index("ix_users_numero_ordem", table_name="users")
    op.create_index("ix_users_numero_ordem", "users", ["numero_ordem"], unique=True)

    op.drop_index("ix_stations_destacamento", table_name="stations")
    op.drop_index("ix_stations_comando_territorial", table_name="stations")
    op.drop_column("stations", "destacamento")
    op.drop_column("stations", "comando_territorial")
