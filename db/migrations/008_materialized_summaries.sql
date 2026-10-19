-- 008: Cached copies of the two summary views the website hits on every page.
-- Computing them live takes 1-2 s (PR detection over all entries). Data only changes
-- when the seed or the admin page writes, and both call vl.refresh_derived() afterwards.
-- These are caches of views, rebuildable at any time, not stored source data.

CREATE MATERIALIZED VIEW vl.mv_competition_summary AS
SELECT * FROM vl.v_competition_summary;

CREATE UNIQUE INDEX mv_competition_summary_id ON vl.mv_competition_summary (competition_id);
CREATE UNIQUE INDEX mv_competition_summary_vlstat ON vl.mv_competition_summary (vlstat_id);
CREATE INDEX mv_competition_summary_date ON vl.mv_competition_summary (date DESC);

CREATE MATERIALIZED VIEW vl.mv_lifter_summary AS
SELECT s.*, st.stability_percentile
FROM vl.v_lifter_summary s
LEFT JOIN vl.v_lifter_stability st USING (lifter_id);

CREATE UNIQUE INDEX mv_lifter_summary_id ON vl.mv_lifter_summary (lifter_id);
CREATE UNIQUE INDEX mv_lifter_summary_vlstat ON vl.mv_lifter_summary (vlstat_id);

-- Refreshing needs the owner's rights, so the write role calls this function instead.
CREATE FUNCTION vl.refresh_derived() RETURNS void
LANGUAGE sql
SECURITY DEFINER
SET search_path = ''
AS $$
    REFRESH MATERIALIZED VIEW CONCURRENTLY vl.mv_competition_summary;
    REFRESH MATERIALIZED VIEW CONCURRENTLY vl.mv_lifter_summary;
$$;

REVOKE ALL ON FUNCTION vl.refresh_derived() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION vl.refresh_derived() TO vl_write;
GRANT SELECT ON vl.mv_competition_summary, vl.mv_lifter_summary TO vl_read, vl_write;
