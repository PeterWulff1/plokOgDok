"""Parse one saved vlstat Results.aspx page into Entry models. Pure function, no I/O.

Table layout (Main_grdResults), one <tr> per lifter, 23 cells:
  0 lifter id (hidden) | 1 class (hidden) | 2 placement | 3 name | 4 club | 5 age | 6 bodyweight
  7/8, 9/10, 11/12   snatch attempt 1-3: weight / hidden "True"|"False" | 13 best snatch
  14/15, 16/17, 18/19 C&J attempt 1-3:   weight / hidden "True"|"False" | 20 best C&J
  21 total | 22 points: "Sinclair", "Masters-sinclair" (age-adjusted) or "Q-points"
Rows with class "gv-class-header" start a weight class, e.g. "-61kg  Kvinder". Some meets
(CWC, team and Sinclair-only meets) group by gender only: "Mænd" -> weight class None.
We ignore vlstat's placement, best, total and Sinclair, except that total and Sinclair are
returned separately for validating our own calculations.
"""

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from bs4 import BeautifulSoup, Tag
from pydantic import ValidationError

from core.models import Attempt, Discipline, Entry, Gender

EXPECTED_HEADERS = [
    "Id", "", "", "Navn", "Klub", "Alder", "Vægt",
    "1.", "", "2.", "", "3.", "", "Bedste",
    "1.", "", "2.", "", "3.", "", "Bedste",
    "Total", "Sinclair",
]  # fmt: skip
# Last header -> which points formula vlstat used on that page.
POINTS_HEADERS = {"Sinclair": "sinclair", "Masters-sinclair": "masters", "Q-points": "qpoints"}
AGE_RANGE = (5, 110)  # Same bounds as Entry.reported_age; outside it is a typo at vlstat.

ATTEMPT_CELLS = {
    Discipline.SNATCH: [(1, 7), (2, 9), (3, 11)],
    Discipline.CLEAN_AND_JERK: [(1, 14), (2, 16), (3, 18)],
}
GENDER_WORDS = {"mænd": Gender.MALE, "kvinder": Gender.FEMALE}

DANISH_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "maj": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "okt": 10, "nov": 11, "dec": 12,
}  # fmt: skip
_LABEL_RE = re.compile(r"^\s*(\d{1,2})([a-zæøå]{3})(\d{4})\s*-\s*(.+?)\s*$", re.IGNORECASE)
_OPTION_DATE_RE = re.compile(r"^\s*(\d{1,2})-([a-zæøå]{3})\s*$", re.IGNORECASE)


class PageFormatError(ValueError):
    """The page doesn't look like the layout this parser was written for."""


@dataclass(frozen=True)
class SourceScores:
    """vlstat's own numbers. Used only to check our calculations, never stored."""

    total: int | None
    points: Decimal | None
    points_kind: str  # "sinclair", "masters" (age-adjusted Sinclair) or "qpoints"


@dataclass(frozen=True)
class ParsedRow:
    entry: Entry
    source: SourceScores


@dataclass(frozen=True)
class ParseResult:
    rows: list[ParsedRow]
    errors: list[str]


def parse_competition_label(label: str) -> tuple[date, str]:
    """'12okt2026 - U23 EM 2026' -> (date(2026, 10, 12), 'U23 EM 2026')."""
    m = _LABEL_RE.match(label)
    if not m:
        raise PageFormatError(f"unrecognised competition label: {label!r}")
    day, month, year, name = m.groups()
    month_number = DANISH_MONTHS.get(month.lower())
    if month_number is None:
        raise PageFormatError(f"unknown month {month!r} in {label!r}")
    return date(int(year), month_number, int(day)), name


def parse_option_date(text: str, year: int) -> date:
    """'24-okt', 2026 -> date(2026, 10, 24). Since Oct 2026 vlstat's competition dropdown
    shows only the name and puts the day and month in the option's data-date attribute;
    the year is the year selected in the other dropdown."""
    m = _OPTION_DATE_RE.match(text)
    if not m:
        raise PageFormatError(f"unrecognised competition date: {text!r}")
    month_number = DANISH_MONTHS.get(m.group(2).lower())
    if month_number is None:
        raise PageFormatError(f"unknown month {m.group(2)!r} in {text!r}")
    return date(year, month_number, int(m.group(1)))


