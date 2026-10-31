"""Integration test against a real, empty, throwaway Postgres database.

Skipped unless TEST_DATABASE_URL is set. Never point it at the Supabase project:
the test creates and drops the `vl` schema. Example with Docker:
    docker run -d --name vl-test -e POSTGRES_PASSWORD=test -p 54329:5432 postgres:17
    TEST_DATABASE_URL=postgresql://postgres:test@localhost:54329/postgres pytest
"""

import os
from pathlib import Path

import pytest

from scraper.parse_and_seed import load_dataset, seed

URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="TEST_DATABASE_URL not set")

FIXTURE = Path(__file__).parent / "fixtures" / "results_sample.html"


@pytest.fixture
def conn():
    import psycopg

    from db.migrate import apply_migrations

    with psycopg.connect(URL, autocommit=True) as c:
        c.execute("DROP SCHEMA IF EXISTS vl CASCADE")
        apply_migrations(c)
        yield c
        c.execute("DROP SCHEMA vl CASCADE")


@pytest.fixture
def raw_dir(tmp_path):
    year = tmp_path / "2019"
    year.mkdir()
    (year / "100.html").write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    (year / "index.json").write_text(
        '[{"id": "100", "label": "28dec2019 - Testcup 2019"}]', encoding="utf-8"
    )
    return tmp_path


def _counts(conn):
    return tuple(
        conn.execute(f"SELECT count(*) FROM vl.{t}").fetchone()[0]
        for t in ("lifter", "competition", "entry", "attempt")
    )


def test_migrations_are_idempotent(conn):
    from db.migrate import apply_migrations

    assert apply_migrations(conn) == []


def test_seed_is_idempotent(conn, raw_dir):
    data = load_dataset(raw_dir)
    seed(conn, data)
    first = _counts(conn)
    seed(conn, data)
    assert _counts(conn) == first == (4, 1, 4, 13)


def test_view_matches_vlstat(conn, raw_dir):
    seed(conn, load_dataset(raw_dir))
    total, sinclair = conn.execute(
        """
        SELECT r.total, round(r.sinclair, 2)
        FROM vl.v_entry_result r JOIN vl.lifter l ON l.id = r.lifter_id
        WHERE l.vlstat_id = 3966
        """
    ).fetchone()
    assert (total, float(sinclair)) == (195, 201.81)


def test_birth_year_derived(conn, raw_dir):
    seed(conn, load_dataset(raw_dir))
    birth_year = conn.execute("SELECT birth_year FROM vl.lifter WHERE vlstat_id = 3966").fetchone()[
        0
    ]
    assert birth_year == 1986


def test_weigh_in_margin_reads_class_ceilings(conn, raw_dir):
    seed(conn, load_dataset(raw_dir))
    lifter_id, competition_id = conn.execute(
        "SELECT lifter_id, competition_id FROM vl.entry LIMIT 1"
    ).fetchone()
    conn.execute("DELETE FROM vl.entry WHERE lifter_id = %s", (lifter_id,))
    rows = [  # (weight_class, bodyweight): only the first two have a usable ceiling
        ("45-49år -81kg", 80.6),
        ("71 - 89kg", 88.6),
        ("+109kg", 120.0),
        ("udenfor konkurrence", 70.0),
        ("-73kg", 75.0),  # above the ceiling: bad data, skipped
    ]
    for wc, bw in rows:
        conn.execute(
            "INSERT INTO vl.entry (lifter_id, competition_id, weight_class, bodyweight, club)"
            " VALUES (%s, %s, %s, %s, 'AK Test')",
            (lifter_id, competition_id, wc, bw),
        )
    margin, n = conn.execute(
        "SELECT weigh_in_margin, weigh_ins FROM vl.v_lifter_weigh_in WHERE lifter_id = %s",
        (lifter_id,),
    ).fetchone()
    assert (float(margin), n) == (0.4, 2)


