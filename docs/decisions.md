# Architecture decisions

Newest first. Each entry: date, decision, reason, consequences.

## 2026-10-20 — Suspect source data is kept but never becomes a record (migrations 011–012)

**Decision:** `entry.reported_total` stores the total vlstat displays (raw source data, like `reported_age`). `v_entry_result.suspect_reason` flags:
- `total_mismatch`: vlstat's total ≠ the total of its own attempts.
- `impossible_lift`: snatch > 2.4 × bodyweight, C&J > 3.1 × bodyweight, or snatch > C&J + 25 kg.

For flagged entries the view returns NULL for best lifts, total and Sinclair, so PRs, bests, rankings and club sums ignore them automatically. The attempts are still shown, with a "tvivlsomme data" note.

**Reason:** A review found obvious typos at vlstat that became "records": a 51 kg masters lifter with a 245 kg snatch (the women's all-time best Sinclair, 416.5), and a 199 kg C&J where vlstat's own total implied 122 kg. A ratio rule like "C&J much bigger than snatch" was rejected because it also hits real beginners (e.g. 40/80 kg). Result: 11 of 9,107 entries are flagged.

**Not flagged:** 74 entries under 30 kg bodyweight are real child lifters (age 6–8).

**Also:** PR flags are cached as `mv_entry_pr` (migration 012), which cut the slowest pages from ~1 s. `scripts/check_site.py` visits every page and fails on errors or leaked template values. The first full run: 1,988 pages, 0 problems.

## 2026-10-20 — PR marking: coral underline

The raised "PR" text made tables uneven. A PR is now a thick coral underline under the record-setting number (no extra width). The legend above each table says "koral streg = PR".

## 2026-10-20 — Best woman and best man instead of one "best Sinclair"

**Decision:** The front page and competition pages show the best Sinclair per gender (migration 010, `v_competition_best_by_gender`, columns `best_f_*` / `best_m_*` in `mv_competition_summary`).

**Reason:** In the 320 competitions with both genders, a man had the top Sinclair 311 times. Since 2024 the median Sinclair is 175 for women and 248 for men. Sinclair normalises each gender against its own records and isn't meant for comparing across genders.

**Rejected for now:** Q-points (built for cross-gender comparison; the formula would first have to be verified against vlstat's Q-points page) and a "form of the day" score (result relative to the lifter's own record). Both could be added later.

## 2026-10-19 — Admin page; website URLs use our own IDs

**Decision:** `/admin` (password `ADMIN_PASSWORD`) adds competitions from a form or a CSV file (`core/manual_entry.py` holds the column and attempt rules). The flow is always form → preview → save, so nothing is written before you've seen how every row matches a lifter. Public URLs changed from vlstat IDs to our own: `/loefter/{lifter.id}`, `/staevne/{competition.id}`.

**Reason:** Lifters and competitions added by hand have no vlstat ID (migration 009 made `lifter.vlstat_id` nullable), so they couldn't have had a URL. The site isn't public yet, so no links break.

**Rules:**
- Attempts: `95` = made, `95x` or `-95` = missed, blank = no attempt (same "no row" rule as the scraper).
- Lifter matching: by `vlstat_id` if given, otherwise by exact name (case-insensitive) plus gender. Several matches → the row is blocked until a `vlstat_id` is given. No match → new lifter, which requires gender. Existing lifters are never modified.
- Only competitions with `vlstat_id IS NULL` (added here) can be deleted. Lifters that existed only through a deleted competition are removed too.
- Every save and delete calls `vl.refresh_derived()`.
- Security: constant-time password check, lockout after 8 failures in 15 minutes, signed session cookie (`SESSION_SECRET`, SameSite=Strict, 8 hours), CSRF token on every POST, `noindex` on admin pages, write role used only here. Set `HTTPS_ONLY=1` when hosted so the cookie is HTTPS-only.

**Caveat:** If a manually added competition later also appears on vlstat.dk and gets scraped, it'll exist twice. Delete the manual one first.

## 2026-10-19 — Website views, and cached summaries (migrations 006–008)

**Decision:** All website numbers come from views in migration 006 (attempt context, hit rates, PR flags, jumps, streaks, comebacks, lifter and competition summaries, club summaries). The two summaries read on every page are cached as materialized views `mv_lifter_summary` and `mv_competition_summary`. `vl.refresh_derived()` rebuilds them, and the seed calls it at the end. The admin page must call it after every save too.

**Reason:** Computed live, the competition list took 2.2 s and a lifter summary 1.2–1.6 s, because PR detection and the stability ranking run over all entries. Cached, both take ~20 ms. The data only changes on seed or admin save.

**Consequences:**
- Materialized views are caches of views and can be rebuilt any time, so they don't break the "raw data only in tables" rule.
- Migration 007 dropped `stability_percentile` from `v_lifter_summary` (nothing used it yet) and moved it to `v_lifter_stability`, because the cross-lifter window function stopped Postgres from filtering to one lifter.
- PR rule: a result is a PR if it beats everything from *earlier dates*. A lifter's first competition is flagged `is_debut` and not counted as PRs.

## 2026-10-19 — Website: FastAPI + server-rendered HTML instead of Streamlit

**Decision:** The website ("Pløk og Døk") is a FastAPI app with Jinja2 templates, htmx for small interactive bits (search, filters) and Plotly.js for charts. It replaces the plan document's Streamlit.

**Reason:** The user wants a site that doesn't look generic or AI-made. Streamlit's layout and styling are fixed and instantly recognisable. Server-rendered HTML gives full design control, real URLs per lifter and competition (`/loefter/2726`), good mobile behaviour, and keeps all logic in Python, so `core/` is reused unchanged.

**Consequences:**
- The architecture rules carry over unchanged: `app/` only presents data; numbers come from SQL views via `db/queries.py` or from `core/`.
- The public site uses the read-only role; the admin page uses the write role after login.
- Runs locally for now. Hosting is decided later.

## 2026-10-19 — Sinclair after 2024 (supersedes "fitted from vlstat for 2025+")

**Decision (migration 005):** The 2021–2024 set also applies to 2025. 2026–2028 uses a new set fitted from vlstat: men a=0.700752735 b=201.161, women a=0.674119984 b=163.916.

**Evidence** (full harvest, `scripts/fit_sinclair.py`, standard-Sinclair pages only):
- 2019–2024: each year's fit reproduces the official IWF set for its cycle, with rms ~1e-5 (the limit of vlstat's 2-decimal rounding).
- 2026: one clean new set, 844 lifters, rms ~1e-5.
- 2025: no set fits exactly, not even within one competition (rms ~1e-3). Inverting vlstat's points showed it used the 2021 set with a stepped bodyweight lookup (62.52 and 62.54 kg both scored as 62.72 kg). So vlstat's 2025 points are up to ~1 point off. Ours use the exact bodyweight and the 2021 set.

