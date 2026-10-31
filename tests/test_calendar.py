import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from scraper import fetch_calendar
from scraper.fetch_calendar import SyncError, fetch_raw_events, is_listed, parse_events

FIXTURE = Path(__file__).parent / "fixtures" / "calendar_sample.json"


@pytest.fixture
def raw_events():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["events"]


def test_parse_events_cleans_text_and_skips_hidden_and_invalid(raw_events):
    events, errors = parse_events(raw_events)
    assert [e.source_id for e in events] == [15556, 15904]
    assert len(errors) == 1 and "16002" in errors[0]

    gotha, palma = events
    assert gotha.title == "AK Gotha’s Fødselsdagsstævne"
    assert gotha.starts_at == datetime(2026, 12, 12, 10, 0)
    assert (gotha.venue, gotha.city, gotha.country) == ("AK Gotha", "København SV", "Denmark")
    assert gotha.source_modified == datetime(2026, 9, 25, 7, 49, 59, tzinfo=UTC)
    # The API sends an empty list, not an object, when there's no venue.
    assert palma.all_day and (palma.venue, palma.city, palma.country) == (None, None, None)


def test_is_listed(raw_events):
    assert [is_listed(r) for r in raw_events] == [True, True, False, True]
    assert not is_listed({"status": "draft"})


def test_parse_rejects_foreign_urls(raw_events):
    raw = dict(raw_events[0], url="https://example.com/event/")
    events, errors = parse_events([raw])
    assert events == [] and len(errors) == 1


def _fake_api(monkeypatch, pages: list[dict]):
    calls = []
    answers = iter(pages)

    def fake_get(url):
        calls.append(url)
        return next(answers)

    monkeypatch.setattr(fetch_calendar, "_get_json", fake_get)
    monkeypatch.setattr(fetch_calendar.time, "sleep", lambda s: calls.append(f"sleep {s}"))
    return calls


def test_fetch_follows_pages_with_a_pause(monkeypatch):
    calls = _fake_api(
        monkeypatch,
        [
            {"events": [{"id": 1}], "total": 2, "next_rest_url": "https://vaegtloeftning.dk/p2"},
            {"events": [{"id": 2}], "total": 2},
        ],
    )
    events = fetch_raw_events(datetime(2026, 10, 31).date())
    assert [e["id"] for e in events] == [1, 2]
    assert calls[1] == "sleep 3.0" and calls[2] == "https://vaegtloeftning.dk/p2"


@pytest.mark.parametrize(
    "pages",
    [
        [{"events": [], "total": 0}],  # an empty calendar is unexpected; don't delete
        [{"events": [{"id": 1}], "total": 5}],  # missing events
    ],
)
def test_fetch_stops_on_unexpected_answers(monkeypatch, pages):
    _fake_api(monkeypatch, pages)
    with pytest.raises(SyncError):
        fetch_raw_events(datetime(2026, 10, 31).date())


def test_get_json_refuses_other_hosts():
    with pytest.raises(SyncError, match="Refusing"):
        fetch_calendar._get_json("https://example.com/wp-json/")
