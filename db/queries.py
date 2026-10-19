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
        _pool = ConnectionPool(url, min_size=1, max_size=4, kwargs={"row_factory": dict_row})
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
        SELECT c.*, l.name AS best_sinclair_lifter
        FROM vl.mv_competition_summary c
        LEFT JOIN vl.lifter l ON l.id = c.best_sinclair_lifter_id
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
    return _one("SELECT * FROM vl.mv_lifter_summary WHERE lifter_id = %s", (lifter_id,))


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
        JOIN vl.v_entry_pr p  ON p.entry_id = r.entry_id
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
        JOIN vl.v_entry_pr p ON p.entry_id = r.entry_id
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


def competition_top_sinclair(competition_id: int, limit: int = 5) -> list[Row]:
    return _all(
        """
        SELECT r.sinclair, r.total, r.bodyweight, r.club, l.name, r.lifter_id
        FROM vl.v_entry_result r JOIN vl.lifter l ON l.id = r.lifter_id
        WHERE r.competition_id = %s AND r.sinclair IS NOT NULL
        ORDER BY r.sinclair DESC
        LIMIT %s
        """,
        (competition_id, limit),
    )
