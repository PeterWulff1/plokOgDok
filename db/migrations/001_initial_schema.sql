-- 001: Initial schema. Raw source data only; derived values live in views (see 003).
-- Tables live in schema `vl`, not `public`, so Supabase's auto-generated REST API
-- does not expose them to the anon role.

CREATE SCHEMA IF NOT EXISTS vl;

CREATE TABLE vl.lifter (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    vlstat_id   integer  NOT NULL UNIQUE,
    name        text     NOT NULL,
    gender      char(1)  CHECK (gender IN ('M', 'F')),
    -- Derived once at seed time from the age vlstat shows per competition. NULL if unknown.
    birth_year  smallint CHECK (birth_year BETWEEN 1900 AND 2100)
);

CREATE TABLE vl.competition (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    -- NULL for competitions entered manually via the admin page.
    vlstat_id   integer UNIQUE,
    name        text    NOT NULL,
    date        date    NOT NULL,
    location    text
);

CREATE INDEX competition_date_idx ON vl.competition (date);

CREATE TABLE vl.entry (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    lifter_id       bigint NOT NULL REFERENCES vl.lifter (id) ON DELETE RESTRICT,
    competition_id  bigint NOT NULL REFERENCES vl.competition (id) ON DELETE CASCADE,
    bodyweight      numeric(5, 2) CHECK (bodyweight > 0 AND bodyweight < 400),
    weight_class    text   NOT NULL,
    club            text,
    -- Age exactly as vlstat shows it for this competition (raw source value).
    reported_age    smallint CHECK (reported_age BETWEEN 5 AND 110),
    UNIQUE (competition_id, lifter_id, weight_class)
);

CREATE INDEX entry_lifter_idx ON vl.entry (lifter_id);

CREATE TABLE vl.attempt (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entry_id        bigint   NOT NULL REFERENCES vl.entry (id) ON DELETE CASCADE,
    discipline      text     NOT NULL CHECK (discipline IN ('snatch', 'cj')),
    attempt_number  smallint NOT NULL CHECK (attempt_number BETWEEN 1 AND 3),
    -- Only attempts with a recorded weight get a row (docs/decisions.md).
    weight_kg       smallint NOT NULL CHECK (weight_kg > 0 AND weight_kg < 400),
    is_successful   boolean  NOT NULL,
    UNIQUE (entry_id, discipline, attempt_number)
);

CREATE TABLE vl.sinclair_coefficient (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    gender           char(1)        NOT NULL CHECK (gender IN ('M', 'F')),
    a                numeric(12, 9) NOT NULL,
    b                numeric(7, 3)  NOT NULL CHECK (b > 0),
    valid_from_year  smallint       NOT NULL,
    valid_to_year    smallint       NOT NULL,
    CHECK (valid_from_year <= valid_to_year),
    UNIQUE (gender, valid_from_year)
);

-- IWF Sinclair cycles. 2025-2028 is not published yet as far as we know;
-- fit it from vlstat's data with scripts/fit_sinclair.py and add it in a new migration.
INSERT INTO vl.sinclair_coefficient (gender, a, b, valid_from_year, valid_to_year) VALUES
    ('M', 0.751945030, 175.508, 2017, 2020),
    ('F', 0.783497476, 153.655, 2017, 2020),
    ('M', 0.722762521, 193.609, 2021, 2024),
    ('F', 0.787004341, 153.757, 2021, 2024);
