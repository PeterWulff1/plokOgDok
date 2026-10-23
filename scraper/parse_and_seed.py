"""Phase 2: parse saved pages in data/raw_html/ and load them into the database.

Reads local files only, never the network. Idempotent: re-running updates rows in place
(keyed on vlstat IDs) and never creates duplicates.

Usage:
    python -m scraper.parse_and_seed --dry-run    # parse and report, no database needed
    python -m scraper.parse_and_seed              # load into DATABASE_URL_WRITE
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import psycopg
from dotenv import load_dotenv

from core.lifters import derive_birth_year, resolve_gender
from core.models import Competition, Entry, Gender, Lifter
from scraper.fetch_raw import RAW_DIR
from scraper.parse_results import PageFormatError, parse_competition_label, parse_results_page


@dataclass
class Dataset:
    competitions: list[tuple[Competition, list[Entry]]] = field(default_factory=list)
    lifters: list[Lifter] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def load_dataset(raw_dir: Path = RAW_DIR) -> Dataset:
    data = Dataset()
    names: dict[int, tuple] = {}  # vlstat_id -> (date, name), latest wins
    genders: dict[int, list[Gender | None]] = defaultdict(list)
    ages: dict[int, list[tuple[int, int]]] = defaultdict(list)

    for index_path in sorted(raw_dir.glob("*/index.json")):
        labels = {e["id"]: e["label"] for e in json.loads(index_path.read_text(encoding="utf-8"))}
        for page in sorted(index_path.parent.glob("*.html")):
            where = f"{index_path.parent.name}/{page.name}"
            label = labels.get(page.stem)
            if label is None:
                data.errors.append(f"{where}: not in index.json")
                continue
            try:
                comp_date, comp_name = parse_competition_label(label)
                result = parse_results_page(page.read_text(encoding="utf-8"))
            except PageFormatError as exc:
                data.errors.append(f"{where}: {exc}")
                continue
            data.errors.extend(f"{where}: {e}" for e in result.errors)

            comp = Competition(vlstat_id=int(page.stem), name=comp_name, date=comp_date)
            entries = [row.entry for row in result.rows]
            data.competitions.append((comp, entries))

            for e in entries:
                lid = e.lifter_vlstat_id
                if lid not in names or names[lid][0] <= comp_date:
                    names[lid] = (comp_date, e.lifter_name)
                genders[lid].append(e.gender)
                if e.reported_age is not None:
                    ages[lid].append((comp_date.year, e.reported_age))

    for lid, (_, name) in sorted(names.items()):
        gender = resolve_gender(genders[lid])
        if gender is None and any(genders[lid]):
            data.errors.append(f"lifter {lid} ({name}): conflicting genders {set(genders[lid])}")
        birth_year = derive_birth_year(ages[lid])
        if birth_year is None and ages[lid]:
            data.errors.append(f"lifter {lid} ({name}): inconsistent ages {sorted(ages[lid])}")
        data.lifters.append(Lifter(vlstat_id=lid, name=name, gender=gender, birth_year=birth_year))
    return data


def seed(conn: psycopg.Connection, data: Dataset) -> None:
    lifter_ids: dict[int, int] = {}
    with conn.transaction():
        for lifter in data.lifters:
            row = conn.execute(
                """
                INSERT INTO vl.lifter (vlstat_id, name, gender, birth_year)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (vlstat_id) DO UPDATE
                SET name = EXCLUDED.name, gender = EXCLUDED.gender,
                    birth_year = EXCLUDED.birth_year
                RETURNING id
                """,
                (lifter.vlstat_id, lifter.name, lifter.gender, lifter.birth_year),
            ).fetchone()
            lifter_ids[lifter.vlstat_id] = row[0]

    for comp, entries in data.competitions:
        with conn.transaction():
            comp_id = conn.execute(
                """
                INSERT INTO vl.competition (vlstat_id, name, date, location)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (vlstat_id) DO UPDATE
                SET name = EXCLUDED.name, date = EXCLUDED.date
                RETURNING id
                """,
                (comp.vlstat_id, comp.name, comp.date, comp.location),
            ).fetchone()[0]
            for e in entries:
                entry_id = conn.execute(
                    """
                    INSERT INTO vl.entry
                        (lifter_id, competition_id, bodyweight, weight_class, club, reported_age,
                         reported_total)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (competition_id, lifter_id, weight_class) DO UPDATE
                    SET bodyweight = EXCLUDED.bodyweight, club = EXCLUDED.club,
                        reported_age = EXCLUDED.reported_age,
                        reported_total = EXCLUDED.reported_total
                    RETURNING id
                    """,
                    (
                        lifter_ids[e.lifter_vlstat_id],
                        comp_id,
                        e.bodyweight,
                        e.weight_class,
                        e.club,
                        e.reported_age,
                        e.reported_total,
                    ),
                ).fetchone()[0]
                # Replace attempts so corrections in the source are picked up.
                conn.execute("DELETE FROM vl.attempt WHERE entry_id = %s", (entry_id,))
                with conn.cursor() as cur:
                    cur.executemany(
                        """
                        INSERT INTO vl.attempt
                            (entry_id, discipline, attempt_number, weight_kg, is_successful)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        [
                            (entry_id, a.discipline, a.attempt_number, a.weight_kg,
                             a.is_successful)
                            for a in e.attempts
                        ],
                    )  # fmt: skip

    # Rebuild the cached summaries the website reads (migration 008).
    conn.execute("SELECT vl.refresh_derived()")


def _report(data: Dataset) -> None:
    n_entries = sum(len(es) for _, es in data.competitions)
    n_attempts = sum(len(e.attempts) for _, es in data.competitions for e in es)
    print(
        f"{len(data.competitions)} competitions, {len(data.lifters)} lifters, "
        f"{n_entries} entries, {n_attempts} attempts, {len(data.errors)} problems"
    )
    for err in data.errors[:50]:
        print("  !", err)
    if len(data.errors) > 50:
        print(f"  ... and {len(data.errors) - 50} more")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="parse and report only")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    data = load_dataset()
    _report(data)
    if args.dry_run:
        return

    load_dotenv()
    url = os.environ.get("DATABASE_URL_WRITE")
    if not url:
        sys.exit("DATABASE_URL_WRITE is not set (see .env.example)")
    with psycopg.connect(url, autocommit=True) as conn:
        seed(conn, data)
    print("Seed complete.")


if __name__ == "__main__":
    main()
