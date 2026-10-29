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
