"""Danish display formatting for templates. Formats values; never computes statistics."""

from datetime import date
from decimal import Decimal
from typing import Any

MONTHS = ["jan.", "feb.", "mar.", "apr.", "maj", "jun.",
          "jul.", "aug.", "sep.", "okt.", "nov.", "dec."]  # fmt: skip
GENDER_LABEL = {"M": "Mænd", "F": "Kvinder"}
DISCIPLINE_LABEL = {"snatch": "Træk", "cj": "Stød"}


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


FILTERS = {
    "num": num,
    "pct": pct,
    "css_pct": css_pct,
    "signed_pct": signed_pct,
    "dk_date": dk_date,
    "gender": gender,
    "discipline": discipline,
}
