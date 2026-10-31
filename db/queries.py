"""Read-only queries for the website. Every number comes from a view (migrations 006-008).

Functions return plain dicts and lists, shaped for templates. They only reshape rows
(grouping, nesting); they never compute statistics. The public site connects with the
read-only role (DATABASE_URL_READ).
"""

import os
from collections import defaultdict
from typing import Any

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

Row = dict[str, Any]

_pool: ConnectionPool | None = None


def open_pool(url: str | None = None) -> ConnectionPool:
    global _pool
    if _pool is None:
        url = url or os.environ["DATABASE_URL_READ"]
        _pool = ConnectionPool(
            url, min_size=1, max_size=4, kwargs={"row_factory": dict_row},
            # Supabase's pooler drops idle connections; test each one before use and
            # recycle idle ones, so a site left running for days doesn't return 500s.
            check=ConnectionPool.check_connection, max_idle=300,
        )  # fmt: skip
    return _pool


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def _all(sql: str, params: tuple = ()) -> list[Row]:
    with open_pool().connection() as conn:
        return conn.execute(sql, params).fetchall()


def _one(sql: str, params: tuple = ()) -> Row | None:
    rows = _all(sql, params)
    return rows[0] if rows else None


# --- Front page -------------------------------------------------------------------


def latest_competitions(limit: int = 12) -> list[Row]:
    return _all(
        """
        SELECT c.*, f.name AS best_f_name, m.name AS best_m_name
        FROM vl.mv_competition_summary c
        LEFT JOIN vl.lifter f ON f.id = c.best_f_lifter_id
        LEFT JOIN vl.lifter m ON m.id = c.best_m_lifter_id
        WHERE c.lifters > 0
        ORDER BY c.date DESC, c.competition_id DESC
        LIMIT %s
        """,
        (limit,),
    )


def search_lifters(query: str, limit: int = 8) -> list[Row]:
    query = query.strip()
    if len(query) < 2:
        return []
    return _all(
        """
        SELECT lifter_id, name, club, gender, pr_total, pr_sinclair, last_date
        FROM vl.mv_lifter_summary
        WHERE name ILIKE %s
        ORDER BY (name ILIKE %s) DESC, last_date DESC
        LIMIT %s
        """,
        (f"%{query}%", f"{query}%", limit),
    )


def search_index() -> list[Row]:
    """Every lifter for the static site's in-browser search, most recently active first."""
    return _all(
        """
        SELECT lifter_id, name, club, pr_total, last_date
        FROM vl.mv_lifter_summary
        ORDER BY last_date DESC, lifter_id
        """
    )


def site_totals() -> Row:
    return _one(
        """
        SELECT
            (SELECT count(*) FROM vl.mv_lifter_summary)                       AS lifters,
            (SELECT count(*) FROM vl.mv_competition_summary WHERE lifters > 0) AS competitions,
            (SELECT sum(attempts) FROM vl.mv_competition_summary)             AS attempts,
            (SELECT min(date) FROM vl.mv_competition_summary)                 AS since
        """
    )


# --- Lifter profile ---------------------------------------------------------------


def lifter_summary(lifter_id: int) -> Row | None:
    return _one(
        """
        SELECT s.*, p.super_total, p.hidden_potential, p.weigh_in_margin, p.weigh_ins
        FROM vl.mv_lifter_summary s
        LEFT JOIN vl.v_lifter_potential p ON p.lifter_id = s.lifter_id
        WHERE s.lifter_id = %s
        """,
        (lifter_id,),
    )


def _attempt_slots(entry_ids: list[int]) -> dict[int, dict[str, list[Row | None]]]:
    """entry_id -> {"snatch": [a1, a2, a3], "cj": [...]}, None where no attempt exists."""
    slots: dict[int, dict[str, list[Row | None]]] = defaultdict(
        lambda: {"snatch": [None, None, None], "cj": [None, None, None]}
    )
    if not entry_ids:
        return slots
    for a in _all(
        """
        SELECT entry_id, discipline, attempt_number, weight_kg, is_successful
        FROM vl.attempt WHERE entry_id = ANY(%s)
        """,
        (entry_ids,),
    ):
        slots[a["entry_id"]][a["discipline"]][a["attempt_number"] - 1] = a
    return slots


