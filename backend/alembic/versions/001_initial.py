"""Initial schema: equipas, users, refresh_tokens, active_sessions, audit_logs.

Three things here are deliberately different from escalasPT (docs/PLANO.md §1.2):

1. RLS policies DENY when `app.current_equipa_id` is missing or empty. escalasPT
   treats an empty setting as "see everything", so a malformed tenant hint is a
   full bypass.
2. Every CREATE POLICY is preceded by DROP POLICY IF EXISTS, so re-running a
   migration on a half-built database is not fatal.
3. The app role is resolved at runtime inside a DO block and interpolated with
   format(%I) — no role name is hardcoded, because dev and prod use different
   ones.

Revision ID: 001
Revises:
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None

# Roles that may exist as the limited application role, most specific first.
APP_ROLE_CANDIDATES = "'caderno_app', 'caderno_app_prod'"


def upgrade() -> None:
    # ── equipas ───────────────────────────────────────────
    op.create_table(
        "equipas",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, index=True),
        sa.Column("nome", sa.String(120), nullable=False),
        sa.Column("codigo", sa.String(20), nullable=False, unique=True, index=True),
        sa.Column("unidade", sa.String(120), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── users ─────────────────────────────────────────────
    # create_type=False on the column type: the enum is created once, here,
    # and create_table must not try to create it a second time.
    postgresql.ENUM("agente", "chefe_equipa", "admin", name="user_role").create(
        op.get_bind(), checkfirst=True
    )
    user_role = postgresql.ENUM(
        "agente", "chefe_equipa", "admin", name="user_role", create_type=False
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, index=True),
        sa.Column("username", sa.String(50), nullable=False, unique=True, index=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True, index=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("nome", sa.String(200), nullable=False),
        sa.Column("nip", sa.String(7), nullable=False, unique=True, index=True),
        sa.Column("role", user_role, nullable=False, server_default="agente"),
        sa.Column(
            "equipa_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("equipas.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("totp_secret_encrypted", sa.Text(), nullable=True),
        sa.Column("totp_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("failed_login_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── refresh_tokens ────────────────────────────────────
    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, index=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("token_hash", sa.String(255), nullable=False, unique=True),
        sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("is_revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── active_sessions ───────────────────────────────────
    op.create_table(
        "active_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, index=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("session_id", sa.String(36), nullable=False, unique=True, index=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("is_revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── audit_logs ────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, index=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("action", sa.String(50), nullable=False, index=True),
        sa.Column("resource_type", sa.String(50), nullable=False, index=True),
        sa.Column("resource_id", sa.String(36), nullable=True),
        sa.Column("old_data", postgresql.JSONB(), nullable=True),
        sa.Column("new_data", postgresql.JSONB(), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
    )

    # ── Row-Level Security ────────────────────────────────
    # equipas is the first table under RLS; phase 1 adds servicos, registos,
    # anexos, catalogos and modelos_texto with exactly this shape.
    op.execute("DROP POLICY IF EXISTS equipas_isolation ON equipas")
    op.execute("ALTER TABLE equipas ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE equipas FORCE ROW LEVEL SECURITY")
    # id::text = nullif(setting, '') is the whole trick:
    #   setting absent or empty  -> NULL -> comparison is NULL -> no rows
    #   setting is not a UUID    -> no match, and no cast error either
    # Both halves have to use missing_ok (the `true` argument): a bare
    # current_setting() on an unset parameter raises, and the planner is free to
    # evaluate it even when the guard in front of it is false.
    op.execute(
        """
        CREATE POLICY equipas_isolation ON equipas
        FOR ALL
        USING (id::text = nullif(current_setting('app.current_equipa_id', true), ''))
        WITH CHECK (id::text = nullif(current_setting('app.current_equipa_id', true), ''))
        """
    )

    # ── Audit log protection ──────────────────────────────
    # Only bites because the application connects as this limited role.
    op.execute(
        f"""
        DO $$
        DECLARE
            app_role text;
        BEGIN
            SELECT rolname INTO app_role FROM pg_catalog.pg_roles
            WHERE rolname IN ({APP_ROLE_CANDIDATES}) LIMIT 1;

            IF app_role IS NOT NULL THEN
                EXECUTE format('REVOKE UPDATE, DELETE ON audit_logs FROM %I', app_role);
                EXECUTE format('GRANT SELECT, INSERT ON audit_logs TO %I', app_role);
            ELSE
                RAISE NOTICE 'No limited app role found — audit_logs left unprotected. '
                             'Create it with scripts/init_db.sql before deploying.';
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS equipas_isolation ON equipas")
    op.execute("ALTER TABLE equipas NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE equipas DISABLE ROW LEVEL SECURITY")

    op.drop_table("audit_logs")
    op.drop_table("active_sessions")
    op.drop_table("refresh_tokens")
    op.drop_table("users")
    op.drop_table("equipas")
    op.execute("DROP TYPE IF EXISTS user_role")