def _text(cell: Tag) -> str:
    return cell.get_text(strip=True).replace("\xa0", "")


def _int_or_none(value: str) -> int | None:
    return int(value) if value.isdigit() else None


def _decimal_or_none(value: str) -> Decimal | None:
    if not value:
        return None
    try:
        return Decimal(value.replace(",", "."))
    except InvalidOperation:
        return None


def _parse_class_header(text: str) -> tuple[str | None, Gender | None]:
    parts = text.split()
    gender = GENDER_WORDS.get(parts[-1].lower()) if parts else None
    weight_class = " ".join(parts[:-1]) if gender else " ".join(parts)
    return weight_class or None, gender


def _is_successful(weight_cell: Tag, flag_cell: Tag) -> bool:
    flag = _text(flag_cell)
    if flag in ("True", "False"):
        return flag == "True"
    # Fallback: vlstat colours missed attempts red.
    return "color:red" not in (weight_cell.get("style") or "").replace(" ", "").lower()


def _parse_attempts(cells: list[Tag]) -> list[Attempt]:
    attempts = []
    for discipline, slots in ATTEMPT_CELLS.items():
        for number, idx in slots:
            raw = _text(cells[idx])
            weight = _decimal_or_none(raw)
            if weight is None or weight <= 0:
                continue  # No recorded weight -> no row (docs/decisions.md).
            if weight != weight.to_integral_value():
                raise ValueError(f"non-integer attempt weight {raw!r}")
            attempts.append(
                Attempt(
                    discipline=discipline,
                    attempt_number=number,
                    weight_kg=int(weight),
                    is_successful=_is_successful(cells[idx], cells[idx + 1]),
                )
            )
    return attempts


def parse_results_page(html: str) -> ParseResult:
    soup = BeautifulSoup(html, "lxml")
    table = soup.find(id="Main_grdResults")
    if table is None:
        return ParseResult(rows=[], errors=["no results table"])

    header = next((tr for tr in table.find_all("tr") if tr.find("th")), None)
    headers = [_text(th) for th in header.find_all("th")] if header else []
    if not headers or headers[:-1] != EXPECTED_HEADERS[:-1] or headers[-1] not in POINTS_HEADERS:
        raise PageFormatError(f"unexpected table headers: {headers}")
    points_kind = POINTS_HEADERS[headers[-1]]

    rows: list[ParsedRow] = []
    errors: list[str] = []
    seen_class_header = False
    weight_class: str | None = None
    gender: Gender | None = None

    for tr in table.find_all("tr"):
        cells = tr.find_all("td")
        if "gv-class-header" in (tr.get("class") or []):
            weight_class, gender = _parse_class_header(_text(cells[1]) if len(cells) > 1 else "")
            seen_class_header = True
            continue
        if len(cells) != len(EXPECTED_HEADERS):
            continue  # header and group rows

        name = _text(cells[3])
        try:
            if not seen_class_header:
                raise ValueError("lifter row before any weight class header")
            age = _int_or_none(_text(cells[5]))
            if age is not None and not AGE_RANGE[0] <= age <= AGE_RANGE[1]:
                errors.append(f"{name}: age {age} out of range, stored as unknown (warning)")
                age = None
            entry = Entry(
                lifter_vlstat_id=int(_text(cells[0])),
                lifter_name=name,
                gender=gender,
                weight_class=weight_class,
                bodyweight=_decimal_or_none(_text(cells[6])),
                club=_text(cells[4]) or None,
                reported_age=age,
                reported_total=_int_or_none(_text(cells[21])),
                attempts=tuple(_parse_attempts(cells)),
            )
        except (ValueError, ValidationError) as exc:
            errors.append(f"{name or '?'}: {exc}")
            continue

        source = SourceScores(
            total=_int_or_none(_text(cells[21])),
            points=_decimal_or_none(_text(cells[22])),
            points_kind=points_kind,
        )
        rows.append(ParsedRow(entry=entry, source=source))

    return ParseResult(rows=rows, errors=errors)
