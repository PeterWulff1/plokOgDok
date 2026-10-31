"""Sync the federation's event calendar (vaegtloeftning.dk/kalender) into vl.calendar_event.

Reads the site's own events API (The Events Calendar's REST endpoint), which holds the same
events the calendar page shows. Meant to run once a day (scripts/sync_calendar.cmd).

Load on vaegtloeftning.dk: one request per 50 events (usually a single request), 3 s apart.
Any HTTP error or unexpected response stops the run without touching the database; the next
day's run tries again. Upcoming events that vanish from the source are deleted (cancelled).

Usage:
    python -m scraper.fetch_calendar --dry-run    # fetch and print, no database needed
    python -m scraper.fetch_calendar              # upsert into DATABASE_URL_WRITE
"""

import argparse
import html
import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from urllib.parse import urlencode, urlparse

import psycopg
from dotenv import load_dotenv
from pydantic import ValidationError

from core.models import CalendarEvent

API_URL = "https://vaegtloeftning.dk/wp-json/tribe/events/v1/events"
ALLOWED_HOST = "vaegtloeftning.dk"
USER_AGENT = "PloekOgDoek-kalender/1.0 (daglig synkronisering, en forespoergsel ad gangen)"
DELAY_SECONDS = 3.0
TIMEOUT_SECONDS = 30
PER_PAGE = 50
MAX_PAGES = 10  # ~500 upcoming events; far more than the calendar ever holds.


class SyncError(RuntimeError):
    """Stop the run. The source isn't answering as expected."""


@dataclass
class SyncReport:
    added: list[CalendarEvent] = field(default_factory=list)
    changed: list[CalendarEvent] = field(default_factory=list)
    removed: list[tuple[datetime, str]] = field(default_factory=list)


# --- Fetching -----------------------------------------------------------------------


def _get_json(url: str) -> dict:
    if urlparse(url).hostname != ALLOWED_HOST:
        raise SyncError(f"Refusing to follow {url}: not {ALLOWED_HOST}")
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            content_type = response.headers.get("Content-Type", "")
            body = response.read()
    except urllib.error.HTTPError as exc:
        raise SyncError(f"HTTP {exc.code} for {url}. Stopping.") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise SyncError(f"No answer from {url}: {exc}. Stopping.") from exc
    if "json" not in content_type:
        raise SyncError(f"Expected JSON from {url}, got {content_type!r}. Stopping.")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise SyncError(f"Invalid JSON from {url}. Stopping.") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("events"), list):
        raise SyncError(f"Unexpected response shape from {url}. Stopping.")
    return payload


def fetch_raw_events(start: date) -> list[dict]:
    """All published events that haven't ended before `start`, following the API's pages."""
    url = f"{API_URL}?{urlencode({'per_page': PER_PAGE, 'start_date': start.isoformat()})}"
    events: list[dict] = []
    total = None
    for page in range(MAX_PAGES):
        if page:
            time.sleep(DELAY_SECONDS)
        payload = _get_json(url)
        events.extend(payload["events"])
        total = payload.get("total")
        url = payload.get("next_rest_url")
        if not url:
            break
    else:
        raise SyncError(f"More than {MAX_PAGES} pages of events. Stopping.")
    if total is not None and total != len(events):
        raise SyncError(f"API said {total} events but returned {len(events)}. Stopping.")
    if not events:
        raise SyncError("The calendar returned no upcoming events. Stopping.")
    return events


# --- Parsing (pure) -----------------------------------------------------------------


def _text(value) -> str | None:
    """Unescape HTML entities and collapse whitespace. Empty -> None."""
    if not isinstance(value, str):
        return None
    text = " ".join(html.unescape(value).split())
    return text or None


def parse_event(raw: dict) -> CalendarEvent:
    venue = raw.get("venue") or {}  # the API sends [] when an event has no venue
    return CalendarEvent(
        source_id=raw["id"],
        title=_text(raw["title"]) or "",
        starts_at=datetime.fromisoformat(raw["start_date"]),
        ends_at=datetime.fromisoformat(raw["end_date"]),
        all_day=bool(raw["all_day"]),
        venue=_text(venue.get("venue")),
        city=_text(venue.get("city")),
        country=_text(venue.get("country")),
        url=raw["url"],
        source_modified=datetime.fromisoformat(raw["modified_utc"]).replace(tzinfo=UTC),
    )


