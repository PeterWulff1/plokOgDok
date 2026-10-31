# Architecture decisions

Newest first. Each entry: date, decision, reason, consequences.

## 2026-10-30 — Admin entry grid: name autocomplete pins rows to a lifter

**Decision:** The name cell in the admin entry grid autocompletes from `/admin/loeftere?q=…` (login required, write role, `db/admin.py:search_lifters`). Picking a lifter stores its id in a hidden `lifter_id` column and fills gender, birth year, club (from the lifter's latest competition) and weight class (from the latest competition that had classes, so a CWC doesn't blank it). The filled cells drop out of the Tab order, so typing a meet is name → bodyweight → six attempts. Attempt cells turn green/red as you type. Enter moves to the next row instead of submitting.
- Matching: a row with `lifter_id` is matched by id only and is never ambiguous; an unknown id blocks the row. Without it the old rules apply (vlstat_id, then exact name + gender, else new lifter).
- `lifter_id` is an optional column in `core/manual_entry.py` (`COLUMNS`). The CSV template and help text use `CSV_COLUMNS`, which leave it out.
- Search: every typed word must appear in the name (`ILIKE ALL`, wildcards escaped), names starting with the first word first, then the most recently active.

**Reason:** Typing 13 cells per lifter was slow, and namesakes forced the user to look up a vlstat_id. The class is a suggestion from the last meet (chosen over computing it from bodyweight, which would need class tables per age group and year); it can be overwritten.

**Rejected for now:** adding a whole club or copying an earlier meet's lifters, pasting from Excel, and warnings for typos (e.g. `950`).

## 2026-10-30 — Club roster: filters and sorting in the browser (migration 015)

**Decision:** The club roster is one table (active and former lifters together) with filters for status (Aktive / Tidligere / Alle, default Aktive), gender and age group, and sorting by clicking a column header.
- The page already loads the whole roster in one query (at most ~155 rows), so filtering and sorting run in the browser (`app/static/js/table-tools.js`) with no extra requests. Rows carry `data-status`, `data-gender` and `data-age`; cells carry their raw sort value in `data-v`.
- `table-tools.js` is generic (any `table.sortable[id]` with an optional `form[data-table]`), so other tables can reuse it.
- Without JavaScript the filter form stays hidden and every lifter is listed.
- A lifter's age group is the one in the year of their latest start for the club, so a former lifter who stopped as a junior stays a junior.
- The age-group rule now lives in one SQL function, `vl.age_group(age)`, used by both `v_club_age_profile` and `v_club_lifter.age_group`. The age profile returns exactly the same rows as before.
- No bodyweight column or sort (the user's choice).
- Look (chosen from three rendered proposals): the filters are plain uppercase words like a newspaper's section nav, the chosen one underlined in burgundy (coral underlines mean PR), groups split by vertical rules. The count ("6 af 32 løftere") sits in the section kicker. Only the sorted column header shows an arrow and turns burgundy.

**Reason:** The user wanted to filter by gender and age and sort by snatch, C&J and total without slowing the page.

**Consequences:**
- On mobile, the Stævner, Sinclair and Seneste columns are hidden, so you can't sort by them there.

## 2026-10-29 — Club page `/klub/{slug}` and club search (migration 014)

**Decision:** Clubs get a page with headline numbers (active lifters, lifters, starts, hit rate vs. the national rate), a record board, the top 5 Sinclair results per gender, an age profile per year, the most loyal lifters and the roster (active first, former folded away). The front-page search lists matching clubs above lifters.
- A club is the raw `entry.club` text; there is no club table. The URL slug is derived from the name in `core/clubs.py` (`Århus Atlet Klub` → `aarhus-atlet-klub`) and resolved against `v_club`.
- Results count for the club printed on that entry, so a lifter who changed clubs appears on both pages with the results from each.
- `Andre` and `ingen klub` are vlstat placeholders: no page, no link (`PLACEHOLDER_CLUBS` in `core/clubs.py`, mirrored in `v_club`).
- Club records are open class per gender, not per weight class: the classes changed in 2025, and masters classes would multiply the board. Ties go to whoever lifted it first.
- Age groups don't overlap (unlike IWF's): ungdom ≤ 17, junior 18–20, senior 21–34, master 35+, by age in the competition year from `birth_year` (`vl.age_group`, migration 015).
- "Active" means a start within the last 365 days.
- Search matches club names ignoring Danish spelling (`aarhus` finds `Århus`) in `core.clubs.match_clubs`, over all ~75 clubs from `v_club`; SQL `ILIKE` can't do that.
- Club logos come from `app/static/logos/logos.json`; `vlstat_club` maps a logo to the name vlstat prints where they differ.

**Reason:** The user picked these sections from a list of options and approved a mockup.

**Consequences:**
- The views are live (not materialized). A club page runs seven queries of 0.03–0.2 s each.
- Renaming a club in vlstat's data gives a new page; there is no alias table for club names.

## 2026-10-29 — Lifter page: "hidden potential" and "weigh-in sniper" replace comebacks and nerves (migration 013)

**Decision:** The lifter page shows two new stats instead of "Comebacks" and "Nerver af stål":
- **Skjult potentiale** = PR snatch + PR C&J (from any competitions) minus the best real total (`v_lifter_potential.hidden_potential`). 0 means both PRs came from the same competition.
- **Indvejnings-snigskytte** = average kg below the weight-class ceiling at weigh-in (`v_lifter_weigh_in.weigh_in_margin`). The ceiling is the number in a trailing `-NNkg` of `entry.weight_class` (`-81kg`, `45-49år -81kg`, `71 - 81kg`). Open-ended classes (`+109kg`), `udenfor konkurrence`, NULL classes (gender-only meets) and bodyweights above the ceiling are skipped.

**Reason:** The user preferred these. Comebacks were 0 for most lifters, and the nerves index repeated what the hit-rate board already shows.

**Consequences:**
- `v_lifter_comeback` and the `comebacks`, `comeback_chances` and `nerves_index` columns stay in `mv_lifter_summary` (nothing is dropped). They're just no longer displayed.
- The new views read `vl.entry` and `mv_lifter_summary` only, so they need no refresh and stay fast for one lifter (~0.1 s).
- Lifters who only ever lifted in open-ended or unclassed groups have no weigh-in margin; the page shows "–".

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
