-- 017: Data page (/data), club changes and club regions.
--
-- 1. vl.lifter_club_change: a lifter's current club when it isn't on vlstat yet, because
--    they changed clubs after their last competition. Raw, manually entered facts. The
--    entries keep the club vlstat printed; the summary shows the new club only while
--    `since` is later than the lifter's last competition, so the next real entry wins.
-- 2. vl.club_region: the DVF region of each club (vl.entry.club text). Raw data from
--    vaegtloeftning.dk/find-klub (read 2026-11-06), which groups member clubs by region.
--    Foreign guest clubs are 'Udland'. Clubs we couldn't place have no row (shown as unknown).
-- 3. vl.weight_class_2025(): the current IWF class (from June 2025) for a bodyweight.
-- 4. vl.v_lifter_data: one row per lifter for the data page's filters.

CREATE TABLE vl.lifter_club_change (
    lifter_id  bigint PRIMARY KEY REFERENCES vl.lifter (id) ON DELETE CASCADE,
    club       text NOT NULL CHECK (btrim(club) <> ''),
    since      date NOT NULL
);

-- Peter Klinge Wulff moved from Bagsværd VK to AK Gotha after Øst B 2026.
INSERT INTO vl.lifter_club_change (lifter_id, club, since)
SELECT id, 'AK Gotha', DATE '2026-11-06' FROM vl.lifter WHERE vlstat_id = 30854;

CREATE TABLE vl.club_region (
    club    text PRIMARY KEY,
    region  text NOT NULL CHECK (region IN (
        'Hovedstaden', 'Sjælland', 'Fyn', 'Sydjylland', 'Midtjylland', 'Nordjylland', 'Udland'
    ))
);

INSERT INTO vl.club_region (club, region) VALUES
    -- Region Hovedstad
    ('IK 99', 'Hovedstaden'),
    ('AK Thor', 'Hovedstaden'),
    ('AK Gotha', 'Hovedstaden'),
    ('Alfa Omega', 'Hovedstaden'),
    ('Gladsaxe Crossfit', 'Hovedstaden'),
    ('Butchers lab', 'Hovedstaden'),
    ('AK Dan', 'Hovedstaden'),
    ('AK Viking', 'Hovedstaden'),
    ('Bagsværd VK', 'Hovedstaden'),
    ('Ålholm IF', 'Hovedstaden'),
    ('VK Valhal', 'Hovedstaden'),
    ('Copenhagen BarBell Club', 'Hovedstaden'),
    -- Region Sjælland
    ('Roskilde AK', 'Sjælland'),
    ('Ringsted IF', 'Sjælland'),
    ('AK Atlas', 'Sjælland'),
    ('VK Esbern Snare', 'Sjælland'),
    ('HG Vægtløftning/Styrkeløft', 'Sjælland'),
    -- Fyn
    ('VK Kono', 'Fyn'),
    ('Svendborg Atlet Club', 'Fyn'),
    -- Sydjylland
    ('VK 49', 'Sydjylland'),
    ('AK Heros', 'Sydjylland'),
    -- Midtjylland
    ('VK Heden', 'Midtjylland'),
    ('Holstebro styrkesport', 'Midtjylland'),
    ('Århus Atlet Klub', 'Midtjylland'),
    ('Århus Crossfit Vægtløftning', 'Midtjylland'),
    ('Århus Styrke og Vægtløfter klub', 'Midtjylland'),
    ('VK Herkules', 'Midtjylland'),
    ('VL365', 'Midtjylland'),
    ('Spartan Mentality Vægtløftning', 'Midtjylland'),
    ('WL 8600', 'Midtjylland'),
    ('VL 8500', 'Midtjylland'),
    -- Nordjylland
    ('AK Teutonia', 'Nordjylland'),
    ('Aalborg VLF', 'Nordjylland'),
    ('AK Jyden', 'Nordjylland'),
    ('Sportshøjskolen', 'Nordjylland'),
    ('Boxen Athlete Club', 'Nordjylland'),
    ('Hobro SVF', 'Nordjylland'),
    -- Guest clubs from abroad
    ('Brandenburg', 'Udland'),
    ('Tønsberg', 'Udland'),
    ('Maidstone', 'Udland'),
    ('Fysiken AK', 'Udland'),
    ('Swedish Weightlifting Federation', 'Udland'),
    ('Herrnburger Athletenverein 77', 'Udland'),
    ('St Birinus', 'Udland'),
    ('Stavanger VK', 'Udland'),
    ('Landskrona Atletklubb', 'Udland'),
    ('Trelleborgs ABK', 'Udland'),
    ('AK Bjørgvin', 'Udland'),
    ('CF Santry', 'Udland'),
    ('Tambarskjelvar IL', 'Udland'),
    ('Eskildstuna TK', 'Udland'),
    ('Falu AK', 'Udland'),
    ('Frankfurt', 'Udland'),
    ('Klippans AK', 'Udland'),
    ('Larvik Atletklubb', 'Udland'),
    ('Olofströms FK', 'Udland'),
    ('Oslo Atletklubb', 'Udland'),
    ('Spydeberg Atletene', 'Udland'),
    ('USC Dornbirn', 'Udland');

