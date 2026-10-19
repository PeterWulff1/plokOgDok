-- 007: v_lifter_summary without its cross-lifter ranking. The window function made
-- every single-lifter lookup compute all 1,592 lifters (1.6 s). The ranking moves to
-- its own view. Nothing used the dropped column yet (website not built), so the drop
-- is safe; see docs/decisions.md.

DROP VIEW vl.v_lifter_summary;

CREATE VIEW vl.v_lifter_summary WITH (security_invoker = true) AS
WITH entries AS (
    SELECT
        lifter_id,
        count(*)                AS competitions,
        min(date)               AS first_date,
        max(date)               AS last_date,
        max(best_snatch)        AS pr_snatch,
        max(best_cj)            AS pr_cj,
        max(total)              AS pr_total,
        max(sinclair)           AS pr_sinclair,
        count(total)            AS totals,
        -- Spread of totals relative to their mean; lower = more stable.
        stddev_samp(total) / nullif(avg(total), 0) AS total_cv,
        avg(best_snatch::numeric / nullif(best_cj, 0)) AS snatch_cj_ratio
    FROM vl.v_entry_result
    GROUP BY lifter_id
),
latest AS (
    SELECT DISTINCT ON (lifter_id) lifter_id, club, weight_class, bodyweight
    FROM vl.v_entry_result
    ORDER BY lifter_id, date DESC, entry_id DESC
),
hits AS (
    SELECT
        lifter_id,
        count(*)                                               AS attempts,
        round(avg(is_successful::int), 4)                      AS hit_rate,
        round(avg(is_successful::int) FILTER (WHERE attempt_number = 1), 4) AS hit_rate_1st,
        round(avg(is_successful::int) FILTER (WHERE attempt_number = 3), 4) AS hit_rate_3rd
    FROM vl.v_attempt
    GROUP BY lifter_id
)
SELECT
    l.id AS lifter_id,
    l.vlstat_id,
    l.name,
    l.gender,
    l.birth_year,
    lt.club,
    lt.weight_class,
    lt.bodyweight AS latest_bodyweight,
    en.competitions,
    en.first_date,
    en.last_date,
    en.pr_snatch,
    en.pr_cj,
    en.pr_total,
    en.pr_sinclair,
    round(en.snatch_cj_ratio, 4) AS snatch_cj_ratio,
    h.attempts,
    h.hit_rate,
    h.hit_rate_1st,
    h.hit_rate_3rd,
    -- "Nerves of steel": positive = better on 3rd attempts than on openers.
    h.hit_rate_3rd - h.hit_rate_1st AS nerves_index,
    coalesce(s.longest_made_streak, 0) AS longest_made_streak,
    coalesce(cb.comebacks, 0)          AS comebacks,
    coalesce(cb.chances, 0)            AS comeback_chances,
    -- Only meaningful with enough totals. Ranking across lifters: v_lifter_stability.
    CASE WHEN en.totals >= 4 THEN round(en.total_cv, 4) END AS total_cv
FROM vl.lifter l
JOIN entries en          ON en.lifter_id = l.id
LEFT JOIN latest lt      ON lt.lifter_id = l.id
LEFT JOIN hits h         ON h.lifter_id = l.id
LEFT JOIN vl.v_lifter_streak s   ON s.lifter_id = l.id
LEFT JOIN vl.v_lifter_comeback cb ON cb.lifter_id = l.id;

-- How stable a lifter's totals are compared with everyone else with at least 4 totals.
-- stability_percentile 0 = the most stable of all.
CREATE VIEW vl.v_lifter_stability WITH (security_invoker = true) AS
SELECT
    lifter_id,
    count(total)                                           AS totals,
    round(stddev_samp(total) / nullif(avg(total), 0), 4)   AS total_cv,
    round((percent_rank() OVER (ORDER BY stddev_samp(total) / nullif(avg(total), 0)))::numeric, 4)
        AS stability_percentile
FROM vl.v_entry_result
GROUP BY lifter_id
HAVING count(total) >= 4;

GRANT SELECT ON vl.v_lifter_summary, vl.v_lifter_stability TO vl_read, vl_write;
