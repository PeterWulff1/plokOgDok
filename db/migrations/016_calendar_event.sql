-- 016: The federation's event calendar (vaegtloeftning.dk/kalender), synced once a day by
-- scraper/fetch_calendar.py from the site's events API. Raw source fields only.
-- Descriptions and organisers are not stored: they carry names, emails and phone numbers.

CREATE TABLE vl.calendar_event (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    -- The event's ID on vaegtloeftning.dk.
    source_id        integer     NOT NULL UNIQUE,
    title            text        NOT NULL,
    -- Danish local time, as the source gives it.
    starts_at        timestamp   NOT NULL,
    ends_at          timestamp   NOT NULL,
    all_day          boolean     NOT NULL,
    venue            text,
    city             text,
    -- Free text at the source ('Danmark', 'Denmark', or missing).
    country          text,
    url              text        NOT NULL,
    source_modified  timestamptz NOT NULL,
    -- Sync bookkeeping: when our sync first and last saw the event.
    first_seen_at    timestamptz NOT NULL DEFAULT now(),
    last_seen_at     timestamptz NOT NULL DEFAULT now(),
    CHECK (starts_at <= ends_at)
);

CREATE INDEX calendar_event_starts_idx ON vl.calendar_event (starts_at);

CREATE VIEW vl.v_calendar_event WITH (security_invoker = true) AS
SELECT
    e.id AS event_id,
    e.source_id,
    e.title,
    e.starts_at::date AS start_date,
    e.ends_at::date   AS end_date,
    e.all_day,
    e.venue,
    e.city,
    e.url,
    e.first_seen_at,
    e.last_seen_at,
    -- The calendar mixes meets with courses and meetings; the source has no category for it.
    CASE
        WHEN e.title ~* 'kursus|seminar|uddannelse'      THEN 'kursus'
        WHEN e.title ~* 'møde|generalforsamling'          THEN 'moede'
        ELSE 'staevne'
    END AS kind,
    -- Only known when the source names a country.
    coalesce(lower(trim(e.country)) NOT IN ('danmark', 'denmark', 'dk', ''), false) AS is_abroad,
    -- Added in the last 14 days, but not part of the very first sync (everything is new then).
    e.first_seen_at > now() - interval '14 days'
        AND e.first_seen_at::date > (SELECT min(first_seen_at)::date FROM vl.calendar_event)
        AS is_new
FROM vl.calendar_event e;

GRANT SELECT ON vl.v_calendar_event TO vl_read, vl_write;
