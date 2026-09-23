"""Take the Supabase Data API's roles off every table.

Supabase serves the public schema over REST (PostgREST) to two roles:
`anon`, which anyone holding the publishable key gets, and `authenticated`.
Its default privileges grant both of them everything on every table created
in public — these migrations included. The app never uses that API: it talks
to Postgres directly as the owner. But with the grants in place, and RLS
either off or with policies that let an unset station through, the
publishable key the frontend ships would read the users table, password
hashes and TOTP secrets included, straight over REST.

So: revoke every grant those roles hold here, and change the migration
role's default privileges so tables added by later migrations start out
without them. On a Postgres that has no such roles (Docker, CI) this is a
no-op.

Revision ID: 010
Revises: 009
"""

revision = "010"
down_revision = "009"

from alembic import op


def upgrade() -> None:
    op.execute("""
        DO $$
        DECLARE
            r text;
        BEGIN
            FOREACH r IN ARRAY ARRAY['anon', 'authenticated'] LOOP
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
                    EXECUTE format('REVOKE ALL ON ALL TABLES IN SCHEMA public FROM %I', r);
                    EXECUTE format('REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM %I', r);
                    EXECUTE format('REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM %I', r);
                    EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM %I', r);
                    EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM %I', r);
                    EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON FUNCTIONS FROM %I', r);
                END IF;
            END LOOP;
        END
        $$;
    """)


def downgrade() -> None:
    # Deliberately nothing: handing the tables back to the public API is not
    # something a rollback should do on its own.
    pass
