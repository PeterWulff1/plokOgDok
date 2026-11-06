"""Danish display formatting for templates. Formats values; never computes statistics."""

from dataclasses import asdict
from datetime import date
from decimal import Decimal
from typing import Any

MONTHS = ["jan.", "feb.", "mar.", "apr.", "maj", "jun.",
          "jul.", "aug.", "sep.", "okt.", "nov.", "dec."]  # fmt: skip
MONTH_NAMES = ["januar", "februar", "marts", "april", "maj", "juni", "juli",
               "august", "september", "oktober", "november", "december"]  # fmt: skip
GENDER_LABEL = {"M": "Mænd", "F": "Kvinder"}
DISCIPLINE_LABEL = {"snatch": "Træk", "cj": "Stød"}
EVENT_KIND_LABEL = {"staevne": "Stævne", "kursus": "Kursus", "moede": "Møde"}


def num(value: Any, decimals: int = 0) -> str:
    """1234.5 -> '1.234,5'. None -> '–'."""
    if value is None:
        return "–"
    text = f"{float(value):,.{decimals}f}"
    return text.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def pct(value: Any) -> str:
    """0.5552 -> '56 %'."""
    return "–" if value is None else f"{round(float(value) * 100)} %"


def css_pct(value: Any) -> str:
    """0.5552 -> '55.52%' for CSS widths."""
    return "0%" if value is None else f"{float(value) * 100:.2f}%"


def signed_pct(value: Any) -> str:
    """-0.5058 -> '−51 point' (percentage points)."""
    if value is None:
        return "–"
    points = round(float(value) * 100)
    return f"{'+' if points > 0 else '−' if points < 0 else '±'}{abs(points)} point"


def dk_date(value: date | None, with_year: bool = True) -> str:
    if value is None:
        return "–"
    text = f"{value.day}. {MONTHS[value.month - 1]}"
    return f"{text} {value.year}" if with_year else text


def dk_date_range(start: date, end: date | None) -> str:
    """'7. nov. 2026', '13.–14. nov. 2026', '30. jan.–1. feb. 2027'."""
    if end is None or end == start:
        return dk_date(start)
    if (start.year, start.month) == (end.year, end.month):
        return f"{start.day}.–{dk_date(end)}"
    if start.year == end.year:
        return f"{dk_date(start, with_year=False)}–{dk_date(end)}"
    return f"{dk_date(start)}–{dk_date(end)}"


def dk_month(value: date) -> str:
    """date(2026, 11, 1) -> 'november 2026'."""
    return f"{MONTH_NAMES[value.month - 1]} {value.year}"


def event_kind(value: str) -> str:
    return EVENT_KIND_LABEL.get(value, value)


def gender(value: str | None) -> str:
    return GENDER_LABEL.get(value or "", "")


def discipline(value: str) -> str:
    return DISCIPLINE_LABEL.get(value, value)


def progression_series(history: list[dict]) -> dict:
    """Chart data for the profile: best snatch and C&J per competition, oldest first.
    Only picks fields already computed by the views."""
    rows = [r for r in reversed(history) if r["best_snatch"] or r["best_cj"]]

    def _f(v: Decimal | int | None) -> float | None:
        return None if v is None else float(v)

    return {
        "dates": [r["date"].isoformat() for r in rows],
        "competitions": [r["competition"] for r in rows],
        "snatch": [_f(r["best_snatch"]) for r in rows],
        "cj": [_f(r["best_cj"]) for r in rows],
        "pr_snatch": [bool(r["is_pr_snatch"]) and not r["is_debut"] for r in rows],
        "pr_cj": [bool(r["is_pr_cj"]) and not r["is_debut"] for r in rows],
    }


def _float(v: Decimal | int | float | None) -> float | None:
    return None if v is None else float(v)


# Parts of the country on the data page (vl.v_lifter_data.area), east to west.
AREAS = ["Sjælland", "Fyn", "Jylland"]


def lifter_data_rows(rows: list[dict], club_slug) -> list[dict]:
    """Rows from vl.v_lifter_data as compact JSON for the data page (static/js/lifter-data.js).
    Only renames and formats fields; every number comes from the view."""
    return [
        {
            "id": r["lifter_id"],
            "name": r["name"],
            "g": r["gender"],
            "club": r["club"],
            "slug": club_slug(r["club"]),
            "area": r["area"],
            "wc": r["weight_class"],
            "sn": r["pr_snatch"],
            "cj": r["pr_cj"],
            "tot": r["pr_total"],
            "sin": _float(r["pr_sinclair"]),
            "age": r["age_group"],
            "active": bool(r["is_active"]),
            "form": bool(r["has_recent_pr"]),
            "lastPr": r["last_pr_date"].isoformat() if r["last_pr_date"] else None,
            "lastPrText": dk_date(r["last_pr_date"]) if r["last_pr_date"] else None,
        }
        for r in rows
    ]


def sinclair_sets(rows: list[dict]) -> list[dict]:
    """Coefficient rows grouped per period for the calculator, newest first:
    [{"from": 2026, "to": 2028, "F": {"a": .., "b": ..}, "M": {...}}]."""
    sets: list[dict] = []
    for r in rows:
        if not sets or sets[-1]["from"] != r["valid_from_year"]:
            sets.append({"from": r["valid_from_year"], "to": r["valid_to_year"]})
        sets[-1][r["gender"]] = {"a": float(r["a"]), "b": float(r["b"])}
    return sets


def q_points_constants(q_points: dict) -> dict:
    """core.scoring.Q_POINTS as JSON for the calculator: {"F": {"scale": ...}, "M": {...}}."""
    return {str(gender): asdict(c) for gender, c in q_points.items()}


FILTERS = {
    "num": num,
    "pct": pct,
    "css_pct": css_pct,
    "signed_pct": signed_pct,
    "dk_date": dk_date,
    "dk_date_range": dk_date_range,
    "dk_month": dk_month,
    "event_kind": event_kind,
    "gender": gender,
    "discipline": discipline,
}