def test_club_views_agree_with_entries(conn, raw_dir):
    seed(conn, load_dataset(raw_dir))
    club, starts = conn.execute(
        "SELECT club, count(*) FROM vl.entry WHERE club IS NOT NULL GROUP BY club"
        " ORDER BY count(*) DESC LIMIT 1"
    ).fetchone()
    assert (
        conn.execute("SELECT starts FROM vl.v_club WHERE club = %s", (club,)).fetchone()[0]
        == starts
    )
    # A record total is shown as snatch + C&J from the same entry.
    for value, sn, cj in conn.execute(
        "SELECT value, best_snatch, best_cj FROM vl.v_club_record WHERE kind = 'total'"
    ):
        assert value == sn + cj
    # Age groups split each year's lifters without overlap.
    for year_lifters, summed in conn.execute(
        "SELECT max(year_lifters), sum(lifters) FROM vl.v_club_age_profile GROUP BY club, year"
    ):
        assert year_lifters == summed
    # Placeholders get no club row.
    conn.execute("UPDATE vl.entry SET club = 'Andre' WHERE club = %s", (club,))
    assert conn.execute("SELECT count(*) FROM vl.v_club WHERE club = 'Andre'").fetchone()[0] == 0


def test_age_group_boundaries(conn):
    cases = {None: "ukendt", 13: "ungdom", 17: "ungdom", 18: "junior", 20: "junior",
             21: "senior", 34: "senior", 35: "master", 70: "master"}  # fmt: skip
    for age, group in cases.items():
        assert conn.execute("SELECT vl.age_group(%s)", (age,)).fetchone()[0] == group


def test_admin_lifter_search_and_match_by_id(conn, raw_dir, monkeypatch):
    from core.manual_entry import parse_rows
    from db import admin as store

    seed(conn, load_dataset(raw_dir))
    lifter_id, name = conn.execute("SELECT id, name FROM vl.lifter ORDER BY id LIMIT 1").fetchone()
    monkeypatch.setenv("DATABASE_URL_WRITE", URL)
    monkeypatch.setattr(store, "_pool", None)
    try:
        words = name.split()
        found = store.search_lifters(f"{words[-1][:3]} {words[0][:3]}".lower())
        assert lifter_id in [f["id"] for f in found]
        hit = next(f for f in found if f["id"] == lifter_id)
        assert hit["last_date"] is not None and {"club", "weight_class", "birth_year"} <= set(hit)
        assert store.search_lifters("%") == [] and store.search_lifters("_ _") == []

        rows = parse_rows([(2, {"navn": "Stavet Forkert", "lifter_id": str(lifter_id)}),
                           (3, {"navn": "Ingen", "lifter_id": "999999"})]).rows  # fmt: skip
        good, bad = store.match_lifters(rows)
        assert good.kind == "existing" and good.lifter_id == lifter_id
        assert bad.kind == "problem" and "999999" in bad.message
    finally:
        store.close_pool()


def test_calendar_sync_adds_changes_and_removes(conn):
    from datetime import UTC, date, datetime, timedelta

    from core.models import CalendarEvent
    from scraper.fetch_calendar import store

    start = date.today()
    modified = datetime(2026, 9, 1, tzinfo=UTC)

    def event(source_id, title, days, mod=modified):
        when = datetime.combine(start + timedelta(days=days), datetime.min.time())
        return CalendarEvent(
            source_id=source_id, title=title, starts_at=when, ends_at=when, all_day=True,
            url=f"https://vaegtloeftning.dk/e/{source_id}/", source_modified=mod,
        )  # fmt: skip

    first = [event(1, "DM Senior", 10), event(2, "Trænerkursus trin 1", 20), event(3, "Gone", 30)]
    report = store(conn, first, {1, 2, 3}, start)
    assert len(report.added) == 3 and not report.changed and not report.removed

    later = modified + timedelta(days=1)
    second = [event(1, "DM Senior", 10), event(2, "Trænerkursus trin 1", 21, later)]
    report = store(conn, second, {1, 2}, start)
    assert not report.added
    assert [e.source_id for e in report.changed] == [2]
    assert [title for _, title in report.removed] == ["Gone"]

    kinds = conn.execute(
        "SELECT source_id, kind, is_abroad, is_new FROM vl.v_calendar_event ORDER BY 1"
    ).fetchall()
    assert kinds == [(1, "staevne", False, False), (2, "kursus", False, False)]
