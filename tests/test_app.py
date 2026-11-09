import re
from datetime import UTC, date, datetime
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


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        (date(2026, 11, 7), date(2026, 11, 7), "7. nov. 2026"),
        (date(2026, 11, 13), date(2026, 11, 14), "13.–14. nov. 2026"),
        (date(2027, 1, 30), date(2027, 2, 1), "30. jan.–1. feb. 2027"),
        (date(2026, 12, 30), date(2027, 1, 2), "30. dec. 2026–2. jan. 2027"),
    ],
)
def test_dk_date_range(start, end, expected):
    assert formatting.dk_date_range(start, end) == expected


def test_dk_month_and_event_kind():
    assert formatting.dk_month(date(2026, 11, 1)) == "november 2026"
    assert formatting.event_kind("kursus") == "Kursus"


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


CLUB = {
    "club": "Århus Atlet Klub",
    "starts": 790,
    "lifters": 99,
    "active_lifters": 42,
    "women": 40,
    "men": 59,
    "competitions": 120,
    "first_date": date(2019, 1, 5),
    "last_date": date(2026, 10, 12),
    "attempts": 4000,
    "made": 2900,
    "hit_rate": Decimal("0.725"),
    "national_hit_rate": Decimal("0.7168"),
}
_REC = {
    "lifter_id": 7,
    "name": "Test Løfter",
    "date": date(2024, 10, 5),
    "weight_class": "-81kg",
    "competition_id": 3,
    "competition": "Aalborg cup 2024",
    "best_snatch": 130,
    "best_cj": 158,
}
CLUB_RECORDS = {
    "F": {},
    "M": {
        "snatch": {**_REC, "value": Decimal(131)},
        "cj": {**_REC, "value": Decimal(158)},
        "total": {**_REC, "value": Decimal(288)},
        "sinclair": {**_REC, "value": Decimal("373.03")},
    },
}
TOP = {
    "rank": 1,
    "lifter_id": 7,
    "name": "Test Løfter",
    "competition": "Aalborg cup 2024",
    "total": 288,
    "bodyweight": Decimal("78.10"),
    "sinclair": Decimal("373.03"),
}
CLUB_LIFTERS = [
    {
        "lifter_id": 7,
        "name": "Test Løfter",
        "gender": "M",
        "birth_year": 2000,
        "weight_class": "-81kg",
        "starts": 12,
        "first_date": date(2019, 6, 1),
        "last_date": date(2026, 6, 1),
        "years": Decimal("7.0"),
        "is_active": True,
        "age_group": "senior",
        "best_snatch": 131,
        "best_cj": 158,
        "best_total": 288,
        "best_sinclair": Decimal("373.03"),
    },
    {
        "lifter_id": 8,
        "name": "Gammel Løfter",
        "gender": "F",
        "birth_year": None,
        "weight_class": None,
        "starts": 1,
        "first_date": date(2019, 2, 1),
        "last_date": date(2019, 2, 1),
        "years": Decimal("0.0"),
        "is_active": False,
        "age_group": "ukendt",
        "best_snatch": None,
        "best_cj": None,
        "best_total": None,
        "best_sinclair": None,
    },
]
AGES = [{"year": 2019, "year_lifters": 2, "groups": [
    {"age_group": "senior", "lifters": 1, "share_of_max": Decimal("0.5")},
    {"age_group": "ukendt", "lifters": 1, "share_of_max": Decimal("0.5")}]}]  # fmt: skip


EVENT = {
    "event_id": 1, "source_id": 15556, "title": "Ladies Open",
    "start_date": date(2027, 1, 9), "end_date": date(2027, 1, 9), "all_day": False,
    "venue": "AK. Atlas", "city": "Slagelse", "url": "https://vaegtloeftning.dk/eventevents/ladies-open/",
    "first_seen_at": datetime(2026, 10, 28, 6, tzinfo=UTC), "kind": "staevne",
    "is_abroad": False, "is_new": True,
}  # fmt: skip
COURSE = dict(EVENT, event_id=2, title="Trænerkursus trin 1", venue=None, city=None,
              kind="kursus", is_new=False, start_date=date(2027, 1, 15),
              end_date=date(2027, 1, 16))  # fmt: skip

