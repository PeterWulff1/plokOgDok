-- 005: Sinclair coefficients after 2024, based on fitting vlstat's own published points
-- (scripts/fit_sinclair.py over the full 2019-2026 harvest). See docs/decisions.md.
--
-- 2025: vlstat still used the 2021-2024 set (with a rounded bodyweight lookup, so its
--       points are up to ~1 point off; ours use the exact bodyweight).
-- 2026+: a new set. Fitted on 844 lifters; reproduces vlstat to the rounding of its
--        2-decimal points. Replace with the official IWF values if they're published.

UPDATE vl.sinclair_coefficient SET valid_to_year = 2025 WHERE valid_from_year = 2021;

INSERT INTO vl.sinclair_coefficient (gender, a, b, valid_from_year, valid_to_year) VALUES
    ('M', 0.700752735, 201.161, 2026, 2028),
    ('F', 0.674119984, 163.916, 2026, 2028);
