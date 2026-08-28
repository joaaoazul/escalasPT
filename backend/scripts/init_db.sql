-- ============================================================
-- Caderno de Serviço — database initialisation
-- Runs once, on first `docker compose up`, via the postgres entrypoint.
--
-- Creates the LIMITED application role. The API connects as this role; the
-- owner is used only by Alembic. That is what makes the audit_logs REVOKE
-- (migration 001) and the RLS policies actually apply at runtime — in
-- escalasPT the app connects as the owner, so neither of them does.
-- ============================================================

\set ON_ERROR_STOP on
\set app_password `echo "${CADERNO_APP_DB_PASSWORD:-}"`

-- Refuse to create a login role with an empty or placeholder password.
SELECT format(
    'DO $guard$ BEGIN RAISE EXCEPTION %L; END $guard$',
    'CADERNO_APP_DB_PASSWORD is not set — run deploy/setup.sh, which generates it.'
)
WHERE :'app_password' IN ('', 'CHANGE_ME', 'GENERATE_ME')
\gexec

-- Create the role (psql substitutes :'app_password' here; it would NOT be
-- substituted inside a dollar-quoted DO block).
SELECT format('CREATE ROLE caderno_app WITH LOGIN PASSWORD %L', :'app_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'caderno_app')
\gexec

SELECT format('GRANT CONNECT ON DATABASE %I TO caderno_app', current_database())
\gexec

GRANT USAGE ON SCHEMA public TO caderno_app;

-- Tables created later by Alembic (as the owner) inherit these.
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO caderno_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO caderno_app;

-- Anything that already exists keeps working too.
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO caderno_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO caderno_app;
