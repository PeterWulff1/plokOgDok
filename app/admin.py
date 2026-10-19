"""Admin page: login, add competitions from a form or CSV, delete manual competitions.

Security: password from ADMIN_PASSWORD (constant-time compare, lockout after repeated
failures), signed session cookie, CSRF token on every POST, write role only here.
"""

import os
import secrets
import time
from collections import defaultdict
from datetime import date

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from starlette.datastructures import UploadFile

from core.manual_entry import COLUMNS, ParsedUpload, parse_csv, to_csv
from db import admin as store

router = APIRouter(prefix="/admin")

MAX_UPLOAD_BYTES = 1_000_000
FORM_ROWS = 8
LOCKOUT_FAILURES = 8
LOCKOUT_SECONDS = 15 * 60
_failures: dict[str, list[float]] = defaultdict(list)


def _templates():
    from app.main import templates  # avoid a circular import at module load

    return templates


def _render(request: Request, name: str, status_code: int = 200, **context) -> HTMLResponse:
    context.setdefault("csrf", _csrf_token(request))
    context.setdefault("flash", request.session.pop("flash", None))
    return _templates().TemplateResponse(request, name, context, status_code=status_code)


# --- Session helpers ----------------------------------------------------------------


def _admin_password() -> str | None:
    pw = os.environ.get("ADMIN_PASSWORD", "")
    return pw if pw and pw != "CHANGE_ME" else None


def _logged_in(request: Request) -> bool:
    return request.session.get("admin") is True


def _csrf_token(request: Request) -> str:
    if "csrf" not in request.session:
        request.session["csrf"] = secrets.token_urlsafe(32)
    return request.session["csrf"]


def _check_csrf(request: Request, token: str) -> None:
    expected = request.session.get("csrf")
    if not expected or not secrets.compare_digest(expected, token or ""):
        raise HTTPException(400, "Formularen er udløbet. Genindlæs siden og prøv igen.")


def _require_admin(request: Request) -> RedirectResponse | None:
    if not _logged_in(request):
        return RedirectResponse("/admin/login", status_code=303)
    return None


