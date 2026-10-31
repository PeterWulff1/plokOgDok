# CLAUDE.md — Dansk Vægtløftning Analyse-app

Analytics app for Danish weightlifting results (2019 onward), built as a supplement to `vlstat.dk`.
The full specification is in `docs/plandokument.md` (Danish). Read the section you need instead of the whole file.

**Guiding principle:** data quality, stable operation and being gentle with vlstat.dk always beat shipping features fast.

## Stack

- Python 3.12+, `pytest`, `ruff`
- Scraper: `Playwright` (sync, single thread) + `BeautifulSoup4`
- Validation: `Pydantic` v2
- Database: PostgreSQL on Supabase, via `psycopg` 3 with plain SQL (no ORM)
- Website: `FastAPI` + `Jinja2` templates + `htmx` + `Plotly.js`, server-rendered (replaces Streamlit, see `docs/decisions.md`)
- Environment: `uv` (`uv sync`, `uv run ...`)

## Project layout

```
scraper/fetch_raw.py      # Phase 1: save Results.aspx pages to data/raw_html/ (local only, gitignored)
scraper/parse_results.py  # Pure parser: one saved page -> Entry models; RAW_DIR, strip_state_fields
scraper/parse_and_seed.py # Phase 2: parse all saved pages, upsert into the database
scraper/fetch_calendar.py # Daily sync of vaegtloeftning.dk/kalender (events API) into vl.calendar_event
db/migrations/            # Numbered SQL files: schema, roles, views. Never edit an applied one.
db/migrate.py             # Applies pending migrations
core/models.py            # Shared Pydantic models (Lifter, Competition, Entry, Attempt)
core/scoring.py           # Totals and Sinclair. Must match the SQL view.
core/lifters.py           # Birth year and gender resolution
core/clubs.py             # Club slugs, placeholder clubs, club search matching
scripts/fit_sinclair.py   # Recovers vlstat's Sinclair coefficients from saved pages
db/queries.py             # Read-only queries the website uses (views only, returns plain data)
db/admin.py               # Write side for the admin page (write role only)
core/manual_entry.py      # CSV/form input rules for the admin page
app/                      # FastAPI routes, templates/, static/. Presentation only.
tests/                    # pytest; fixtures/ holds small HTML samples without __VIEWSTATE
data/raw_html/competitions/{year}/{vlstat_id}.html + index.json   # Not committed
docs/                     # plandokument.md, decisions.md
```

## Commands

