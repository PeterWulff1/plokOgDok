-- 002: Access roles. These are NOLOGIN group roles; no passwords live in this repo.
-- Create the login users once by hand (e.g. in the Supabase SQL editor):
--   CREATE ROLE vl_reader LOGIN PASSWORD '...' IN ROLE vl_read;
--   CREATE ROLE vl_writer LOGIN PASSWORD '...' IN ROLE vl_write;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'vl_read') THEN
        CREATE ROLE vl_read NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'vl_write') THEN
        CREATE ROLE vl_write NOLOGIN;
    END IF;
END
$$;

GRANT USAGE ON SCHEMA vl TO vl_read, vl_write;

GRANT SELECT ON ALL TABLES IN SCHEMA vl TO vl_read;
ALTER DEFAULT PRIVILEGES IN SCHEMA vl GRANT SELECT ON TABLES TO vl_read;

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA vl TO vl_write;
ALTER DEFAULT PRIVILEGES IN SCHEMA vl GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO vl_write;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA vl TO vl_write;
ALTER DEFAULT PRIVILEGES IN SCHEMA vl GRANT USAGE ON SEQUENCES TO vl_write;
