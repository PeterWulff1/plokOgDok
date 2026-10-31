from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from core.models import Discipline, Gender
from scraper.parse_and_seed import load_dataset
from scraper.parse_results import (
    PageFormatError,
    parse_competition_label,
    parse_option_date,
    parse_results_page,
    strip_state_fields,
)

FIXTURE = (Path(__file__).parent / "fixtures" / "results_sample.html").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def parsed():
    result = parse_results_page(FIXTURE)
    return {row.entry.lifter_name: row for row in result.rows}, result.errors


def test_parses_all_lifters_without_errors(parsed):
    rows, errors = parsed
    assert errors == []
    assert set(rows) == {"Martin Aksel Jensen", "Ikke Mødt", "Siff Wibling", "Uden Flag"}


def test_entry_fields(parsed):
    e = parsed[0]["Martin Aksel Jensen"].entry
    assert e.lifter_vlstat_id == 3966
    assert e.gender == Gender.MALE
    assert e.weight_class == "+109kg"
    assert e.bodyweight == Decimal("126.90")
    assert e.club == "Århus Atlet Klub"
    assert e.reported_age == 33


def test_gender_comes_from_class_header(parsed):
    assert parsed[0]["Siff Wibling"].entry.gender == Gender.FEMALE
    assert parsed[0]["Siff Wibling"].entry.weight_class == "-61kg"


def test_attempts_and_flags(parsed):
    attempts = parsed[0]["Martin Aksel Jensen"].entry.attempts
    snatch = [(a.attempt_number, a.weight_kg, a.is_successful)
              for a in attempts if a.discipline == Discipline.SNATCH]  # fmt: skip
    assert snatch == [(1, 85, False), (2, 85, True), (3, 90, False)]


def test_zero_weight_attempt_gets_no_row(parsed):
    cj = [a for a in parsed[0]["Martin Aksel Jensen"].entry.attempts
          if a.discipline == Discipline.CLEAN_AND_JERK]  # fmt: skip
    assert [a.attempt_number for a in cj] == [1, 2]


def test_did_not_lift_entry_has_no_attempts(parsed):
    e = parsed[0]["Ikke Mødt"].entry
    assert e.attempts == ()
    assert e.reported_age is None
    assert e.bodyweight is None


def test_missing_flag_falls_back_to_red_colour(parsed):
    snatch = [a.is_successful for a in parsed[0]["Uden Flag"].entry.attempts
              if a.discipline == Discipline.SNATCH]  # fmt: skip
    assert snatch == [True, False, True]


def test_source_scores_kept_for_validation(parsed):
    src = parsed[0]["Martin Aksel Jensen"].source
    assert src.total == 195
    assert src.points == Decimal("201.81")
    assert src.points_kind == "sinclair"


@pytest.mark.parametrize(
    ("header", "kind"), [("Masters-sinclair", "masters"), ("Q-points", "qpoints")]
)
def test_other_points_headers_accepted(header, kind):
    result = parse_results_page(FIXTURE.replace(">Sinclair<", f">{header}<"))
    assert result.errors == []
    assert {row.source.points_kind for row in result.rows} == {kind}


def test_impossible_age_becomes_unknown_but_entry_is_kept():
    html = FIXTURE.replace('<td class="col-age">33</td>', '<td class="col-age">2</td>')
    result = parse_results_page(html)
    martin = next(r.entry for r in result.rows if r.entry.lifter_vlstat_id == 3966)
    assert martin.reported_age is None
    assert len(result.errors) == 1


def test_gender_only_class_header():
    html = FIXTURE.replace("+109kg  Mænd", "Mænd")
    rows = {r.entry.lifter_name: r.entry for r in parse_results_page(html).rows}
    assert rows["Martin Aksel Jensen"].weight_class is None
    assert rows["Martin Aksel Jensen"].gender == Gender.MALE
    assert rows["Siff Wibling"].weight_class == "-61kg"


def test_unexpected_headers_raise():
    broken = FIXTURE.replace(">Sinclair<", ">Points<")
    with pytest.raises(PageFormatError):
        parse_results_page(broken)


def test_page_without_table_reports_error():
    assert parse_results_page("<html><body></body></html>").errors == ["no results table"]


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("12okt2026 - U23 EM 2026", (date(2026, 10, 12), "U23 EM 2026")),
        ("28dec2019 -  AK Atlas nytårscup 2919", (date(2019, 12, 28), "AK Atlas nytårscup 2919")),
        ("23maj2026 - XL cup ungdom 2026", (date(2026, 5, 23), "XL cup ungdom 2026")),
        ("3jan2026 - Ladies open - senior", (date(2026, 1, 3), "Ladies open - senior")),
    ],
)
def test_competition_label(label, expected):
    assert parse_competition_label(label) == expected


def test_bad_label_raises():
    with pytest.raises(PageFormatError):
        parse_competition_label("Ladies open 2026")


def test_strip_state_fields():
    html = '<input type="hidden" name="__VIEWSTATE" id="__VIEWSTATE" value="abc/+=" />'
    assert strip_state_fields(html) == (
        '<input type="hidden" name="__VIEWSTATE" id="__VIEWSTATE" value="" />'
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [("24-okt", date(2026, 10, 24)), ("03-jan", date(2026, 1, 3)), ("3-Maj", date(2026, 5, 3))],
)
def test_option_date(text, expected):
    assert parse_option_date(text, 2026) == expected


@pytest.mark.parametrize("text", ["", "24okt", "24-xyz", "Øst junior 2026"])
def test_bad_option_date_raises(text):
    with pytest.raises(PageFormatError):
        parse_option_date(text, 2026)


def test_index_in_both_formats(tmp_path):
    """Old index.json labels carry the date; newer ones keep it in a separate field."""
    year = tmp_path / "2026"
    year.mkdir()
    for page in ("100", "101"):
        (year / f"{page}.html").write_text(FIXTURE, encoding="utf-8")
    (year / "index.json").write_text(
        '[{"id": "100", "label": "12okt2026 -  U23 EM 2026"},'
        ' {"id": "101", "label": "Øst  junior 2026", "date": "24-okt"}]',
        encoding="utf-8",
    )
    comps = {c.vlstat_id: (c.date, c.name) for c, _ in load_dataset(tmp_path).competitions}
    assert comps == {100: (date(2026, 10, 12), "U23 EM 2026"),
                     101: (date(2026, 10, 24), "Øst junior 2026")}  # fmt: skip