DATA_ROW = {
    "lifter_id": 689, "name": "Peter Klinge Wulff", "gender": "M", "birth_year": 2001,
    "club": "AK Gotha", "region": "Hovedstaden", "latest_bodyweight": Decimal("80.4"),
    "weight_class": "-88", "pr_snatch": 100, "pr_cj": 125, "pr_total": 225,
    "pr_sinclair": Decimal("281.37"), "competitions": 15, "last_date": date(2026, 9, 26),
    "is_active": True, "age_group": "senior", "first_date": date(2019, 11, 17),
    "is_new": False, "last_pr_date": date(2025, 2, 1), "has_recent_pr": False, "area": "Sjælland",
}  # fmt: skip
COEFFICIENTS = [
    {"gender": g, "a": Decimal(a), "b": Decimal(b), "valid_from_year": y0, "valid_to_year": y1}
    for g, a, b, y0, y1 in [
        ("F", "0.674119984", "163.916", 2026, 2028),
        ("M", "0.700752735", "201.161", 2026, 2028),
        ("F", "0.787004341", "153.757", 2021, 2025),
        ("M", "0.722762521", "193.609", 2021, 2025),
    ]
]


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
    monkeypatch.setattr(q, "all_clubs", lambda: [CLUB])
    monkeypatch.setattr(q, "club_summary", lambda club: CLUB if club == CLUB["club"] else None)
    monkeypatch.setattr(q, "club_records", lambda club: CLUB_RECORDS)
    monkeypatch.setattr(q, "club_top_sinclair", lambda club, per_gender=5: {"F": [], "M": [TOP]})
    monkeypatch.setattr(q, "club_lifters", lambda club: CLUB_LIFTERS)
    monkeypatch.setattr(
        q, "club_loyal", lambda club, limit=4: {"starts": CLUB_LIFTERS, "years": CLUB_LIFTERS}
    )
    monkeypatch.setattr(q, "club_age_profile", lambda club: AGES)
    monkeypatch.setattr(q, "competition_summary", lambda competition_id: None)
    monkeypatch.setattr(q, "upcoming_events", lambda limit=None, meets_only=False: [EVENT])
    monkeypatch.setattr(
        q, "calendar_months", lambda: [{"month": date(2027, 1, 1), "events": [EVENT, COURSE]}]
    )
    monkeypatch.setattr(q, "calendar_synced_at", lambda: datetime(2026, 10, 31, 6, tzinfo=UTC))
    monkeypatch.setattr(q, "lifter_data", lambda: [DATA_ROW])
    monkeypatch.setattr(q, "sinclair_coefficients", lambda: COEFFICIENTS)
    with TestClient(app_main.app) as c:
        yield c