def _client(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _locked_out(client: str) -> bool:
    now = time.monotonic()
    _failures[client] = [t for t in _failures[client] if now - t < LOCKOUT_SECONDS]
    return len(_failures[client]) >= LOCKOUT_FAILURES


# --- Login ------------------------------------------------------------------------


@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    if _logged_in(request):
        return RedirectResponse("/admin", status_code=303)
    return _render(request, "admin/login.html", disabled=_admin_password() is None)


@router.post("/login", response_class=HTMLResponse)
def login(request: Request, password: str = Form(""), csrf: str = Form("")):
    _check_csrf(request, csrf)
    expected = _admin_password()
    client = _client(request)
    if expected is None:
        return _render(request, "admin/login.html", status_code=503, disabled=True)
    if _locked_out(client):
        return _render(request, "admin/login.html", status_code=429,
                       error="For mange forkerte forsøg. Vent et kvarter.")  # fmt: skip
    if not secrets.compare_digest(password.encode(), expected.encode()):
        _failures[client].append(time.monotonic())
        time.sleep(1)  # slows down guessing
        return _render(request, "admin/login.html", status_code=401, error="Forkert password.")
    _failures.pop(client, None)
    request.session.clear()
    request.session["admin"] = True  # new session, new CSRF token
    return RedirectResponse("/admin", status_code=303)


@router.post("/logout")
def logout(request: Request, csrf: str = Form("")):
    _check_csrf(request, csrf)
    request.session.clear()
    return RedirectResponse("/", status_code=303)


# --- Overview and upload --------------------------------------------------------------


def _blank_rows() -> list[dict[str, str]]:
    return [dict.fromkeys(COLUMNS, "") for _ in range(FORM_ROWS)]


@router.get("", response_class=HTMLResponse)
def overview(request: Request):
    if redirect := _require_admin(request):
        return redirect
    return _render(
        request, "admin/index.html",
        competitions=store.manual_competitions(), columns=COLUMNS,
        form={"name": "", "date": "", "location": ""}, rows=_blank_rows(),
        saved_id=request.session.pop("saved_id", None),
    )  # fmt: skip


@router.get("/skabelon.csv")
def csv_template(request: Request):
    if redirect := _require_admin(request):
        return redirect
    example = "Mette Eksempel;;K;1998;AK Eksempel;-64kg;63,4;70;73x;74;88;-92;92\n"
    return PlainTextResponse(
        ";".join(COLUMNS) + "\n" + example,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="ploek-og-doek-skabelon.csv"'},
    )


def _form_rows(form) -> list[dict[str, str]]:
    rows: dict[int, dict[str, str]] = defaultdict(lambda: dict.fromkeys(COLUMNS, ""))
    for key, value in form.multi_items():
        parts = key.split("-", 2)
        if len(parts) == 3 and parts[0] == "rows" and parts[1].isdigit() and parts[2] in COLUMNS:
            rows[int(parts[1])][parts[2]] = str(value)
    return [rows[i] for i in sorted(rows)]


def _competition_fields(name: str, date_text: str, location: str) -> tuple[dict, list[str]]:
    errors = []
    fields = {"name": " ".join(name.split()), "date": date_text.strip(),
              "location": " ".join(location.split())}  # fmt: skip
    if not fields["name"]:
        errors.append("Stævnet skal have et navn.")
    try:
        parsed = date.fromisoformat(fields["date"])
        if not date(1990, 1, 1) <= parsed <= date.today().replace(year=date.today().year + 1):
            errors.append("Datoen ligger uden for det forventede interval.")
    except ValueError:
        errors.append("Angiv en gyldig dato.")
    return fields, errors


@router.post("/forhaandsvis", response_class=HTMLResponse)
async def preview(request: Request):
    if redirect := _require_admin(request):
        return redirect
    form = await request.form()
    _check_csrf(request, str(form.get("csrf", "")))
    fields, errors = _competition_fields(
        str(form.get("name", "")), str(form.get("date", "")), str(form.get("location", ""))
    )

    upload = form.get("csv_file")
    form_rows = _form_rows(form)
    if isinstance(upload, UploadFile) and upload.filename:
        data = await upload.read(MAX_UPLOAD_BYTES + 1)
        if len(data) > MAX_UPLOAD_BYTES:
            errors.append("Filen er for stor (højst 1 MB).")
            csv_text = ""
        else:
            try:
                csv_text = data.decode("utf-8-sig")
            except UnicodeDecodeError:
                csv_text = data.decode("cp1252")  # Excel on Danish Windows
    else:
        csv_text = to_csv(form_rows)

    parsed = parse_csv(csv_text) if csv_text else ParsedUpload(errors=["Ingen løftere angivet."])
    errors += parsed.errors
    if errors:
        return _render(
            request, "admin/index.html", status_code=422,
            competitions=store.manual_competitions(), columns=COLUMNS, form=fields,
            rows=form_rows or _blank_rows(), errors=errors,
        )  # fmt: skip

    matches = store.match_lifters(parsed.rows)
    return _render(
        request, "admin/preview.html",
        form=fields, csv_text=csv_text, rows=list(zip(parsed.rows, matches, strict=True)),
        blocked=any(m.kind == "problem" for m in matches),
    )  # fmt: skip


@router.post("/gem")
def save(
    request: Request,
    csrf: str = Form(""),
    name: str = Form(""),
    date_text: str = Form("", alias="date"),
    location: str = Form(""),
    csv_text: str = Form(""),
):
    if redirect := _require_admin(request):
        return redirect
    _check_csrf(request, csrf)
    fields, errors = _competition_fields(name, date_text, location)
    parsed = parse_csv(csv_text)
    errors += parsed.errors
    if not errors:
        try:
            comp_id = store.save_competition(
                fields["name"], date.fromisoformat(fields["date"]), fields["location"] or None,
                parsed.rows,
            )  # fmt: skip
        except ValueError as exc:
            errors.append(str(exc))
    if errors:
        request.session["flash"] = "Ikke gemt: " + " ".join(errors)
        return RedirectResponse("/admin", status_code=303)
    request.session["flash"] = f"Gemt: {fields['name']} med {len(parsed.rows)} løftere."
    request.session["saved_id"] = comp_id
    return RedirectResponse("/admin", status_code=303)


@router.post("/slet/{competition_id}")
def delete(request: Request, competition_id: int, csrf: str = Form("")):
    if redirect := _require_admin(request):
        return redirect
    _check_csrf(request, csrf)
    ok = store.delete_manual_competition(competition_id)
    request.session["flash"] = "Stævnet er slettet." if ok else "Stævnet kunne ikke slettes."
    return RedirectResponse("/admin", status_code=303)
