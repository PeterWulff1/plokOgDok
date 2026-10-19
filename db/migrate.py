"""Apply SQL migrations in db/migrations/ in filename order, each exactly once.

Needs owner rights (creates schemas, roles and grants), so it uses DATABASE_URL_ADMIN:
on Supabase, the `postgres` user's connection string.

Usage: python -m db.migrate            (reads .env)
"""

import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def apply_migrations(conn: psycopg.Connection) -> list[str]:
    """Apply pending migrations. Returns the filenames applied."""
    # Bookkeeping lives in `vl` too: Supabase's REST API exposes `public` to anonymous users.
    conn.execute("CREATE SCHEMA IF NOT EXISTS vl")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS vl.schema_migrations (
            filename   text PRIMARY KEY,
            applied_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    done = {row[0] for row in conn.execute("SELECT filename FROM vl.schema_migrations")}
    applied = []
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        if path.name in done:
            continue
        with conn.transaction():
            conn.execute(path.read_text(encoding="utf-8"))
            conn.execute("INSERT INTO vl.schema_migrations (filename) VALUES (%s)", (path.name,))
        applied.append(path.name)
    return applied


def main() -> None:
    load_dotenv()
    url = os.environ.get("DATABASE_URL_ADMIN")
    if not url:
        sys.exit("DATABASE_URL_ADMIN is not set (see .env.example)")
    with psycopg.connect(url, autocommit=True) as conn:
        applied = apply_migrations(conn)
    print("Applied:", ", ".join(applied) if applied else "nothing, already up to date")


if __name__ == "__main__":
    main()
