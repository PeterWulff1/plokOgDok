-- 004: Some competitions (CWC, team and Sinclair-only meets) group lifters by gender only,
-- with no weight class. Allow NULL, and keep (competition, lifter, class) unique with
-- NULL counted as a value, so re-running the seed still never duplicates entries.
-- Needs Postgres 15+ (Supabase runs 17).

ALTER TABLE vl.entry ALTER COLUMN weight_class DROP NOT NULL;

ALTER TABLE vl.entry DROP CONSTRAINT entry_competition_id_lifter_id_weight_class_key;
ALTER TABLE vl.entry
    ADD CONSTRAINT entry_competition_lifter_class_key
    UNIQUE NULLS NOT DISTINCT (competition_id, lifter_id, weight_class);
