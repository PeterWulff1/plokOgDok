-- 013: Two lifter-page stats that replace "comebacks" and "nerves of steel" on the
-- page (those views and columns stay; nothing is dropped).
--
--   hidden_potential  PR snatch + PR C&J (the "super total" across competitions) minus
--                     the best real total. 0 = both PRs were set at the same competition.
--   weigh_in_margin   Average kg below the class ceiling at weigh-in. Only entries in a
--                     class with a ceiling count: "-81kg", "45-49år -81kg", "71 - 81kg"
--                     give 81; "+109kg", "udenfor konkurrence" and NULL are skipped, as are
--                     bodyweights above the ceiling (bad source data).
--
-- Reads only vl.entry and the cached summary, so a single-lifter lookup stays fast.

CREATE VIEW vl.v_lifter_weigh_in WITH (security_invoker = true) AS
WITH classed AS (
    SELECT
        e.lifter_id,
        e.bodyweight,
        (regexp_match(e.weight_class, '-\s*(\d+)\s*kg$'))[1]::numeric AS ceiling
    FROM vl.entry e
    WHERE e.bodyweight IS NOT NULL
)
SELECT
    lifter_id,
    round(avg(ceiling - bodyweight), 1) AS weigh_in_margin,
    count(*)                            AS weigh_ins
FROM classed
WHERE ceiling IS NOT NULL AND bodyweight <= ceiling
GROUP BY lifter_id;

CREATE VIEW vl.v_lifter_potential WITH (security_invoker = true) AS
SELECT
    s.lifter_id,
    s.pr_snatch + s.pr_cj            AS super_total,
    s.pr_snatch + s.pr_cj - s.pr_total AS hidden_potential,
    w.weigh_in_margin,
    coalesce(w.weigh_ins, 0)         AS weigh_ins
FROM vl.mv_lifter_summary s
LEFT JOIN vl.v_lifter_weigh_in w ON w.lifter_id = s.lifter_id;

GRANT SELECT ON vl.v_lifter_weigh_in, vl.v_lifter_potential TO vl_read, vl_write;
