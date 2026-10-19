-- 006: Views for the website (lifter profiles, competition pages, fun stats).
-- All derived numbers live here, never in app/. security_invoker so the caller's
-- privileges apply (Supabase best practice), even though `vl` isn't API-exposed.

-- One row per attempt with its context and the previous attempt in the same discipline.
CREATE VIEW vl.v_attempt WITH (security_invoker = true) AS
SELECT
    a.id AS attempt_id,
    a.entry_id,
    e.lifter_id,
    e.competition_id,
    c.date,
    a.discipline,
    a.attempt_number,
    a.weight_kg,
    a.is_successful,
    lag(a.weight_kg) OVER w     AS prev_weight_kg,
    lag(a.is_successful) OVER w AS prev_successful,
    a.weight_kg - lag(a.weight_kg) OVER w AS jump_kg
FROM vl.attempt a
JOIN vl.entry e       ON e.id = a.entry_id
JOIN vl.competition c ON c.id = e.competition_id
WINDOW w AS (PARTITION BY a.entry_id, a.discipline ORDER BY a.attempt_number);

-- Hit rate per lifter, discipline and attempt number.
CREATE VIEW vl.v_lifter_hit_rate WITH (security_invoker = true) AS
SELECT
    lifter_id,
    discipline,
    attempt_number,
    count(*)                                   AS attempts,
    count(*) FILTER (WHERE is_successful)      AS made,
    round(avg(is_successful::int), 4)          AS hit_rate
FROM vl.v_attempt
GROUP BY lifter_id, discipline, attempt_number;