def lifter_history(lifter_id: int) -> list[Row]:
    """All competitions for a lifter, newest first, with attempts and PR flags."""
    rows = _all(
        """
        SELECT r.*, c.name AS competition,
               p.is_pr_snatch, p.is_pr_cj, p.is_pr_total, p.is_debut
        FROM vl.v_entry_result r
        JOIN vl.competition c ON c.id = r.competition_id
        JOIN vl.mv_entry_pr p ON p.entry_id = r.entry_id
        WHERE r.lifter_id = %s
        ORDER BY r.date DESC, r.entry_id DESC
        """,
        (lifter_id,),
    )
    slots = _attempt_slots([r["entry_id"] for r in rows])
    for r in rows:
        r["attempts"] = slots[r["entry_id"]]
    return rows


def lifter_hit_rates(lifter_id: int) -> dict[str, list[Row | None]]:
    """{"snatch": [1st, 2nd, 3rd], "cj": [...]} with attempts/made/hit_rate."""
    out: dict[str, list[Row | None]] = {"snatch": [None] * 3, "cj": [None] * 3}
    for r in _all("SELECT * FROM vl.v_lifter_hit_rate WHERE lifter_id = %s", (lifter_id,)):
        out[r["discipline"]][r["attempt_number"] - 1] = r
    return out


def lifter_favourite_jumps(lifter_id: int, per_discipline: int = 3) -> dict[str, list[Row]]:
    out: dict[str, list[Row]] = {"snatch": [], "cj": []}
    for r in _all(
        """
        SELECT * FROM vl.v_lifter_jump
        WHERE lifter_id = %s AND jump_kg > 0
        ORDER BY discipline, times DESC, jump_kg
        """,
        (lifter_id,),
    ):
        if len(out[r["discipline"]]) < per_discipline:
            out[r["discipline"]].append(r)
    return out


# --- Competition page -------------------------------------------------------------


def competition_summary(competition_id: int) -> Row | None:
    return _one(
        """
        SELECT c.*, l.name AS best_sinclair_lifter
        FROM vl.mv_competition_summary c
        LEFT JOIN vl.lifter l ON l.id = c.best_sinclair_lifter_id
        WHERE c.competition_id = %s
        """,
        (competition_id,),
    )


def competition_results(competition_id: int) -> list[Row]:
    """Entries grouped by (gender, weight class): [{"gender", "weight_class", "entries"}]."""
    rows = _all(
        """
        SELECT r.*, l.name,
               p.is_pr_snatch, p.is_pr_cj, p.is_pr_total, p.is_debut
        FROM vl.v_entry_result r
        JOIN vl.lifter l     ON l.id = r.lifter_id
        JOIN vl.mv_entry_pr p ON p.entry_id = r.entry_id
        WHERE r.competition_id = %s
        ORDER BY r.gender, r.weight_class NULLS FIRST, r.total DESC NULLS LAST, r.sinclair DESC
        """,
        (competition_id,),
    )
    slots = _attempt_slots([r["entry_id"] for r in rows])
    groups: list[Row] = []
    for r in rows:
        r["attempts"] = slots[r["entry_id"]]
        key = (r["gender"], r["weight_class"])
        if not groups or (groups[-1]["gender"], groups[-1]["weight_class"]) != key:
            groups.append({"gender": key[0], "weight_class": key[1], "entries": []})
        groups[-1]["entries"].append(r)
    return groups


def competition_clubs(competition_id: int) -> list[Row]:
    return _all(
        """
        SELECT * FROM vl.v_competition_club
        WHERE competition_id = %s
        ORDER BY sum_sinclair DESC NULLS LAST
        """,
        (competition_id,),
    )


def competition_top_sinclair(competition_id: int, per_gender: int = 3) -> dict[str, list[Row]]:
    """Best Sinclair per gender: {"F": [...], "M": [...]}. Sinclair isn't comparable
    across genders (docs/decisions.md), so women and men are listed separately."""
    out: dict[str, list[Row]] = {"F": [], "M": []}
    for r in _all(
        """
        SELECT * FROM (
            SELECT r.gender, r.sinclair, r.total, r.bodyweight, r.club, l.name, r.lifter_id,
                   row_number() OVER (PARTITION BY r.gender ORDER BY r.sinclair DESC) AS n
            FROM vl.v_entry_result r JOIN vl.lifter l ON l.id = r.lifter_id
            WHERE r.competition_id = %s AND r.sinclair IS NOT NULL AND r.gender IS NOT NULL
        ) t WHERE n <= %s
        ORDER BY gender, n
        """,
        (competition_id, per_gender),
    ):
        out[r["gender"]].append(r)
    return out


# --- Club page --------------------------------------------------------------------


def all_clubs() -> list[Row]:
    """Every club (~75 rows), busiest first. Search and slug lookup filter these in
    core.clubs, since matching ignores Danish spelling (aa/å), which SQL ILIKE can't."""
    return _all("SELECT * FROM vl.v_club ORDER BY starts DESC, club")


