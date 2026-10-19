"""Totals and Sinclair points. Must match db/migrations/003_entry_result_view.sql."""

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from core.models import Attempt, Discipline, Gender


@dataclass(frozen=True)
class SinclairCoefficient:
    gender: Gender
    a: float
    b: float
    valid_from_year: int
    valid_to_year: int


def best_lift(attempts: Iterable[Attempt], discipline: Discipline) -> int | None:
    made = [a.weight_kg for a in attempts if a.discipline == discipline and a.is_successful]
    return max(made) if made else None


def total(attempts: Sequence[Attempt]) -> int | None:
    """Best snatch + best C&J. None if either discipline has no made lift."""
    snatch = best_lift(attempts, Discipline.SNATCH)
    cj = best_lift(attempts, Discipline.CLEAN_AND_JERK)
    if snatch is None or cj is None:
        return None
    return snatch + cj


def find_coefficient(
    coefficients: Iterable[SinclairCoefficient], gender: Gender, year: int
) -> SinclairCoefficient | None:
    for c in coefficients:
        if c.gender == gender and c.valid_from_year <= year <= c.valid_to_year:
            return c
    return None


def sinclair_factor(bodyweight: float, coefficient: SinclairCoefficient) -> float:
    if bodyweight >= coefficient.b:
        return 1.0
    return 10 ** (coefficient.a * math.log10(bodyweight / coefficient.b) ** 2)


def sinclair_points(
    lifted_total: int | None, bodyweight: float | None, coefficient: SinclairCoefficient | None
) -> float | None:
    if lifted_total is None or bodyweight is None or coefficient is None:
        return None
    return lifted_total * sinclair_factor(bodyweight, coefficient)
