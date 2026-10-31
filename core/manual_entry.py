"""Rules for results typed in on the admin page, via CSV or the form. Pure, no I/O.

Both inputs end up as the same row dicts and go through parse_rows(), so the rules are
identical. Columns (Danish, case-insensitive, CSV separator ; or ,):

    navn; vlstat_id; køn; fødselsår; klub; vægtklasse; kropsvægt; t1; t2; t3; s1; s2; s3

- køn: M/mand/mænd or K/F/kvinde/kvinder. Required for new lifters.
- t1-t3 / s1-s3 (snatch/C&J attempts): "95" = made, "95x" or "-95" = missed, blank = no attempt.
- kropsvægt accepts a decimal comma.
- lifter_id (optional, our own id) is set by the form's name autocomplete. It pins the row
  to an existing lifter, so name, vlstat_id and gender are not used for matching.
"""

import csv
import io
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from pydantic import ValidationError

from core.models import Attempt, Discipline, Entry, Gender

CSV_COLUMNS = [
    "navn", "vlstat_id", "køn", "fødselsår", "klub", "vægtklasse", "kropsvægt",
    "t1", "t2", "t3", "s1", "s2", "s3",
]  # fmt: skip
COLUMNS = [*CSV_COLUMNS, "lifter_id"]  # the form adds a hidden lifter_id
REQUIRED = {"navn"}
ATTEMPT_COLUMNS = {
    Discipline.SNATCH: ["t1", "t2", "t3"],
    Discipline.CLEAN_AND_JERK: ["s1", "s2", "s3"],
}
GENDERS = {
    "m": Gender.MALE, "mand": Gender.MALE, "mænd": Gender.MALE,
    "k": Gender.FEMALE, "f": Gender.FEMALE, "kvinde": Gender.FEMALE, "kvinder": Gender.FEMALE,
}  # fmt: skip
_ATTEMPT_RE = re.compile(r"^(-)?\s*(\d{1,3})\s*([xX])?$")
MAX_ROWS = 500


@dataclass(frozen=True)
class ManualRow:
    line: int  # 1-based, as the user sees it (CSV header is line 1)
    entry: Entry
    birth_year: int | None
    lifter_id: int | None = None  # set when the form's autocomplete picked a lifter


@dataclass
class ParsedUpload:
    rows: list[ManualRow] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors and bool(self.rows)


def parse_attempt(text: str) -> tuple[int, bool] | None:
    """'95' -> (95, True), '95x' / '-95' -> (95, False), '' -> None. Raises on junk."""
    text = text.strip()
    if not text:
        return None
    m = _ATTEMPT_RE.match(text)
    if not m or (m.group(1) and m.group(3)):
        raise ValueError(f"forstår ikke forsøget {text!r} (skriv f.eks. 95 eller 95x)")
    weight = int(m.group(2))
    if weight == 0:
        return None
    return weight, not (m.group(1) or m.group(3))


def _decimal(text: str, what: str) -> Decimal | None:
    text = text.strip().replace(",", ".")
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        raise ValueError(f"{what} {text!r} er ikke et tal") from None


def _int(text: str, what: str) -> int | None:
    text = text.strip()
    if not text:
        return None
    if not text.isdigit():
        raise ValueError(f"{what} {text!r} er ikke et heltal")
    return int(text)