def club_summary(club: str) -> Row | None:
    return _one(
        """
        SELECT c.*, h.attempts, h.made, h.hit_rate, h.national_hit_rate
        FROM vl.v_club c
        LEFT JOIN vl.v_club_hit_rate h ON h.club = c.club
        WHERE c.club = %s
        """,
        (club,),
    )


def club_records(club: str) -> dict[str, dict[str, Row]]:
    """{"F": {"snatch": row, "cj": ..., "total": ..., "sinclair": ...}, "M": {...}}."""
    out: dict[str, dict[str, Row]] = {"F": {}, "M": {}}
    for r in _all(
        """
        SELECT r.*, l.name, c.name AS competition
        FROM vl.v_club_record r
        JOIN vl.lifter l      ON l.id = r.lifter_id
        JOIN vl.competition c ON c.id = r.competition_id
        WHERE r.club = %s AND r.gender IS NOT NULL
        """,
        (club,),
    ):
        out[r["gender"]][r["kind"]] = r
    return out


def club_top_sinclair(club: str, per_gender: int = 5) -> dict[str, list[Row]]:
    """Each lifter's best Sinclair for the club, top N per gender (never ranked together)."""
    out: dict[str, list[Row]] = {"F": [], "M": []}
    for r in _all(
        """
        SELECT t.*, l.name, c.name AS competition
        FROM vl.v_club_top_sinclair t
        JOIN vl.lifter l      ON l.id = t.lifter_id
        JOIN vl.competition c ON c.id = t.competition_id
        WHERE t.club = %s AND t.rank <= %s AND t.gender IS NOT NULL
        ORDER BY t.gender, t.rank
        """,
        (club, per_gender),
    ):
        out[r["gender"]].append(r)
    return out


def club_lifters(club: str) -> list[Row]:
    """Everyone who lifted for the club: active first, then by best Sinclair."""
    return _all(
        """
        SELECT cl.*, l.name, l.gender, l.birth_year
        FROM vl.v_club_lifter cl
        JOIN vl.lifter l ON l.id = cl.lifter_id
        WHERE cl.club = %s
        ORDER BY cl.is_active DESC, cl.best_sinclair DESC NULLS LAST, l.name
        """,
        (club,),
    )


def club_loyal(club: str, limit: int = 4) -> dict[str, list[Row]]:
    """{"starts": most competitions for the club, "years": longest span in the club}."""
    return {
        "starts": _all(
            """
            SELECT cl.*, l.name
            FROM vl.v_club_lifter cl JOIN vl.lifter l ON l.id = cl.lifter_id
            WHERE cl.club = %s
            ORDER BY cl.starts DESC, cl.last_date DESC
            LIMIT %s
            """,
            (club, limit),
        ),
        "years": _all(
            """
            SELECT cl.*, l.name
            FROM vl.v_club_lifter cl JOIN vl.lifter l ON l.id = cl.lifter_id
            WHERE cl.club = %s
            ORDER BY cl.years DESC, cl.starts DESC
            LIMIT 1
            """,
            (club,),
        ),
    }


def club_age_profile(club: str) -> list[Row]:
    """[{"year", "year_lifters", "groups": [rows by group_order]}], oldest year first."""
    years: list[Row] = []
    for r in _all(
        """
        SELECT * FROM vl.v_club_age_profile
        WHERE club = %s
        ORDER BY year, group_order
        """,
        (club,),
    ):
        if not years or years[-1]["year"] != r["year"]:
            years.append({"year": r["year"], "year_lifters": r["year_lifters"], "groups": []})
        years[-1]["groups"].append(r)
    return years


# --- Calendar (vaegtloeftning.dk/kalender, migration 016) ----------------------------


def upcoming_events(limit: int | None = None, meets_only: bool = False) -> list[Row]:
    return _all(
        """
        SELECT * FROM vl.v_calendar_event
        WHERE end_date >= current_date AND (NOT %s OR kind = 'staevne')
        ORDER BY start_date, title
        LIMIT %s
        """,
        (meets_only, limit),
    )


def calendar_months() -> list[Row]:
    """Upcoming events grouped by the month they start in, soonest first."""
    months: dict = defaultdict(list)
    for event in upcoming_events():
        months[event["start_date"].replace(day=1)].append(event)
    return [{"month": month, "events": events} for month, events in months.items()]


def calendar_synced_at():
    """When the daily sync last saw the calendar, or None before the first sync."""
    return _one("SELECT max(last_seen_at) AS synced_at FROM vl.v_calendar_event")["synced_at"]
