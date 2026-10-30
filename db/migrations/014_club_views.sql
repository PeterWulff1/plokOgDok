-- 014: Club page (/klub/{slug}). A club is the raw `entry.club` text; there is no club
-- table. Every view is keyed on that text, so `WHERE club = %s` reaches the base tables.
--
-- 'Andre' and 'ingen klub' are vlstat placeholders, not clubs; they get no page
-- (mirrored in core/clubs.py PLACEHOLDER_CLUBS).
--
-- Stats are per club stint: a lifter's results count for the club printed on that entry,
-- so a lifter who changed clubs shows up on both pages with the results from each.

-- One row per club: the headline numbers and the search index.
CREATE VIEW vl.v_club WITH (security_invoker = true) AS
SELECT
    e.club,
    count(*)                                                       AS starts,
    count(DISTINCT e.lifter_id)                                    AS lifters,
    count(DISTINCT e.lifter_id) FILTER (WHERE c.date > current_date - 365) AS active_lifters,
    count(DISTINCT e.lifter_id) FILTER (WHERE l.gender = 'F')      AS women,
    count(DISTINCT e.lifter_id) FILTER (WHERE l.gender = 'M')      AS men,
    count(DISTINCT e.competition_id)                               AS competitions,
    min(c.date)                                                    AS first_date,
    max(c.date)                                                    AS last_date
FROM vl.entry e
JOIN vl.competition c ON c.id = e.competition_id
JOIN vl.lifter l      ON l.id = e.lifter_id
WHERE e.club IS NOT NULL AND e.club NOT IN ('Andre', 'ingen klub')
GROUP BY e.club;

-- Hit rate per club, next to the national rate over every recorded attempt.
CREATE VIEW vl.v_club_hit_rate WITH (security_invoker = true) AS
WITH per_club AS (
    SELECT
        e.club,
        count(*)                              AS attempts,
        count(*) FILTER (WHERE a.is_successful) AS made
    FROM vl.attempt a
    JOIN vl.entry e ON e.id = a.entry_id
    GROUP BY e.club
),
with_national AS (
    SELECT
        club,
        attempts,
        made,
        round(made::numeric / attempts, 4)                         AS hit_rate,
        round(sum(made) OVER () / sum(attempts) OVER (), 4)       AS national_hit_rate
    FROM per_club
)
SELECT * FROM with_national WHERE club IS NOT NULL;

-- Club records: best snatch, C&J, total and Sinclair per gender, open class. Ties go to
-- whoever lifted it first. Suspect entries have NULL results, so they never count.
CREATE VIEW vl.v_club_record WITH (security_invoker = true) AS
WITH lifts AS (
    SELECT r.*, x.kind, x.value
    FROM vl.v_entry_result r
    CROSS JOIN LATERAL (VALUES
        ('snatch',   r.best_snatch::numeric),
        ('cj',       r.best_cj::numeric),
        ('total',    r.total::numeric),
        ('sinclair', r.sinclair)
    ) AS x (kind, value)
    WHERE r.club IS NOT NULL AND x.value IS NOT NULL
)
SELECT DISTINCT ON (club, gender, kind)
    club, gender, kind, value, lifter_id, entry_id, competition_id, date,
    weight_class, bodyweight, best_snatch, best_cj
FROM lifts
ORDER BY club, gender, kind, value DESC, date, entry_id;

-- Each lifter's best Sinclair result for the club, ranked per gender.
CREATE VIEW vl.v_club_top_sinclair WITH (security_invoker = true) AS
WITH best AS (
    SELECT DISTINCT ON (club, lifter_id)
        club, lifter_id, gender, entry_id, competition_id, date,
        sinclair, total, bodyweight
    FROM vl.v_entry_result
    WHERE club IS NOT NULL AND sinclair IS NOT NULL
    ORDER BY club, lifter_id, sinclair DESC, date
)
SELECT
    *,
    row_number() OVER (PARTITION BY club, gender ORDER BY sinclair DESC, date) AS rank
FROM best;

-- One row per club and lifter: the roster and "trofaste" lists.
CREATE VIEW vl.v_club_lifter WITH (security_invoker = true) AS
SELECT
    r.club,
    r.lifter_id,
    count(*)                                              AS starts,
    min(r.date)                                           AS first_date,
    max(r.date)                                           AS last_date,
    round((max(r.date) - min(r.date)) / 365.25, 1)        AS years,
    max(r.date) > current_date - 365                      AS is_active,
    (array_agg(r.weight_class ORDER BY r.date DESC, r.entry_id DESC))[1] AS weight_class,
    max(r.best_snatch)                                    AS best_snatch,
    max(r.best_cj)                                        AS best_cj,
    max(r.total)                                          AS best_total,
    max(r.sinclair)                                       AS best_sinclair
FROM vl.v_entry_result r
WHERE r.club IS NOT NULL
GROUP BY r.club, r.lifter_id;

-- Lifters per year by age group (age in the competition year, from birth_year).
-- Groups don't overlap, unlike IWF's: ungdom <= 17, junior 18-20, senior 21-34,
-- master 35+. share_of_max = group size / the club's busiest year, for bar heights.
CREATE VIEW vl.v_club_age_profile WITH (security_invoker = true) AS
WITH aged AS (
    SELECT DISTINCT
        e.club,
        extract(year FROM c.date)::int AS year,
        e.lifter_id,
        extract(year FROM c.date)::int - l.birth_year AS age
    FROM vl.entry e
    JOIN vl.competition c ON c.id = e.competition_id
    JOIN vl.lifter l      ON l.id = e.lifter_id
    WHERE e.club IS NOT NULL
),
grouped AS (
    SELECT
        club,
        year,
        CASE
            WHEN age IS NULL THEN 'ukendt'
            WHEN age <= 17   THEN 'ungdom'
            WHEN age <= 20   THEN 'junior'
            WHEN age <= 34   THEN 'senior'
            ELSE 'master'
        END AS age_group,
        count(*) AS lifters
    FROM aged
    GROUP BY 1, 2, 3
),
per_year AS (
    SELECT
        g.*,
        sum(lifters) OVER (PARTITION BY club, year) AS year_lifters
    FROM grouped g
)
SELECT
    club,
    year,
    age_group,
    CASE age_group
        WHEN 'ungdom' THEN 1 WHEN 'junior' THEN 2 WHEN 'senior' THEN 3
        WHEN 'master' THEN 4 ELSE 5
    END AS group_order,
    lifters,
    year_lifters,
    round(lifters / max(year_lifters) OVER (PARTITION BY club), 4) AS share_of_max
FROM per_year;

GRANT SELECT ON vl.v_club, vl.v_club_hit_rate, vl.v_club_record, vl.v_club_top_sinclair,
    vl.v_club_lifter, vl.v_club_age_profile TO vl_read, vl_write;
