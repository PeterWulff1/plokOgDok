-- 011: Flag entries whose source data can't be right, so they don't become records.
--
-- Two rules (docs/decisions.md):
--   total_mismatch  vlstat's own total differs from the total of its own attempts
--                   (e.g. C&J 199 kg but vlstat's total implies 122 kg).
--   impossible_lift snatch > 2.4 x bodyweight, C&J > 3.1 x bodyweight, or snatch more
--                   than 25 kg above C&J (e.g. a 51 kg lifter with a 245 kg snatch).
--
-- Suspect entries keep their attempts (raw data is never hidden), but their best lifts,
-- total and Sinclair are NULL here. So every view built on v_entry_result (PRs, bests,
-- rankings, club sums) ignores them automatically.

-- vlstat's displayed total, stored as raw source data like reported_age. 0 = no total.
ALTER TABLE vl.entry ADD COLUMN reported_total smallint;

CREATE OR REPLACE VIEW vl.v_entry_result AS
WITH best AS (
    SELECT
        e.id AS entry_id,
        max(a.weight_kg) FILTER (WHERE a.discipline = 'snatch' AND a.is_successful) AS best_snatch,
        max(a.weight_kg) FILTER (WHERE a.discipline = 'cj' AND a.is_successful)     AS best_cj
    FROM vl.entry e
    LEFT JOIN vl.attempt a ON a.entry_id = e.id
    GROUP BY e.id
),
checked AS (
    SELECT
        e.id AS entry_id,
        e.lifter_id,
        e.competition_id,
        c.date,
        l.gender,
        e.bodyweight,
        e.weight_class,
        e.club,
        b.best_snatch,
        b.best_cj,
        CASE
            WHEN nullif(e.reported_total, 0) IS DISTINCT FROM (b.best_snatch + b.best_cj)
                 AND e.reported_total IS NOT NULL
                THEN 'total_mismatch'
            WHEN b.best_snatch > 2.4 * e.bodyweight
              OR b.best_cj     > 3.1 * e.bodyweight
              OR b.best_snatch > b.best_cj + 25
                THEN 'impossible_lift'
        END AS suspect_reason,
        sc.a,
        sc.b
    FROM vl.entry e
    JOIN vl.competition c ON c.id = e.competition_id
    JOIN vl.lifter l      ON l.id = e.lifter_id
    JOIN best b           ON b.entry_id = e.id
    LEFT JOIN vl.sinclair_coefficient sc
           ON sc.gender = l.gender
          AND extract(year FROM c.date) BETWEEN sc.valid_from_year AND sc.valid_to_year
),
scored AS (
    SELECT
        entry_id, lifter_id, competition_id, date, gender, bodyweight, weight_class, club,
        CASE WHEN suspect_reason IS NULL THEN best_snatch END AS best_snatch,
        CASE WHEN suspect_reason IS NULL THEN best_cj END     AS best_cj,
        -- No total unless both disciplines have a made lift.
        CASE WHEN suspect_reason IS NULL THEN best_snatch + best_cj END AS total,
        suspect_reason, a, b
    FROM checked
)
SELECT
    entry_id,
    lifter_id,
    competition_id,
    date,
    gender,
    bodyweight,
    weight_class,
    club,
    best_snatch,
    best_cj,
    total,
    CASE
        WHEN total IS NULL OR bodyweight IS NULL OR a IS NULL THEN NULL
        WHEN bodyweight >= b THEN total::numeric
        ELSE total * power(10, a * power(log(10, bodyweight / b), 2))
    END AS sinclair,
    suspect_reason
FROM scored;
