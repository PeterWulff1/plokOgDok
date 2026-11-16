-- 020: A role that can only maintain the calendar.
-- The nightly GitHub workflow syncs the calendar. It used the full write role for that, which
-- can change every table; this role can only touch vl.calendar_event, so a leaked workflow
-- secret can't alter results (docs/decisions.md, 2026-11-16).
-- NOLOGIN group role, like vl_read and vl_write. Create the login user once by hand:
--   CREATE ROLE vl_calendar_sync LOGIN PASSWORD '...' IN ROLE vl_calendar;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'vl_calendar') THEN
        CREATE ROLE vl_calendar NOLOGIN;
    END IF;
END
$$;

GRANT USAGE ON SCHEMA vl TO vl_calendar;
-- Everything scraper/fetch_calendar.py does: look up, upsert, delete cancelled events.
-- The id is an identity column, so no sequence privilege is needed.
GRANT SELECT, INSERT, UPDATE, DELETE ON vl.calendar_event TO vl_calendar;