def test_front_page(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Pløk" in r.text and "vlstat.dk" in r.text
    assert "Kommende stævner" in r.text and "Ladies Open" in r.text


def test_calendar_page(client):
    r = client.get("/kalender")
    assert r.status_code == 200
    text = r.text
    assert "januar 2027" in text and "hentet 31. okt. 2026" in text
    assert 'href="https://vaegtloeftning.dk/eventevents/ladies-open/"' in text
    assert "AK. Atlas, Slagelse" in text and "tilføjet 28. okt." in text
    assert "15.–16. jan. 2027" in text and "Kursus ·" not in text and "Kursus" in text
    assert "None" not in text


def test_club_logos_exist_and_wheel_renders(client):
    logos_dir = app_main.HERE / "static" / "logos"
    assert app_main.CLUB_LOGOS
    for logo in app_main.CLUB_LOGOS:
        assert (logos_dir / logo["file"]).is_file(), logo["file"]
    r = client.get("/")
    first = app_main.CLUB_LOGOS[0]
    # Each logo appears twice (the loop copy), but only the first copy has alt text.
    assert r.text.count(f"/static/logos/{first['file']}") == 2
    assert r.text.count(f'alt="{first["club"]}"') == 1


def test_search_partial(client):
    r = client.get("/sog", params={"q": "test"})
    assert r.status_code == 200
    assert 'href="/loefter/7"' in r.text


def test_unknown_lifter_and_competition_are_404(client):
    assert client.get("/loefter/1").status_code == 404
    assert client.get("/staevne/1").status_code == 404


def test_search_partial_lists_clubs_by_danish_spelling(client):
    r = client.get("/sog", params={"q": "aarhus"})
    assert r.status_code == 200
    assert 'href="/klub/aarhus-atlet-klub"' in r.text
    assert "Klubber" in r.text


def test_club_page(client):
    r = client.get("/klub/aarhus-atlet-klub")
    assert r.status_code == 200
    text = r.text
    assert "Århus Atlet Klub" in text
    assert "aarhus-ak.webp" in text  # logo mapped through vlstat_club in logos.json
    assert "288<small>kg</small>" in text  # record total, shown like the other records
    assert "373,0" in text
    # One roster table; filters and sorting work on these row attributes in the browser.
    assert 'data-status="active" data-gender="M" data-age="senior"' in text
    assert 'data-status="former" data-gender="F" data-age="ukendt"' in text
    assert 'value="active" checked' in text  # active lifters shown first
    assert 'data-v="373.03"' in text and "table-tools.js" in text
    assert "Ukendt alder" in text
    assert "None" not in text


def test_unknown_or_placeholder_club_is_404(client):
    assert client.get("/klub/ak-findes-ikke").status_code == 404
    assert client.get("/klub/andre").status_code == 404


def test_static_urls_are_versioned(client):
    r = client.get("/")
    m = re.search(r'href="(/static/css/site\.css\?v=\d+)"', r.text)
    assert m, "stylesheet link should carry a version"
    assert client.get(m.group(1)).status_code == 200


def test_pages_are_kept_out_of_search_engines(client):
    assert '<meta name="robots" content="noindex, nofollow">' in client.get("/").text


def test_static_build_swaps_server_search_for_browser_search(client, monkeypatch):
    assert 'hx-get="/sog"' in client.get("/").text
    monkeypatch.setitem(app_main.templates.env.globals, "static_site", True)
    text = client.get("/").text
    assert 'data-index="/sog.json"' in text and "js/search.js" in text
    assert 'hx-get="/sog"' not in text


def test_front_page_logos_link_to_club_pages(client):
    text = client.get("/").text
    # Århus Atlet Klub has a page (logo mapped through vlstat_club); the loop copy is
    # kept out of the tab order.
    assert text.count('href="/klub/aarhus-atlet-klub"') == 2
    assert text.count('href="/klub/aarhus-atlet-klub" tabindex="-1"') == 1
    # Clubs without a page in the data get a plain logo.
    assert 'href="/klub/ak-gotha"' not in text


def test_footer_credits_both_sources(client):
    text = client.get("/").text
    assert "Data fra" in text and 'href="https://vaegtloeftning.dk"' in text
    assert "regnet ud af os selv" not in text


def test_lifter_data_rows_and_sinclair_sets():
    from core.clubs import club_slug

    (row,) = formatting.lifter_data_rows([DATA_ROW], club_slug)
    assert row == {
        "id": 689, "name": "Peter Klinge Wulff", "g": "M", "club": "AK Gotha",
        "slug": "ak-gotha", "area": "Sjælland", "wc": "-85", "sn": 100, "cj": 125,
        "tot": 225, "sin": 281.37, "age": "senior", "active": True, "form": False,
        "lastPr": "2025-02-01", "lastPrText": "1. feb. 2025",
    }  # fmt: skip
    sets = formatting.sinclair_sets(COEFFICIENTS)
    assert [(s["from"], s["to"]) for s in sets] == [(2026, 2028), (2021, 2025)]
    assert sets[0]["M"] == {"a": 0.700752735, "b": 201.161}


def test_data_page(client):
    r = client.get("/data")
    assert r.status_code == 200
    text = r.text
    assert '<script type="application/json" id="data-lifters">' in text
    assert '"name": "Peter Klinge Wulff"' in text and '"slug": "ak-gotha"' in text
    assert [
        a
        for a in ("Sjælland", "Fyn", "Jylland", "Hovedstaden", "Udland", "ukendt")
        if f'name="region" value="{a}"' in text
    ] == ["Sjælland", "Fyn", "Jylland"]
    assert 'name="status" value="active"' in text and 'name="status" value="form"' not in text
    assert 'name="status" value="new"' not in text and 'name="age" value="junior"' in text
    assert "<select" not in text and "js/lifter-data.js" in text
    assert 'href="/data"' in text  # in the main menu


def test_points_page(client):
    r = client.get("/point")
    assert r.status_code == 200
    text = r.text
    assert "Pointberegner" in text and '"from": 2026' in text and ">2026–2028<" in text
    assert '"qpoints": {"F": {' in text and '"scale": 463.26' in text
    assert "js/points.js" in text and 'href="/point"' in text
    assert "<select" not in text
    assert "Sådan regnes det" not in text
    assert ">DM-krav<" in text and '"qualifying_total": 190' in text
