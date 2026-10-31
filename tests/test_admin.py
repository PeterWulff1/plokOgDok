"""Admin routes with the database replaced by fakes: login, CSRF, access, preview, save."""

import re

import pytest
from fastapi.testclient import TestClient

from app import admin as admin_routes
from app import main as app_main
from core.manual_entry import COLUMNS, CSV_COLUMNS
from db.admin import LifterMatch

PASSWORD = "korrekt-hest-batteri"


@pytest.fixture
def saved():
    return []


@pytest.fixture
def client(monkeypatch, saved):
    monkeypatch.setenv("ADMIN_PASSWORD", PASSWORD)
    monkeypatch.setattr(admin_routes, "_failures", {}, raising=True)
    monkeypatch.setattr(admin_routes, "_failures", __import__("collections").defaultdict(list))
    monkeypatch.setattr(admin_routes.time, "sleep", lambda s: None)
    q = app_main.queries
    monkeypatch.setattr(q, "open_pool", lambda url=None: None)
    monkeypatch.setattr(q, "close_pool", lambda: None)
    store = admin_routes.store
    monkeypatch.setattr(store, "close_pool", lambda: None)
    monkeypatch.setattr(store, "manual_competitions", lambda: [])
    monkeypatch.setattr(store, "match_lifters", lambda rows: [LifterMatch("new") for _ in rows])

    def fake_save(name, comp_date, location, rows):
        saved.append((name, comp_date, location, rows))
        return 42

    monkeypatch.setattr(store, "save_competition", fake_save)
    with TestClient(app_main.app) as c:
        yield c


def _csrf(html: str) -> str:
    return re.search(r'name="csrf" value="([^"]+)"', html).group(1)


def _login(client, password=PASSWORD):
    token = _csrf(client.get("/admin/login").text)
    return client.post("/admin/login", data={"password": password, "csrf": token},
                       follow_redirects=False)  # fmt: skip


def test_admin_requires_login(client):
    r = client.get("/admin", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/admin/login"
    assert client.get("/admin/skabelon.csv", follow_redirects=False).status_code == 303


def test_wrong_password_rejected(client):
    assert _login(client, "forkert").status_code == 401
    assert client.get("/admin", follow_redirects=False).status_code == 303


def test_lockout_after_repeated_failures(client):
    for _ in range(admin_routes.LOCKOUT_FAILURES):
        _login(client, "forkert")
    assert _login(client).status_code == 429  # even the right password is refused for now


def test_login_requires_csrf(client):
    client.get("/admin/login")
    r = client.post("/admin/login", data={"password": PASSWORD, "csrf": "nope"})
    assert r.status_code == 400


def test_login_then_overview(client):
    r = _login(client)
    assert r.status_code == 303 and r.headers["location"] == "/admin"
    page = client.get("/admin")
    assert page.status_code == 200 and "Nyt stævne" in page.text
    assert 'name="robots" content="noindex' in page.text


def test_disabled_without_password(client, monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD", "CHANGE_ME")
    assert "slået fra" in client.get("/admin/login").text


def _form(token, **rows):
    data = {"csrf": token, "name": "Klubstævne", "date": "2026-10-18", "location": "Odense"}
    for i, row in rows.items():
        for col in COLUMNS:
            data[f"rows-{i[1:]}-{col}"] = row.get(col, "")
    return data


def test_preview_and_save_from_form(client, saved):
    _login(client)
    token = _csrf(client.get("/admin").text)
    row = {"navn": "Ole Testsen", "køn": "M", "vægtklasse": "-81kg",
           "kropsvægt": "80,2", "t1": "100", "t2": "105x", "s1": "125"}  # fmt: skip
    data = _form(token, r0=row)
    preview = client.post("/admin/forhaandsvis", data=data)
    assert preview.status_code == 200, preview.text
    assert "Ole Testsen" in preview.text and "Ny løfter" in preview.text
    assert saved == []  # nothing saved by previewing

    csv_text = re.search(
        r'<textarea name="csv_text" hidden>(.*?)</textarea>', preview.text, re.S
    ).group(1)
    r = client.post("/admin/gem", data={"csrf": token, "name": "Klubstævne", "date": "2026-10-18",
                                        "location": "Odense", "csv_text": csv_text},
                    follow_redirects=False)  # fmt: skip
    assert r.status_code == 303
    assert len(saved) == 1 and saved[0][0] == "Klubstævne" and len(saved[0][3]) == 1


def test_preview_shows_errors(client):
    _login(client)
    token = _csrf(client.get("/admin").text)
    data = _form(token, r0={"navn": "Ole", "køn": "Q"})
    data["date"] = "ikke en dato"
    r = client.post("/admin/forhaandsvis", data=data)
    assert r.status_code == 422
    assert "gyldig dato" in r.text and "køn" in r.text


def test_csv_upload_preview(client):
    _login(client)
    token = _csrf(client.get("/admin").text)
    csv_bytes = (";".join(COLUMNS) + "\nMia;;K;;AK X;-64kg;63;70;;;90;;\n").encode("utf-8")
    r = client.post(
        "/admin/forhaandsvis",
        data={"csrf": token, "name": "CSV-stævne", "date": "2026-10-18", "location": ""},
        files={"csv_file": ("resultater.csv", csv_bytes, "text/csv")},
    )
    assert r.status_code == 200 and "Mia" in r.text


def test_save_requires_csrf(client, saved):
    _login(client)
    r = client.post("/admin/gem", data={"csrf": "nope", "name": "X", "date": "2026-10-18",
                                        "csv_text": "navn;køn\nOle;M\n"})  # fmt: skip
    assert r.status_code == 400 and saved == []


def test_csv_template_has_no_hidden_columns(client):
    _login(client)
    header = client.get("/admin/skabelon.csv").text.splitlines()[0]
    assert header == ";".join(CSV_COLUMNS) and "lifter_id" not in header


def test_lifter_suggestions_require_login(client):
    r = client.get("/admin/loeftere?q=ole")
    assert r.status_code == 401


def test_lifter_suggestions_in_form_values(client, monkeypatch):
    from datetime import date

    seen = []

    def fake_search(q):
        seen.append(q)
        return [{"id": 7, "name": "Mia Test", "gender": "F", "birth_year": 2001,
                 "club": "AK X", "weight_class": "-64kg", "last_date": date(2026, 5, 1)},
                {"id": 8, "name": "Ny Testsen", "gender": "M", "birth_year": None,
                 "club": None, "weight_class": None, "last_date": None}]  # fmt: skip

    monkeypatch.setattr(admin_routes.store, "search_lifters", fake_search)
    _login(client)
    r = client.get("/admin/loeftere", params={"q": "mi" * 50})
    assert r.status_code == 200 and len(seen[0]) == 60  # long queries are cut
    first, second = r.json()
    assert first == {"id": 7, "name": "Mia Test", "club": "AK X", "gender": "K", "birth_year": 2001,
                     "weight_class": "-64kg", "last_date": "2026-05-01"}  # fmt: skip
    assert second["club"] == "" and second["birth_year"] == "" and second["gender"] == "M"


def test_entry_grid_has_hidden_lifter_id(client):
    _login(client)
    html = client.get("/admin").text
    assert 'name="rows-0-lifter_id"' in html and 'type="hidden"' in html
    assert "admin-entry.js" in html
