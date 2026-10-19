"""Check each database connection in .env and that its permissions are what we expect.

Usage: python -m db.check
Never prints passwords. Exits non-zero if something is wrong.
"""

import os
import sys

import psycopg
from dotenv import load_dotenv

TABLES = ["lifter", "competition", "entry", "attempt", "sinclair_coefficient"]


def _can_write(conn: psycopg.Connection) -> bool:
    """Try an insert inside a transaction that's always rolled back."""
    try:
        with conn.transaction(force_rollback=True):
            conn.execute(
                "INSERT INTO vl.competition (name, date) VALUES ('__check__', '2000-01-01')"
            )
        return True
    except psycopg.errors.InsufficientPrivilege:
        return False


def check(label: str, env_var: str, expect_write: bool) -> bool:
    url = os.environ.get(env_var)
    if not url or "CHANGE_ME" in url:
        print(f"[skip] {label}: {env_var} not filled in")
        return True
    try:
        with psycopg.connect(url, autocommit=True, connect_timeout=15) as conn:
            user = conn.execute("SELECT current_user").fetchone()[0]
            found = {
                r[0]
                for r in conn.execute(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema = 'vl'"
                )
            }
            missing = [t for t in TABLES if t not in found]
            if missing:
                print(f"[FAIL] {label} ({user}): can't see tables {missing}")
                return False
            coeffs = conn.execute("SELECT count(*) FROM vl.sinclair_coefficient").fetchone()[0]
            writes = _can_write(conn)
    except psycopg.Error as exc:
        print(f"[FAIL] {label}: {type(exc).__name__}: {str(exc).splitlines()[0]}")
        return False

    ok = writes == expect_write
    mode = "read+write" if writes else "read-only"
    print(f"[{'ok' if ok else 'FAIL'}] {label} ({user}): {mode}, {coeffs} Sinclair rows")
    return ok


def main() -> None:
    load_dotenv()
    results = [
        check("admin", "DATABASE_URL_ADMIN", expect_write=True),
        check("writer", "DATABASE_URL_WRITE", expect_write=True),
        check("reader", "DATABASE_URL_READ", expect_write=False),
    ]
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
