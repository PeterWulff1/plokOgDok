-- 009: Lifters added through the admin page may not exist on vlstat.dk, so they have no
-- vlstat_id. Uniqueness stays for the ones that do (NULLs don't collide).

ALTER TABLE vl.lifter ALTER COLUMN vlstat_id DROP NOT NULL;
