#!/bin/bash
# ============================================================
# EscalasPT — Production database initialization
# Runs on first docker-compose up via postgres entrypoint
# ============================================================
set -e

# Use the same password as the main user if APP_DB_PASSWORD is not set
APP_DB_PASSWORD="${APP_DB_PASSWORD:-$POSTGRES_PASSWORD}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Create limited application user for RLS
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'escalaspt_app') THEN
            CREATE ROLE escalaspt_app WITH LOGIN PASSWORD '${APP_DB_PASSWORD}';
        ELSE
            ALTER ROLE escalaspt_app WITH PASSWORD '${APP_DB_PASSWORD}';
        END IF;
    END
    \$\$;

    GRANT CONNECT ON DATABASE "$POSTGRES_DB" TO escalaspt_app;

    ALTER DEFAULT PRIVILEGES IN SCHEMA public
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO escalaspt_app;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public
        GRANT USAGE, SELECT ON SEQUENCES TO escalaspt_app;
EOSQL
