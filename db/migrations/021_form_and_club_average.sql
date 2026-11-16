-- 021: "Varm" lifters and average Sinclair per club at a competition. Only adds: every
-- existing column keeps its name and position.
--
-- vl.v_lifter_form (new), one row per lifter:
--   last_pr_date  latest competition where the lifter beat an earlier best snatch, C&J or
--                 total (a debut doesn't count; same rule as 018)
--   is_hot        the lifter set such a PR at their latest competition, and that competition
--                 is within the last 183 days. Shown as a flame by the name.
-- vl.v_lifter_data gets is_hot (last column) and now reads last_pr_date from v_lifter_form.
-- vl.v_competition_club gets avg_sinclair (last column): the mean over the club's lifters
-- with a valid total. The competition page ranks clubs by it instead of sum_sinclair, so a
-- big squad doesn't win on head count alone.

CREATE VIEW vl.v_lifter_form WITH (security_invoker = true) AS
SELECT
    s.lifter_id,
    p.last_pr_date,
    coalesce(p.last_pr_date = s.last_date AND s.last_date > current_date - 183, false) AS is_hot
FROM vl.mv_lifter_summary s
LEFT JOIN (
    SELECT lifter_id, max(date) AS last_pr_date
    FROM vl.mv_entry_pr
    WHERE NOT is_debut AND (is_pr_snatch OR is_pr_cj OR is_pr_total)
    GROUP BY lifter_id
) p ON p.lifter_id = s.lifter_id;

GRANT SELECT ON vl.v_lifter_form TO vl_read, vl_write;

CREATE OR REPLACE VIEW vl.v_lifter_data WITH (security_invoker = true) AS
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
    f.last_pr_date,
    coalesce(f.last_pr_date > current_date - 365, false) AS has_recent_pr,
    CASE
        WHEN r.region IN ('Hovedstaden', 'Sjælland') THEN 'Sjælland'
        WHEN r.region = 'Fyn' THEN 'Fyn'
        WHEN r.region IN ('Sydjylland', 'Midtjylland', 'Nordjylland') THEN 'Jylland'
        WHEN r.region = 'Udland' THEN 'Udland'
    END AS area,
    f.is_hot
FROM vl.mv_lifter_summary s
LEFT JOIN vl.club_region r ON r.club = s.club
LEFT JOIN vl.v_lifter_form f ON f.lifter_id = s.lifter_id;

CREATE OR REPLACE VIEW vl.v_competition_club WITH (security_invoker = true) AS
SELECT
    r.competition_id,
    r.club,
    count(*)                                                     AS lifters,
    max(r.sinclair)                                              AS best_sinclair,
    sum(r.sinclair)                                              AS sum_sinclair,
    count(*) FILTER (WHERE p.is_pr_total AND NOT p.is_debut)     AS total_prs,
    avg(r.sinclair)                                              AS avg_sinclair
FROM vl.v_entry_result r
JOIN vl.mv_entry_pr p ON p.entry_id = r.entry_id
GROUP BY r.competition_id, r.club;
