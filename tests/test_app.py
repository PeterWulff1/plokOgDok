from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app import formatting
from app import main as app_main


@pytest.mark.parametrize(
    ("value", "decimals", "expected"),
    [(1234.5, 1, "1.234,5"), (Decimal("219.49"), 1, "219,5"), (163, 0, "163"), (None, 0, "–")],
)
def test_num(value, decimals, expected):
    assert formatting.num(value, decimals) == expected


def test_pct_and_signed_pct():
    assert formatting.pct(Decimal("0.5552")) == "56 %"
    assert formatting.pct(None) == "–"
    assert formatting.signed_pct(Decimal("-0.5058")) == "−51 point"
    assert formatting.signed_pct(Decimal("0.12")) == "+12 point"
    assert formatting.css_pct(Decimal("0.5")) == "50.00%"


def test_dk_date():
    assert formatting.dk_date(date(2026, 10, 12)) == "12. okt. 2026"
    assert formatting.dk_date(date(2026, 5, 3), with_year=False) == "3. maj"


def test_progression_series_is_oldest_first_and_skips_debut_prs():
    history = [
        {"date": date(2026, 2, 1), "competition": "B", "best_snatch": 75, "best_cj": 90,
         "is_pr_snatch": True, "is_pr_cj": False, "is_debut": False},
        {"date": date(2025, 1, 1), "competition": "A", "best_snatch": 70, "best_cj": 88,
         "is_pr_snatch": True, "is_pr_cj": True, "is_debut": True},
    ]  # fmt: skip
    s = formatting.progression_series(history)
    assert s["competitions"] == ["A", "B"]
    assert s["pr_snatch"] == [False, True]
    assert s["pr_cj"] == [False, False]


@pytest.fixture
def client(monkeypatch):
    """App with the database replaced by canned rows."""
    q = app_main.queries
    monkeypatch.setattr(q, "open_pool", lambda url=None: None)
    monkeypatch.setattr(q, "close_pool", lambda: None)
    monkeypatch.setattr(q, "latest_competitions", lambda limit=12: [])
    monkeypatch.setattr(
        q, "site_totals",
        lambda: {"lifters": 2, "competitions": 1, "attempts": 12, "since": date(2019, 1, 5)},
    )  # fmt: skip
    monkeypatch.setattr(
        q, "search_lifters",
        lambda query, limit=8: [{"lifter_id": 7, "name": "Test Løfter", "club": "AK Test",
                                 "pr_total": 200, "last_date": date(2026, 1, 1)}],
    )  # fmt: skip
    monkeypatch.setattr(q, "lifter_summary", lambda lifter_id: None)
    monkeypatch.setattr(q, "competition_summary", lambda competition_id: None)
    with TestClient(app_main.app) as c:
        yield c


def test_front_page(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Pløk" in r.text and "vlstat.dk" in r.text


def test_search_partial(client):
    r = client.get("/sog", params={"q": "test"})
    assert r.status_code == 200
    assert 'href="/loefter/7"' in r.text


def test_unknown_lifter_and_competition_are_404(client):
    assert client.get("/loefter/1").status_code == 404
    assert client.get("/staevne/1").status_code == 404