def is_listed(raw: dict) -> bool:
    """Published and not hidden from the calendar page."""
    return raw.get("status") == "publish" and not raw.get("hide_from_listings")


def parse_events(raw_events: list[dict]) -> tuple[list[CalendarEvent], list[str]]:
    """Valid, listed events, plus one message per event that couldn't be read."""
    events, errors = [], []
    for raw in raw_events:
        if not is_listed(raw):
            continue
        try:
            events.append(parse_event(raw))
        except (KeyError, TypeError, AttributeError, ValueError, ValidationError) as exc:
            errors.append(f"event {raw.get('id')!r}: {exc}".splitlines()[0])
    return events, errors


# --- Storing ------------------------------------------------------------------------


def store(
    conn: psycopg.Connection, events: list[CalendarEvent], seen_ids: set[int], start: date
) -> SyncReport:
    """Upsert events and delete upcoming ones the source no longer lists.

    `seen_ids` holds every ID the API returned, including events that failed to parse,
    so a parse problem never deletes an event.
    """
    report = SyncReport()
    with conn.transaction():
        for e in events:
            old_modified = conn.execute(
                """
                WITH old AS (
                    SELECT source_modified FROM vl.calendar_event WHERE source_id = %(source_id)s
                )
                INSERT INTO vl.calendar_event
                    (source_id, title, starts_at, ends_at, all_day, venue, city, country, url,
                     source_modified)
                VALUES (%(source_id)s, %(title)s, %(starts_at)s, %(ends_at)s, %(all_day)s,
                        %(venue)s, %(city)s, %(country)s, %(url)s, %(source_modified)s)
                ON CONFLICT (source_id) DO UPDATE
                SET title = EXCLUDED.title, starts_at = EXCLUDED.starts_at,
                    ends_at = EXCLUDED.ends_at, all_day = EXCLUDED.all_day,
                    venue = EXCLUDED.venue, city = EXCLUDED.city, country = EXCLUDED.country,
                    url = EXCLUDED.url, source_modified = EXCLUDED.source_modified,
                    last_seen_at = now()
                RETURNING (SELECT source_modified FROM old)
                """,
                e.model_dump(),
            ).fetchone()[0]
            if old_modified is None:
                report.added.append(e)
            elif old_modified != e.source_modified:
                report.changed.append(e)

        report.removed = conn.execute(
            """
            DELETE FROM vl.calendar_event
            WHERE starts_at >= %s AND NOT (source_id = ANY(%s))
            RETURNING starts_at, title
            """,
            (start, sorted(seen_ids)),
        ).fetchall()
    return report


def _print_report(report: SyncReport) -> None:
    for e in report.added:
        print(f"  + {e.starts_at:%Y-%m-%d} {e.title}")
    for e in report.changed:
        print(f"  ~ {e.starts_at:%Y-%m-%d} {e.title}")
    for starts_at, title in report.removed:
        print(f"  - {starts_at:%Y-%m-%d} {title}")
    print(f"{len(report.added)} new, {len(report.changed)} changed, {len(report.removed)} removed.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="fetch and print only")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    print(f"{datetime.now():%Y-%m-%d %H:%M} calendar sync")

    today = date.today()
    try:
        raw_events = fetch_raw_events(today)
    except SyncError as exc:
        sys.exit(f"  ! {exc}")
    events, errors = parse_events(raw_events)
    print(f"  {len(raw_events)} events from the API, {len(events)} valid, {len(errors)} problems")
    for err in errors:
        print("  !", err)

    if args.dry_run:
        for e in events:
            where = ", ".join(filter(None, [e.venue, e.city, e.country]))
            print(f"  {e.starts_at:%Y-%m-%d} {e.title} | {where}")
        return

    load_dotenv()
    url = os.environ.get("DATABASE_URL_WRITE")
    if not url:
        sys.exit("DATABASE_URL_WRITE is not set (see .env.example)")
    seen_ids = {r["id"] for r in raw_events if is_listed(r) and isinstance(r.get("id"), int)}
    with psycopg.connect(url, autocommit=True) as conn:
        _print_report(store(conn, events, seen_ids, today))


if __name__ == "__main__":
    main()
