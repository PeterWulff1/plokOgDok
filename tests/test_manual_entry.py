from decimal import Decimal

import pytest

from core.manual_entry import COLUMNS, parse_attempt, parse_csv, parse_rows, to_csv
from core.models import Discipline, Gender

HEADER = ";".join(COLUMNS)


@pytest.mark.parametrize(
    ("text", "expected"),
    [("95", (95, True)), ("95x", (95, False)), ("95X", (95, False)), ("-95", (95, False)),
     (" 102 ", (102, True)), ("", None), ("0", None)],
)  # fmt: skip
def test_parse_attempt(text, expected):
    assert parse_attempt(text) == expected


@pytest.mark.parametrize("text", ["abc", "95.5", "-95x", "1000"])
def test_parse_attempt_rejects_junk(text):
    with pytest.raises(ValueError):
        parse_attempt(text)


def test_parse_csv_semicolon_with_decimal_comma():
    text = HEADER + "\nMette Eksempel;;K;1998;AK Eksempel;-64kg;63,4;70;73x;;88;-92;92\n"
    result = parse_csv(text)
    assert result.ok, result.errors
    row = result.rows[0]
    e = row.entry
    assert (e.lifter_name, e.gender, e.weight_class, e.club) == (
        "Mette Eksempel",
        Gender.FEMALE,
        "-64kg",
        "AK Eksempel",
    )
    assert e.bodyweight == Decimal("63.4")
    assert row.birth_year == 1998
    assert e.lifter_vlstat_id is None
    snatch = [(a.attempt_number, a.weight_kg, a.is_successful)
              for a in e.attempts if a.discipline == Discipline.SNATCH]  # fmt: skip
    assert snatch == [(1, 70, True), (2, 73, False)]  # blank 3rd attempt -> no row


def test_parse_csv_comma_separated_and_bom():
    text = "﻿" + ",".join(["navn", "køn", "s1"]) + "\nOle,M,120\n"
    result = parse_csv(text)
    assert result.ok, result.errors
    assert result.rows[0].entry.attempts[0].weight_kg == 120


def test_unknown_columns_are_reported():
    result = parse_csv("navn;vægt i kg\nOle;80\n")
    assert not result.ok
    assert "ukendte kolonner" in result.errors[0]


def test_row_errors_name_the_line():
    text = HEADER + "\nOle;;X;;;;;;;;;;\nMia;;K;;;;abc;;;;;;\n"
    result = parse_csv(text)
    assert any(e.startswith("Linje 2:") and "køn" in e for e in result.errors)
    assert any(e.startswith("Linje 3:") and "kropsvægt" in e for e in result.errors)


def test_duplicate_lifter_in_same_class_is_an_error():
    rows = [
        (2, {"navn": "Ole", "vægtklasse": "-81kg"}),
        (3, {"navn": "ole", "vægtklasse": "-81kg"}),
    ]
    result = parse_rows(rows)
    assert len(result.rows) == 1
    assert "to gange" in result.errors[0]


def test_blank_rows_skipped_and_empty_upload_rejected():
    assert parse_rows([(2, dict.fromkeys(COLUMNS, ""))]).errors == [
        "Der er ingen løftere at gemme."
    ]


def test_to_csv_roundtrip_drops_blank_rows():
    rows = [dict.fromkeys(COLUMNS, ""), {**dict.fromkeys(COLUMNS, ""), "navn": "Ole", "køn": "M"}]
    result = parse_csv(to_csv(rows))
    assert result.ok and [r.entry.lifter_name for r in result.rows] == ["Ole"]


def test_lifter_id_from_autocomplete_is_kept():
    rows = [(2, {"navn": "Ole", "lifter_id": "17", "t1": "100"})]
    result = parse_rows(rows)
    assert result.ok and result.rows[0].lifter_id == 17
    assert parse_rows([(2, {"navn": "Ole", "køn": "M"})]).rows[0].lifter_id is None


def test_lifter_id_must_be_a_number():
    result = parse_rows([(2, {"navn": "Ole", "lifter_id": "abc"})])
    assert result.errors and "lifter_id" in result.errors[0]


def test_same_lifter_id_twice_in_a_class_is_an_error():
    row = {"navn": "Ole", "lifter_id": "17", "vægtklasse": "-81kg"}
    result = parse_rows([(2, row), (3, {**row, "navn": "Ole H."})])
    assert len(result.rows) == 1 and "også linje 2" in result.errors[0]


def test_to_csv_keeps_lifter_id_for_the_save_step():
    rows = [{**dict.fromkeys(COLUMNS, ""), "navn": "Ole", "lifter_id": "17"}]
    assert parse_csv(to_csv(rows)).rows[0].lifter_id == 17
