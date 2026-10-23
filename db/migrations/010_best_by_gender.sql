-- 010: "Best of the day" per gender. Sinclair isn't built to compare women with men:
-- in 320 mixed competitions a man had the top Sinclair 311 times. So the website shows
-- the best woman and the best man separately. See docs/decisions.md.

CREATE VIEW vl.v_competition_best_by_gender WITH (security_invoker = true) AS
SELECT DISTINCT ON (competition_id, gender)
    competition_id, gender, lifter_id, sinclair, total, bodyweight
FROM vl.v_entry_result
WHERE sinclair IS NOT NULL AND gender IS NOT NULL
ORDER BY competition_id, gender, sinclair DESC, entry_id;

-- Rebuild the cached summary with both winners. The old best_sinclair columns stay
-- (overall best), so existing queries keep working.
DROP MATERIALIZED VIEW vl.mv_competition_summary;

CREATE MATERIALIZED VIEW vl.mv_competition_summary AS
SELECT
    s.*,
    bf.lifter_id AS best_f_lifter_id,
    bf.sinclair  AS best_f_sinclair,
    bm.lifter_id AS best_m_lifter_id,
    bm.sinclair  AS best_m_sinclair
FROM vl.v_competition_summary s
LEFT JOIN vl.v_competition_best_by_gender bf ON bf.competition_id = s.competition_id AND bf.gender = 'F'
LEFT JOIN vl.v_competition_best_by_gender bm ON bm.competition_id = s.competition_id AND bm.gender = 'M';

CREATE UNIQUE INDEX mv_competition_summary_id ON vl.mv_competition_summary (competition_id);
CREATE UNIQUE INDEX mv_competition_summary_vlstat ON vl.mv_competition_summary (vlstat_id);
CREATE INDEX mv_competition_summary_date ON vl.mv_competition_summary (date DESC);

GRANT SELECT ON vl.v_competition_best_by_gender, vl.mv_competition_summary TO vl_read, vl_write;
