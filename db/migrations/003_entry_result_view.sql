-- 003: Per-entry results: best lifts, total and Sinclair, all computed from raw attempts.
-- Must match core/scoring.py (tests compare both against vlstat's own numbers).

CREATE VIEW vl.v_entry_result AS
WITH best AS (
    SELECT
        e.id AS entry_id,
        max(a.weight_kg) FILTER (WHERE a.discipline = 'snatch' AND a.is_successful) AS best_snatch,
        max(a.weight_kg) FILTER (WHERE a.discipline = 'cj' AND a.is_successful)     AS best_cj
    FROM vl.entry e
    LEFT JOIN vl.attempt a ON a.entry_id = e.id
    GROUP BY e.id
),
scored AS (
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
        -- No total unless both disciplines have a made lift.
        b.best_snatch + b.best_cj AS total,
        sc.a,
        sc.b
    FROM vl.entry e
    JOIN vl.competition c ON c.id = e.competition_id
    JOIN vl.lifter l      ON l.id = e.lifter_id
    JOIN best b           ON b.entry_id = e.id
    LEFT JOIN vl.sinclair_coefficient sc
           ON sc.gender = l.gender
          AND extract(year FROM c.date) BETWEEN sc.valid_from_year AND sc.valid_to_year
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
    END AS sinclair
FROM scored;

GRANT SELECT ON vl.v_entry_result TO vl_read, vl_write;
