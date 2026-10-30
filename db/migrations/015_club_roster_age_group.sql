-- 015: Age group as one shared function, used by the club age profile and the roster
-- filter. Groups don't overlap (unlike IWF's): ungdom <= 17, junior 18-20,
-- senior 21-34, master 35+, 'ukendt' without a birth year.

CREATE FUNCTION vl.age_group(age int) RETURNS text
LANGUAGE sql IMMUTABLE PARALLEL SAFE
AS $$
    SELECT CASE
        WHEN age IS NULL THEN 'ukendt'
        WHEN age <= 17   THEN 'ungdom'
        WHEN age <= 20   THEN 'junior'
        WHEN age <= 34   THEN 'senior'
        ELSE 'master'
    END
$$;

GRANT EXECUTE ON FUNCTION vl.age_group(int) TO vl_read, vl_write;

-- Same columns as in 014; the grouping now comes from vl.age_group.
CREATE OR REPLACE VIEW vl.v_club_age_profile WITH (security_invoker = true) AS
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
    SELECT club, year, vl.age_group(age) AS age_group, count(*) AS lifters
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

-- 014's columns plus age_group: the lifter's group in the year of their latest start
-- for the club (for active lifters that is this year or last).
CREATE OR REPLACE VIEW vl.v_club_lifter WITH (security_invoker = true) AS
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
    max(r.sinclair)                                       AS best_sinclair,
    vl.age_group(extract(year FROM max(r.date))::int - l.birth_year) AS age_group
FROM vl.v_entry_result r
JOIN vl.lifter l ON l.id = r.lifter_id
WHERE r.club IS NOT NULL
GROUP BY r.club, r.lifter_id, l.birth_year;