def _row_to_entry(raw: dict[str, str]) -> tuple[Entry, int | None]:
    gender_text = raw.get("køn", "").strip().lower()
    gender = GENDERS.get(gender_text) if gender_text else None
    if gender_text and gender is None:
        raise ValueError(f"køn {raw['køn']!r} skal være M eller K")

    attempts = []
    for discipline, cols in ATTEMPT_COLUMNS.items():
        for number, col in enumerate(cols, start=1):
            parsed = parse_attempt(raw.get(col, ""))
            if parsed:
                weight, made = parsed
                attempts.append(
                    Attempt(discipline=discipline, attempt_number=number,
                            weight_kg=weight, is_successful=made)
                )  # fmt: skip

    entry = Entry(
        lifter_vlstat_id=_int(raw.get("vlstat_id", ""), "vlstat_id"),
        lifter_name=" ".join(raw.get("navn", "").split()),
        gender=gender,
        weight_class=raw.get("vægtklasse", "").strip() or None,
        bodyweight=_decimal(raw.get("kropsvægt", ""), "kropsvægt"),
        club=raw.get("klub", "").strip() or None,
        attempts=tuple(attempts),
    )
    return entry, _int(raw.get("fødselsår", ""), "fødselsår")


def _short(exc: ValidationError) -> str:
    return "; ".join(f"{'.'.join(map(str, e['loc'])) or 'række'}: {e['msg']}" for e in exc.errors())


def parse_rows(raw_rows: list[tuple[int, dict[str, str]]]) -> ParsedUpload:
    """raw_rows: (line number, {column: text}). Blank rows are skipped."""
    out = ParsedUpload()
    seen: dict[tuple, int] = {}
    for line, raw in raw_rows:
        if not any((v or "").strip() for v in raw.values()):
            continue
        if len(out.rows) >= MAX_ROWS:
            out.errors.append(f"Højst {MAX_ROWS} løftere pr. stævne.")
            break
        try:
            entry, birth_year = _row_to_entry(raw)
            lifter_id = _int(raw.get("lifter_id", ""), "lifter_id")
            if birth_year is not None and not 1900 <= birth_year <= 2100:
                raise ValueError(f"fødselsår {birth_year} er ikke realistisk")
        except ValidationError as exc:
            out.errors.append(f"Linje {line}: {_short(exc)}")
            continue
        except ValueError as exc:
            out.errors.append(f"Linje {line}: {exc}")
            continue
        who = lifter_id or entry.lifter_vlstat_id or entry.lifter_name.lower()
        key = (who, entry.weight_class)
        if key in seen:
            out.errors.append(
                f"Linje {line}: {entry.lifter_name} står to gange i samme vægtklasse "
                f"(også linje {seen[key]})"
            )
            continue
        seen[key] = line
        out.rows.append(
            ManualRow(line=line, entry=entry, birth_year=birth_year, lifter_id=lifter_id)
        )
    if not out.rows and not out.errors:
        out.errors.append("Der er ingen løftere at gemme.")
    return out


def parse_csv(text: str) -> ParsedUpload:
    text = text.lstrip("﻿").strip()
    if not text:
        return ParsedUpload(errors=["Filen er tom."])
    first_line = text.splitlines()[0]
    delimiter = ";" if first_line.count(";") >= first_line.count(",") else ","
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    header = [h.strip().lower() for h in next(reader)]
    unknown = [h for h in header if h and h not in COLUMNS]
    missing = REQUIRED - set(header)
    if unknown or missing:
        problems = []
        if missing:
            problems.append(f"mangler kolonnen {', '.join(sorted(missing))}")
        if unknown:
            problems.append(f"ukendte kolonner: {', '.join(unknown)}")
        return ParsedUpload(
            errors=[f"Overskriftslinjen {'; '.join(problems)}. Brug: {'; '.join(CSV_COLUMNS)}"]
        )
    rows = []
    for line, values in enumerate(reader, start=2):
        rows.append(
            (line, {col: (values[i] if i < len(values) else "") for i, col in enumerate(header)})
        )
    return parse_rows(rows)


def to_csv(rows: list[dict[str, str]]) -> str:
    """Form rows -> CSV text (semicolon), so the preview step can resubmit one format."""
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";", lineterminator="\n")
    writer.writerow(COLUMNS)
    for r in rows:
        if any((r.get(c) or "").strip() for c in COLUMNS):
            writer.writerow([(r.get(c) or "").strip() for c in COLUMNS])
    return buf.getvalue()