**Consequences:** Our 2025 Sinclair won't match vlstat's to the cent. That's intended. If IWF publishes official post-2024 values, add them in a new migration.

## 2026-10-19 — Parser: gender-only meets, masters and Q-points pages, bad ages

Found while parsing the full harvest (392 pages):
- **133 pages** (CWC, team and Sinclair-only meets) group lifters by gender only ("Mænd"/"Kvinder"), with no weight class. `entry.weight_class` is now nullable (migration 004), with `UNIQUE NULLS NOT DISTINCT` so re-seeding still can't duplicate entries.
- **42 masters pages** label the last column "Masters-sinclair" (age-adjusted) and **1 page** uses "Q-points". The layout is otherwise identical, so they're accepted. `SourceScores.points_kind` records which formula it was, and the Sinclair fit uses only standard pages.
- An age outside 5–110 (one row with age 2) is a typo at vlstat. It's stored as unknown and the entry is kept.
- 2 pages have no results table at vlstat. They're skipped.
- 7 of ~9100 entries have a vlstat total that doesn't match their own attempts (e.g. 217 vs 294). We always compute totals from attempts.

## 2026-10-19 — Scrape only Results.aspx; skip lifter profile pages

**Decision:** Phase 1 harvests one `Results.aspx` page per competition (via the year and competition dropdowns) and nothing else. The planned lifter-profile harvest is dropped.

**Reason:** Looking at vlstat.dk showed that:
- Each results page has, per lifter: vlstat lifter ID (hidden column), name, club, age at the competition, bodyweight, every attempt weight, and a hidden True/False made flag per attempt.
- Gender is in each weight-class header ("-61kg Kvinder", "+109kg Mænd").
- `lifterpopup.aspx?id=...` shows only current age, club and a results list. No birth year, no gender.

**Consequences:**
- About 50 requests per year instead of thousands, and no deduplication logic is needed.
- `lifter.birth_year` is derived from `entry.reported_age`: `competition year - age`, using the smaller value when they differ by one (`core/lifters.py`). It may be one year off for lifters seen only once.
- `entry.reported_age` keeps vlstat's raw age so the derivation can be redone.
- Competition IDs come from the dropdown values on `Results.aspx`. `Stats.aspx` was not used because its competition names aren't unique (128 duplicates).
- vlstat has no competition location, so `competition.location` is NULL for scraped data.
- Attempts shown as `0` are blank attempts and get no row.

## 2026-10-19 — Sinclair coefficients: fitted from vlstat for 2025+

**Decision:** The database holds the IWF 2017–2020 and 2021–2024 cycles. The 2025+ coefficients are fitted from vlstat's published points with `scripts/fit_sinclair.py` after the full harvest, and added in a new migration.

**Reason:** IWF's 2025–2028 coefficients couldn't be found. The fit on 2019 data reproduced the official 2017 values (women a=0.7834, b=153.66; men a=0.7520, b=175.50), which shows the method works and that vlstat uses standard Sinclair. The 2026 women's data gave a≈0.6741, b≈163.92 from only 5 lifters, which is too few to trust yet.

## 2026-10-19 — Tables in schema `vl`; psycopg 3 instead of SQLAlchemy

**Decision:** All tables and views live in schema `vl`. Database access uses psycopg 3 with plain parameterized SQL and numbered migration files.

**Reason:** Supabase auto-exposes the `public` schema through its REST API to anonymous users. A separate schema keeps the data private unless we grant access. Plain SQL keeps views and migrations readable, and the project doesn't need an ORM.

## 2026-10-19 — Attempts without a recorded weight get no row

**Decision:** An `attempt` row is created only when vlstat.dk shows a weight for that attempt. `attempt.weight_kg` is `NOT NULL`.

**Reason:** The plan document allowed two options (no row, or `weight_kg = NULL`). Allowing both would make every hit-rate query handle two cases. The source data also doesn't tell us whether a blank attempt was passed by the lifter or just not recorded, so we can't store a "passed" state truthfully.

**Consequences:**
- A missing row means "no data", never "missed lift".
- `attempt_number` keeps its real value, so a lifter can have attempt 1 and 3 without attempt 2.
- Hit rate = successful rows / existing rows, per attempt number and discipline.
- Statistics about passing attempts aren't possible with this data.
- A unique constraint on (`entry_id`, `discipline`, `attempt_number`) keeps the seed idempotent.
