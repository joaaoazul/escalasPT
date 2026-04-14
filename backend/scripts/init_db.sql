-- ============================================================
-- EscalasPT — Database initialization script
-- Runs on first docker-compose up via entrypoint
-- Creates the limited app user and sets audit_log protections
-- ============================================================

-- Create limited application user (if not exists)
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'gnr_app') THEN
        CREATE ROLE gnr_app WITH LOGIN PASSWORD 'CHANGE_ME_app_strong_password';
    END IF;
END
$$;

-- Grant connect
GRANT CONNECT ON DATABASE gnr_escalas TO gnr_app;

-- Schema permissions (will apply after migrations create the tables)
-- We grant broad permissions first; audit_log restrictions come after migration
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO gnr_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO gnr_app;
