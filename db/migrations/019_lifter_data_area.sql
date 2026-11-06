-- 019: The data page filters on three parts of the country instead of DVF's regions.
-- Adds `area` to vl.v_lifter_data (018's columns stay, in the same order):
--   Sjælland  Region Hovedstad and Region Sjælland (DVF regions)
--   Fyn       Fyn
--   Jylland   Sydjylland, Midtjylland and Nordjylland
--   Udland    foreign guest clubs (shown, not offered as a filter)
-- NULL for clubs without a region. vl.club_region keeps DVF's regions as the raw data.

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
    coalesce(p.last_pr_date > current_date - 365, false) AS has_recent_pr,
    CASE
        WHEN r.region IN ('Hovedstaden', 'Sjælland') THEN 'Sjælland'
        WHEN r.region = 'Fyn' THEN 'Fyn'
        WHEN r.region IN ('Sydjylland', 'Midtjylland', 'Nordjylland') THEN 'Jylland'
        WHEN r.region = 'Udland' THEN 'Udland'
    END AS area
FROM vl.mv_lifter_summary s
LEFT JOIN vl.club_region r ON r.club = s.club
LEFT JOIN prs p ON p.lifter_id = s.lifter_id;
