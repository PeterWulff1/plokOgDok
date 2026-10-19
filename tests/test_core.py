import pytest
from pydantic import ValidationError

from core.lifters import derive_birth_year, resolve_gender
from core.models import Attempt, Discipline, Entry, Gender
from core.scoring import (
    SinclairCoefficient,
    best_lift,
    find_coefficient,
    sinclair_points,
    total,
)

S, CJ = Discipline.SNATCH, Discipline.CLEAN_AND_JERK

# Test data only: the real coefficients live in the database (vl.sinclair_coefficient).
MEN_2017 = SinclairCoefficient(Gender.MALE, 0.751945030, 175.508, 2017, 2020)
MEN_2021 = SinclairCoefficient(Gender.MALE, 0.722762521, 193.609, 2021, 2024)


def att(discipline, number, weight, ok):
    return Attempt(discipline=discipline, attempt_number=number, weight_kg=weight, is_successful=ok)


MARTIN = [att(S, 1, 85, False), att(S, 2, 85, True), att(S, 3, 90, False),
          att(CJ, 1, 110, True), att(CJ, 2, 115, False)]  # fmt: skip


def test_best_lift_ignores_misses():
    assert best_lift(MARTIN, S) == 85
    assert best_lift(MARTIN, CJ) == 110


def test_total():
    assert total(MARTIN) == 195


def test_no_total_without_made_lift_in_both():
    assert total([att(S, 1, 80, True), att(CJ, 1, 100, False)]) is None
    assert total([]) is None


def test_sinclair_matches_vlstat():
    # Martin Aksel Jensen, AK Atlas nytårscup 2019: vlstat shows 201,81.
    assert sinclair_points(195, 126.90, MEN_2017) == pytest.approx(201.81, abs=0.01)


def test_sinclair_above_b_is_total():
    assert sinclair_points(400, 200.0, MEN_2017) == 400


def test_sinclair_missing_input():
    assert sinclair_points(None, 80.0, MEN_2017) is None
    assert sinclair_points(200, None, MEN_2017) is None
    assert sinclair_points(200, 80.0, None) is None


def test_find_coefficient_by_year():
    coeffs = [MEN_2017, MEN_2021]
    assert find_coefficient(coeffs, Gender.MALE, 2019) is MEN_2017
    assert find_coefficient(coeffs, Gender.MALE, 2021) is MEN_2021
    assert find_coefficient(coeffs, Gender.FEMALE, 2021) is None
    assert find_coefficient(coeffs, Gender.MALE, 2026) is None


def test_entry_rejects_duplicate_attempt_slot():
    with pytest.raises(ValidationError):
        Entry(lifter_vlstat_id=1, lifter_name="X", gender=None, weight_class="-81kg",
              attempts=(att(S, 1, 80, True), att(S, 1, 82, False)))  # fmt: skip


def test_attempt_rejects_zero_weight():
    with pytest.raises(ValidationError):
        att(S, 1, 0, False)


@pytest.mark.parametrize(
    ("pairs", "expected"),
    [
        ([(2026, 23), (2025, 22)], 2003),  # calendar-year age: consistent
        ([(2026, 23), (2026, 22)], 2003),  # exact age, birthday mid-year: smaller is right
        ([(2026, 23)], 2003),
        ([(2026, 23), (2020, 10)], None),  # spread > 1 year: bad data
        ([], None),
    ],
)
def test_derive_birth_year(pairs, expected):
    assert derive_birth_year(pairs) == expected


def test_resolve_gender():
    assert resolve_gender([Gender.FEMALE, None, Gender.FEMALE]) == Gender.FEMALE
    assert resolve_gender([Gender.FEMALE, Gender.MALE]) is None
    assert resolve_gender([None]) is None