-- Same body as migration 007; only `club` changes, to honour vl.lifter_club_change.
CREATE OR REPLACE VIEW vl.v_lifter_summary WITH (security_invoker = true) AS
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
    CASE WHEN cc.since > en.last_date THEN cc.club ELSE lt.club END AS club,
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
    h.hit_rate_3rd - h.hit_rate_1st AS nerves_index,
    coalesce(s.longest_made_streak, 0) AS longest_made_streak,
    coalesce(cb.comebacks, 0)          AS comebacks,
    coalesce(cb.chances, 0)            AS comeback_chances,
    CASE WHEN en.totals >= 4 THEN round(en.total_cv, 4) END AS total_cv
FROM vl.lifter l
JOIN entries en          ON en.lifter_id = l.id
LEFT JOIN latest lt      ON lt.lifter_id = l.id
LEFT JOIN hits h         ON h.lifter_id = l.id
LEFT JOIN vl.v_lifter_streak s   ON s.lifter_id = l.id
LEFT JOIN vl.v_lifter_comeback cb ON cb.lifter_id = l.id
LEFT JOIN vl.lifter_club_change cc ON cc.lifter_id = l.id;

REFRESH MATERIALIZED VIEW vl.mv_lifter_summary;

-- IWF bodyweight classes from June 2025: '-81' style labels, '+110' above the top class.
CREATE FUNCTION vl.weight_class_2025(gender char(1), bodyweight numeric) RETURNS text
LANGUAGE sql IMMUTABLE
AS $$
    SELECT CASE
        WHEN bodyweight IS NULL OR gender IS NULL THEN NULL
        WHEN bodyweight > top THEN '+' || top
        ELSE '-' || (SELECT min(c) FROM unnest(ceilings) c WHERE bodyweight <= c)
    END
    FROM (
        SELECT CASE gender
                   WHEN 'F' THEN ARRAY[48, 53, 58, 63, 69, 77, 86]
                   ELSE ARRAY[60, 65, 71, 79, 88, 94, 110]
               END AS ceilings,
               CASE gender WHEN 'F' THEN 86 ELSE 110 END AS top
    ) k
$$;

-- One row per lifter: current club and region, class from the latest weigh-in, all-time
-- PRs, and whether they competed within the last 365 days (same rule as the club roster).
CREATE VIEW vl.v_lifter_data WITH (security_invoker = true) AS
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
    s.last_date > current_date - 365 AS is_active
FROM vl.mv_lifter_summary s
LEFT JOIN vl.club_region r ON r.club = s.club;

GRANT SELECT ON vl.lifter_club_change, vl.club_region, vl.v_lifter_data TO vl_read, vl_write;
GRANT EXECUTE ON FUNCTION vl.weight_class_2025(char, numeric) TO vl_read, vl_write;
