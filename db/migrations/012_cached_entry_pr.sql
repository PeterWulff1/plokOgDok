-- 012: Cache PR flags. v_entry_pr runs a window over every entry of a lifter, so pages
-- joining it took up to ~1 s. The cached copy is refreshed with the other summaries.

CREATE MATERIALIZED VIEW vl.mv_entry_pr AS SELECT * FROM vl.v_entry_pr;

CREATE UNIQUE INDEX mv_entry_pr_entry ON vl.mv_entry_pr (entry_id);
CREATE INDEX mv_entry_pr_lifter ON vl.mv_entry_pr (lifter_id);
CREATE INDEX mv_entry_pr_competition ON vl.mv_entry_pr (competition_id);

-- Club summary reads the cached flags (same columns as before).
CREATE OR REPLACE VIEW vl.v_competition_club WITH (security_invoker = true) AS
SELECT
    r.competition_id,
    r.club,
    count(*)                                                     AS lifters,
    max(r.sinclair)                                              AS best_sinclair,
    sum(r.sinclair)                                              AS sum_sinclair,
    count(*) FILTER (WHERE p.is_pr_total AND NOT p.is_debut)     AS total_prs
FROM vl.v_entry_result r
JOIN vl.mv_entry_pr p ON p.entry_id = r.entry_id
GROUP BY r.competition_id, r.club;

CREATE OR REPLACE FUNCTION vl.refresh_derived() RETURNS void
LANGUAGE sql
SECURITY DEFINER
SET search_path = ''
AS $$
    REFRESH MATERIALIZED VIEW CONCURRENTLY vl.mv_entry_pr;
    REFRESH MATERIALIZED VIEW CONCURRENTLY vl.mv_competition_summary;
    REFRESH MATERIALIZED VIEW CONCURRENTLY vl.mv_lifter_summary;
$$;

GRANT SELECT ON vl.mv_entry_pr TO vl_read, vl_write;