-- Per entry: was this a new personal record at the time? Compared with all earlier
-- competitions only (same-day entries don't count as "earlier").
CREATE VIEW vl.v_entry_pr WITH (security_invoker = true) AS
WITH prior AS (
    SELECT
        r.*,
        max(r.best_snatch) OVER p AS prior_snatch,
        max(r.best_cj)     OVER p AS prior_cj,
        max(r.total)       OVER p AS prior_total
    FROM vl.v_entry_result r
    WINDOW p AS (PARTITION BY r.lifter_id ORDER BY r.date
                 RANGE BETWEEN UNBOUNDED PRECEDING AND '1 day'::interval PRECEDING)
)
SELECT
    entry_id,
    lifter_id,
    competition_id,
    date,
    best_snatch,
    best_cj,
    total,
    sinclair,
    (best_snatch > coalesce(prior_snatch, 0)) AS is_pr_snatch,
    (best_cj     > coalesce(prior_cj, 0))     AS is_pr_cj,
    (total       > coalesce(prior_total, 0))  AS is_pr_total,
    -- First competition: everything is a PR, but that isn't news.
    (prior_snatch IS NULL AND prior_cj IS NULL AND prior_total IS NULL) AS is_debut
FROM prior;

-- Weight jumps between consecutive attempts (same entry, same discipline).
CREATE VIEW vl.v_lifter_jump WITH (security_invoker = true) AS
SELECT
    lifter_id,
    discipline,
    jump_kg,
    count(*)                              AS times,
    count(*) FILTER (WHERE is_successful) AS made
FROM vl.v_attempt
WHERE jump_kg IS NOT NULL
GROUP BY lifter_id, discipline, jump_kg;

-- Longest run of consecutive made attempts across a lifter's career
-- (ordered by date, competition, snatch before C&J, attempt number).
CREATE VIEW vl.v_lifter_streak WITH (security_invoker = true) AS
WITH ordered AS (
    SELECT
        lifter_id,
        is_successful,
        row_number() OVER (PARTITION BY lifter_id
                           ORDER BY date, competition_id, discipline DESC, attempt_number) AS rn
    FROM vl.v_attempt
),
islands AS (
    SELECT
        lifter_id,
        rn - row_number() OVER (PARTITION BY lifter_id ORDER BY rn) AS island
    FROM ordered
    WHERE is_successful
)
SELECT lifter_id, max(len) AS longest_made_streak
FROM (SELECT lifter_id, island, count(*) AS len FROM islands GROUP BY lifter_id, island) s
GROUP BY lifter_id;

-- Comebacks: made the 3rd attempt after missing both the 1st and 2nd.
CREATE VIEW vl.v_lifter_comeback WITH (security_invoker = true) AS
SELECT
    lifter_id,
    count(*) FILTER (WHERE third_made)  AS comebacks,
    count(*)                            AS chances
FROM (
    SELECT
        lifter_id, entry_id, discipline,
        bool_or(attempt_number = 3 AND is_successful) AS third_made
    FROM vl.v_attempt
    GROUP BY lifter_id, entry_id, discipline
    HAVING bool_or(attempt_number = 1 AND NOT is_successful)
       AND bool_or(attempt_number = 2 AND NOT is_successful)
       AND bool_or(attempt_number = 3)
) t
GROUP BY lifter_id;

-- One row per lifter: headline numbers for the profile and the search results.
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
    -- Only meaningful with enough totals; 0 = most stable of all such lifters.
    CASE WHEN en.totals >= 4 THEN round(en.total_cv, 4) END AS total_cv,
    CASE WHEN en.totals >= 4 THEN
        round((percent_rank() OVER (PARTITION BY (en.totals >= 4) ORDER BY en.total_cv))::numeric, 4)
    END AS stability_percentile
FROM vl.lifter l
JOIN entries en          ON en.lifter_id = l.id
LEFT JOIN latest lt      ON lt.lifter_id = l.id
LEFT JOIN hits h         ON h.lifter_id = l.id
LEFT JOIN vl.v_lifter_streak s   ON s.lifter_id = l.id
LEFT JOIN vl.v_lifter_comeback cb ON cb.lifter_id = l.id;

-- One row per competition: headline numbers for the front page and competition page.
CREATE VIEW vl.v_competition_summary WITH (security_invoker = true) AS
WITH att AS (
    SELECT
        competition_id,
        count(*)                               AS attempts,
        round(avg(is_successful::int), 4)      AS hit_rate
    FROM vl.v_attempt
    GROUP BY competition_id
),
ent AS (
    SELECT
        competition_id,
        count(*)                               AS lifters,
        count(DISTINCT club)                   AS clubs,
        max(sinclair)                          AS best_sinclair
    FROM vl.v_entry_result
    GROUP BY competition_id
),
prs AS (
    SELECT competition_id,
           count(*) FILTER (WHERE NOT is_debut AND (is_pr_snatch OR is_pr_cj OR is_pr_total)) AS lifters_with_pr
    FROM vl.v_entry_pr
    GROUP BY competition_id
),
best AS (
    SELECT DISTINCT ON (competition_id) competition_id, lifter_id AS best_sinclair_lifter_id
    FROM vl.v_entry_result
    WHERE sinclair IS NOT NULL
    ORDER BY competition_id, sinclair DESC
)
SELECT
    c.id AS competition_id,
    c.vlstat_id,
    c.name,
    c.date,
    c.location,
    coalesce(ent.lifters, 0)  AS lifters,
    coalesce(ent.clubs, 0)    AS clubs,
    coalesce(att.attempts, 0) AS attempts,
    att.hit_rate,
    ent.best_sinclair,
    best.best_sinclair_lifter_id,
    coalesce(prs.lifters_with_pr, 0) AS lifters_with_pr
FROM vl.competition c
LEFT JOIN att  ON att.competition_id = c.id
LEFT JOIN ent  ON ent.competition_id = c.id
LEFT JOIN prs  ON prs.competition_id = c.id
LEFT JOIN best ON best.competition_id = c.id;

-- Per competition and club.
CREATE VIEW vl.v_competition_club WITH (security_invoker = true) AS
SELECT
    r.competition_id,
    r.club,
    count(*)                                                     AS lifters,
    max(r.sinclair)                                              AS best_sinclair,
    sum(r.sinclair)                                              AS sum_sinclair,
    count(*) FILTER (WHERE p.is_pr_total AND NOT p.is_debut)     AS total_prs
FROM vl.v_entry_result r
JOIN vl.v_entry_pr p ON p.entry_id = r.entry_id
GROUP BY r.competition_id, r.club;

GRANT SELECT ON
    vl.v_attempt, vl.v_lifter_hit_rate, vl.v_entry_pr, vl.v_lifter_jump, vl.v_lifter_streak,
    vl.v_lifter_comeback, vl.v_lifter_summary, vl.v_competition_summary, vl.v_competition_club
TO vl_read, vl_write;
