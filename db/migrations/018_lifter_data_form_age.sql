-- 018: More filters for the data page (/data). Adds columns to vl.v_lifter_data
-- (017's columns stay, in the same order):
--   age_group      the lifter's group this calendar year (vl.age_group), 'ukendt' without a
--                  birth year. Current age, so juniors today can be found.
--   first_date     debut, the lifter's first competition
--   is_new         debut within the last 365 days
--   last_pr_date   latest competition where the lifter beat an earlier best snatch, C&J or
--                  total. A debut doesn't count: everything there is trivially a PR.
--   has_recent_pr  last_pr_date within the last 365 days ("i form")

CREATE OR REPLACE VIEW vl.v_lifter_data WITH (security_invoker = true) AS
WITH prs AS (
    SELECT lifter_id, max(date) AS last_pr_date
    FROM vl.mv_entry_pr
    WHERE NOT is_debut AND (is_pr_snatch OR is_pr_cj OR is_pr_total)
    GROUP BY lifter_id
)
SELECT
    s.lifter_id,
    s.name,
    s.gender,
    s.birth_year,
    s.club,
    r.region,
    s.latest_bodyweight,
    vl.weight_class_2025(s.gender, s.latest_bodyweight) AS weight_class,
    s.pr_snatch,
    s.pr_cj,
    s.pr_total,
    s.pr_sinclair,
    s.competitions,
    s.last_date,
    s.last_date > current_date - 365 AS is_active,
    vl.age_group(extract(year FROM current_date)::int - s.birth_year) AS age_group,
    s.first_date,
    s.first_date > current_date - 365 AS is_new,
    p.last_pr_date,
    coalesce(p.last_pr_date > current_date - 365, false) AS has_recent_pr
FROM vl.mv_lifter_summary s
LEFT JOIN vl.club_region r ON r.club = s.club
LEFT JOIN prs p ON p.lifter_id = s.lifter_id;
