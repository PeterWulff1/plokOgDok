"""Write side for the admin page. Uses the write role (DATABASE_URL_WRITE) only.

Manually added competitions have vlstat_id NULL. Only those can be deleted here, so the
admin page can never damage data that came from vlstat.dk.
"""

import os
from dataclasses import dataclass
from datetime import date
from typing import Any

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from core.manual_entry import ManualRow

_pool: ConnectionPool | None = None


def _conn():
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            os.environ["DATABASE_URL_WRITE"], min_size=0, max_size=2,
            kwargs={"row_factory": dict_row, "autocommit": True},
        )  # fmt: skip
    return _pool.connection()


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


@dataclass(frozen=True)
class LifterMatch:
    """How one uploaded row maps to a lifter."""

    kind: str  # "existing" | "new" | "problem"
    lifter_id: int | None = None
    existing_name: str | None = None
    existing_club: str | None = None
    message: str | None = None


def _match_one(conn: Connection, row: ManualRow) -> LifterMatch:
    e = row.entry
    if e.lifter_vlstat_id is not None:
        found = conn.execute(
            "SELECT id, name FROM vl.lifter WHERE vlstat_id = %s", (e.lifter_vlstat_id,)
        ).fetchone()
        if found:
            return LifterMatch("existing", found["id"], found["name"])
        if e.gender is None:
            return LifterMatch("problem", message="ny løfter: angiv køn (M/K)")
        return LifterMatch("new")

    candidates = conn.execute(
        """
        SELECT l.id, l.name, l.gender, s.club
        FROM vl.lifter l LEFT JOIN vl.mv_lifter_summary s ON s.lifter_id = l.id
        WHERE lower(l.name) = lower(%s) AND (%s::char IS NULL OR l.gender = %s::char)
        """,
        (e.lifter_name, e.gender, e.gender),
    ).fetchall()
    if len(candidates) == 1:
        c = candidates[0]
        return LifterMatch("existing", c["id"], c["name"], c["club"])
    if len(candidates) > 1:
        clubs = ", ".join(c["club"] or "ukendt klub" for c in candidates)
        return LifterMatch(
            "problem",
            message=f"{len(candidates)} løftere hedder sådan ({clubs}): angiv vlstat_id",
        )
    if e.gender is None:
        return LifterMatch("problem", message="ny løfter: angiv køn (M/K)")
    return LifterMatch("new")


def match_lifters(rows: list[ManualRow]) -> list[LifterMatch]:
    with _conn() as conn:
        return [_match_one(conn, r) for r in rows]


def save_competition(
    name: str, comp_date: date, location: str | None, rows: list[ManualRow]
) -> int:
    """Insert a competition with all entries in one transaction. Returns its id.
    Raises ValueError if any row can't be matched to a lifter."""
    with _conn() as conn:
        matches = [_match_one(conn, r) for r in rows]
        problems = [f"Linje {r.line}: {m.message}" for r, m in zip(rows, matches, strict=True)
                    if m.kind == "problem"]  # fmt: skip
        if problems:
            raise ValueError("; ".join(problems))

        with conn.transaction():
            comp_id = conn.execute(
                """
                INSERT INTO vl.competition (name, date, location)
                VALUES (%s, %s, %s) RETURNING id
                """,
                (name, comp_date, location),
            ).fetchone()["id"]
            new_lifters: dict[Any, int] = {}
            for row, match in zip(rows, matches, strict=True):
                e = row.entry
                lifter_id = match.lifter_id
                if match.kind == "new":
                    key = e.lifter_vlstat_id or (e.lifter_name.lower(), e.gender)
                    if key not in new_lifters:
                        new_lifters[key] = conn.execute(
                            """
                            INSERT INTO vl.lifter (vlstat_id, name, gender, birth_year)
                            VALUES (%s, %s, %s, %s) RETURNING id
                            """,
                            (e.lifter_vlstat_id, e.lifter_name, e.gender, row.birth_year),
                        ).fetchone()["id"]
                    lifter_id = new_lifters[key]
                entry_id = conn.execute(
                    """
                    INSERT INTO vl.entry (lifter_id, competition_id, bodyweight, weight_class, club)
                    VALUES (%s, %s, %s, %s, %s) RETURNING id
                    """,
                    (lifter_id, comp_id, e.bodyweight, e.weight_class, e.club),
                ).fetchone()["id"]
                with conn.cursor() as cur:
                    cur.executemany(
                        """
                        INSERT INTO vl.attempt
                            (entry_id, discipline, attempt_number, weight_kg, is_successful)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        [(entry_id, a.discipline, a.attempt_number, a.weight_kg, a.is_successful)
                         for a in e.attempts],
                    )  # fmt: skip
        conn.execute("SELECT vl.refresh_derived()")
        return comp_id


def manual_competitions() -> list[dict]:
    with _conn() as conn:
        return conn.execute(
            """
            SELECT c.id, c.name, c.date, c.location, count(e.id) AS lifters
            FROM vl.competition c LEFT JOIN vl.entry e ON e.competition_id = c.id
            WHERE c.vlstat_id IS NULL
            GROUP BY c.id
            ORDER BY c.date DESC, c.id DESC
            """
        ).fetchall()


def delete_manual_competition(competition_id: int) -> bool:
    """Delete a manually added competition and lifters that only existed through it."""
    with _conn() as conn:
        with conn.transaction():
            deleted = conn.execute(
                "DELETE FROM vl.competition WHERE id = %s AND vlstat_id IS NULL RETURNING id",
                (competition_id,),
            ).fetchone()
            if not deleted:
                return False
            conn.execute(
                """
                DELETE FROM vl.lifter l
                WHERE l.vlstat_id IS NULL
                  AND NOT EXISTS (SELECT 1 FROM vl.entry e WHERE e.lifter_id = l.id)
                """
            )
        conn.execute("SELECT vl.refresh_derived()")
        return True