- Tests: `uv run python -m pytest` (use `python -m`; the `pytest` launcher can fail on Windows)
- DB tests: set `TEST_DATABASE_URL` to a throwaway Postgres (see `tests/test_database.py`)
- Lint/format: `uv run ruff check . --fix && uv run ruff format .`
- Migrate: `uv run python -m db.migrate` (uses `DATABASE_URL_ADMIN`; setup in `docs/supabase-setup.md`)
- Check connections and permissions: `uv run python -m db.check`
- Phase 1 harvest: `uv run python -m scraper.fetch_raw [--from 2019 --to 2026 --limit N]`
- Phase 2 check: `uv run python -m scraper.parse_and_seed --dry-run`
- Phase 2 seed: `uv run python -m scraper.parse_and_seed`
- Sinclair fit: `uv run python -m scripts.fit_sinclair`
- Calendar sync: `uv run python -m scraper.fetch_calendar [--dry-run]` (runs daily via the Windows task "PloekOgDoek kalender-sync")
- Check every page of the site: `uv run python -m scripts.check_site` (run after UI or view changes)
- Static site for GitHub Pages: `uv run python -m scripts.build_static --base plokOgDok` (writes `site/`); preview with `--serve 8040`. Published nightly by `.github/workflows/pages.yml`
- Run website: `uv run uvicorn app.main:app --reload` (then http://127.0.0.1:8000)
- Admin: http://127.0.0.1:8000/admin (password `ADMIN_PASSWORD` in `.env`)

## Architecture rules (binding)

The three layers only talk through the database and the `core` package's public functions.

1. **Data layer** (`scraper/`, `db/`): fetching, raw HTML storage, Pydantic validation, idempotent loads, migrations, roles and SQL views.
2. **Business logic** (`core/`): formulas (Sinclair, totals), validation rules and the shared Pydantic models. Pure Python. No web framework imports.
3. **Presentation** (`app/`): only displays data. It calls `core` and `db/queries.py`, which reads SQL views.

- **No calculations in `app/`** (routes or templates). No Sinclair, totals, hit rates or rankings there. If a page needs a number, add a function in `core/` or a SQL view.
- **Reuse existing models.** Before you create a Pydantic model, type or constant, search `core/` for one that already exists. Never create overlapping models.
- **Keep changes focused.** Change only what the current task needs. Don't refactor nearby code unasked.
- **Backwards compatibility.** Never break an existing SQL view or table. Add columns or views; don't rename or drop them without an explicit decision written in `docs/`.

## Data model invariants

Tables hold **raw source data only**. Never store derived values (total, Sinclair points, placement, hit rate) as columns. Compute them in SQL views or in `core/`.

All tables live in schema `vl` (not `public`, so Supabase's REST API doesn't expose them).

- `lifter`: `id`, `vlstat_id` (unique), `name`, `gender` (`'M'`/`'F'`), `birth_year`
- `competition`: `id`, `vlstat_id` (unique, NULL for manual entries), `name`, `date`, `location` (vlstat has none)
- `entry`: `lifter_id`, `competition_id`, `bodyweight`, `weight_class` (NULL at gender-only meets like CWC), `club`, `reported_age` (raw age vlstat shows)
- `attempt`: `entry_id`, `discipline` (`'snatch'` | `'cj'`), `attempt_number` (1–3), `weight_kg` (int), `is_successful` (bool)
- `sinclair_coefficient`: `a`, `b`, `gender`, `valid_from_year`, `valid_to_year`

Rules:
- **Attempts without a recorded weight get no row.** `weight_kg` is `NOT NULL`. The source doesn't say whether a blank attempt was passed or simply not recorded, so a missing row means "no data", never "missed". A lifter can have attempt 3 without attempt 2. Hit rate = made rows / existing rows. See `docs/decisions.md`.
- Sinclair uses the coefficient set valid for the competition's year. Never hardcode coefficients in code. They live in the table.
- Store `birth_year` only, never the full date of birth (GDPR, junior lifters).
- Every load is idempotent: upsert on `vlstat_id`, so re-running the seed never duplicates data.
- **Suspect entries** (`v_entry_result.suspect_reason`): vlstat's total doesn't match its attempts, or a lift is physically impossible. Their attempts stay visible, but best lifts, total and Sinclair are NULL, so they never count as records. Show them with the "tvivlsomme data" note.

## Scraper rules (vlstat.dk)

vlstat.dk is legacy ASP.NET WebForms (`.aspx`, `__VIEWSTATE` postbacks), probably on a small server. Our load must never harm it: the harvest should look like one person slowly browsing.

- **Scraping is a one-off.** The app never contacts vlstat.dk. All app data comes from our own database.
- **Minimal load:** one browser, one tab, one request at a time. Block images, fonts and stylesheets in Playwright (`page.route`) so each visit fetches only the HTML we need.
- **Stop on trouble.** On HTTP 429/5xx, timeouts or unexpected pages, stop the run. Don't retry in a loop. Resume later from what's on disk.
- **No evasion techniques:** no proxies, IP rotation, user-agent rotation, fingerprint masking or CAPTCHA solving. Respect `robots.txt`. If the site blocks us, stop and ask the user.
- **Phase 1 (`fetch_raw.py`) only saves HTML.** No parsing, no database writes.
  - `time.sleep(3.0)` between **every** click or navigation. Never lower it, parallelize it or make it async.
  - Only `Results.aspx` is harvested: one page per competition has everything. Lifter profile pages (`lifterpopup.aspx`) are **not** fetched; they lack birth year and gender (`docs/decisions.md`).
  - The script must be resumable: skip competitions already saved on disk.
  - `__VIEWSTATE` and `__EVENTVALIDATION` values are stripped before saving.
- **Phase 2 (`parse_and_seed.py`) reads only local files.** It never touches the network.
  - Ignore vlstat's Total and Points columns. We compute those ourselves.
  - Validate every record through Pydantic before insert. Log and skip invalid rows; don't crash the whole seed.
- Don't use the browser or MCP tools to explore vlstat.dk without asking first. Work from saved HTML.

## Token hygiene (important)

- **Never read a whole file in `data/raw_html/`.** The `__VIEWSTATE` blobs are huge. Use `grep`, `head`, or a small Python snippet to extract one `<table>` or 2–3 `<tr>` rows, and read only that.
- When working on `app/`, read only function signatures in `core/` and view definitions in `db/`. Don't read `scraper/`.
- Put small HTML fixtures for parser tests in `tests/fixtures/`, already stripped of `__VIEWSTATE`.

## Model routing

When you delegate to subagents:
- **Use the main model** (Opus/Sonnet) for schema design, complex SQL views (window functions for PRs, streaks, hit rates), Sinclair/total logic, and Playwright `__VIEWSTATE` navigation.
- **Use Haiku subagents** for boilerplate: Pydantic models from an agreed schema, CRUD, admin forms, Streamlit layout and CSS, Plotly charts from existing views, pytest tests and docs.

## Security

- Keep secrets out of code. Database URLs (`DATABASE_URL_ADMIN`, `DATABASE_URL_WRITE`, `DATABASE_URL_READ`) and `ADMIN_PASSWORD` go in `.env`, which is in `.gitignore`. Never read `.env` or print its values; use `db.check` to test connections. Keep `.env.example` current with dummy values.
- The public Streamlit app connects with the **read-only** role. The write role is used only by the seed script and by the admin page after login.
- Use parameterized SQL only. Never build queries with f-strings.

## Website: Pløk og Døk

The site's name is **Pløk og Døk**. Never brand it with "vlstat" or anything that could be mistaken for vlstat.dk; credit vlstat.dk as the data source in the footer.

**Look:** inspired by DPM.lol (stat-heavy profiles, big numbers, search up front) but rawer and rustic: gym chalk, iron and paper, not a glossy SaaS dashboard. It must not look AI-generated: no purple gradients, no glassmorphism, no rows of identical rounded cards with emoji icons, no generic hero sections, no "✨". Hand-chosen typography, visible structure (rules, grids), real data everywhere instead of filler copy.

**Version 1** (decided 2026-10-19; runs locally only, hosting decided later):
- **Front page:** latest competitions plus a prominent lifter search.
- **Lifter profile** `/loefter/{lifter_id}` (our own ID; manual lifters have no vlstat_id): PRs (snatch, C&J, total, Sinclair), progression chart, hit rate per attempt number and discipline, snatch/C&J ratio over time, full competition history with attempt colors, and fun stats: favourite weight jump, weigh-in precision (avg kg below the class ceiling), hidden potential (PR snatch + PR C&J minus best total), longest streak of made lifts, most stable lifter.
- **Competition page** `/staevne/{competition_id}`: results by weight class, competition hit rate, best Sinclair of the day, PRs set, club summary.
- **Club page** `/klub/{slug}` (slug from `core/clubs.py`): headline numbers, record board, top Sinclair per gender, age profile, loyal lifters, roster with filters (status, gender, age) and column sorting done in the browser. Clubs also show in the search.
- **Admin page:** password login (`ADMIN_PASSWORD`), add competitions via form or CSV. Uses the write role only after login.
- Not in v1: leaderboards.

Desktop and mobile get equal attention. UI text in Danish.

## UI conventions

- Colors: background `#FFF9F2` (Light Cream), panels/sidebar/tables `#F3E6D5` (Warm Beige), headings/primary buttons `#800020` (Deep Burgundy), accents/metrics/PR markers/chart highlights `#D45060` (Coral Rose). Define them once as CSS custom properties in `app/static/`, not inline.
- Attempts display as the plain number (e.g. `95`). Show made vs. missed **by color only**: dark green for made, `#D45060` for missed. No strikethrough, no minus signs, no X.
- **PRs:** a thick coral underline under the number that set the record (class `is-pr`: the total, or the made attempt that was the new best snatch/C&J). No stamps, badges, superscripts or icons; nothing that adds width to table cells. A lifter's first competition is marked "debut" in the sub-line instead, since everything there is trivially a PR.
- **Sinclair across genders:** never rank women and men together. Show the best woman and the best man separately (`v_competition_best_by_gender`).
- **Logo font:** Anton (uppercase). Headings: Big Shoulders Display. Body: Archivo.
- **Front page headline:** plain and functional ("Find en løfter"). No slogans or marketing copy anywhere.

## Definition of Done

A task is done only when:
1. `pytest` passes, with new tests for new logic.
2. `ruff check` and `ruff format` are clean.
3. Data is validated against the Pydantic models and schema.
4. The app/script runs without errors.
5. Architectural decisions and schema changes are written up in `docs/`.

## Language

Code, identifiers and comments in English. UI text in Danish.
