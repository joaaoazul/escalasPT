"""Let the application role send Supabase Realtime signals.

The API announces changes by calling realtime.send() in its own transaction
(see app/services/realtime.py). That function is not SECURITY DEFINER: it
inserts into realtime.messages with the caller's rights, and fails quietly
(a WARNING, nothing sent) without them.

Granted to the limited application role by the same names 001 looks for.
Where there is no realtime schema (Docker, CI) or no such role — the app
connects as the owner — this does nothing.

Revision ID: 011
Revises: 010
"""

revision = "011"
down_revision = "010"

from alembic import op


def upgrade() -> None:
    op.execute("""
        DO $$
        DECLARE
            app_role text;
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'realtime') THEN
                RETURN;
            END IF;
            FOR app_role IN
                SELECT rolname FROM pg_roles WHERE rolname IN ('gnr_app', 'escalaspt_app')
            LOOP
                EXECUTE format('GRANT USAGE ON SCHEMA realtime TO %I', app_role);
                EXECUTE format('GRANT INSERT ON realtime.messages TO %I', app_role);
            END LOOP;
        END
        $$;
    """)


def downgrade() -> None:
    op.execute("""
        DO $$
        DECLARE
            app_role text;
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'realtime') THEN
                RETURN;
            END IF;
            FOR app_role IN
                SELECT rolname FROM pg_roles WHERE rolname IN ('gnr_app', 'escalaspt_app')
            LOOP
                EXECUTE format('REVOKE INSERT ON realtime.messages FROM %I', app_role);
                EXECUTE format('REVOKE USAGE ON SCHEMA realtime FROM %I', app_role);
            END LOOP;
        END
        $$;
    """)
