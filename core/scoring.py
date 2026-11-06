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


@dataclass(frozen=True)
class QPointsCoefficient:
    """Q-points (Huebner, Meltzer, Bjarnason, Perperoglou, Med Sci Sports Exerc 2023):
    total * scale / (b0 + b1 * B**-2 + b2 * B**2) with B = bodyweight / 100.
    min_bodyweight: lighter lifters are scored at this weight (Nordic Weightlifting
    Federation congress, 15 Nov 2025), because the B**-2 term overrates light lifters."""

    scale: float
    b0: float
    b1: float
    b2: float
    min_bodyweight: float


# Fixed by the published model (osf.io/8x3nb, qpoints_Excelformula.txt), not per period
# like Sinclair. Checked against vlstat's Q-points page: woman, 66.00 kg, 137 kg -> 182.61.
Q_POINTS: dict[Gender, QPointsCoefficient] = {
    Gender.MALE: QPointsCoefficient(463.26, 416.7, -47.87, 18.93, 50.0),
    Gender.FEMALE: QPointsCoefficient(306.54, 266.5, -19.44, 18.61, 41.0),
}


def q_points_factor(bodyweight: float, coefficient: QPointsCoefficient) -> float:
    c = coefficient
    b = max(bodyweight, c.min_bodyweight) / 100
    return c.scale / (c.b0 + c.b1 * b**-2 + c.b2 * b**2)


def q_points(
    lifted_total: int | None, bodyweight: float | None, gender: Gender | None
) -> float | None:
    if lifted_total is None or bodyweight is None or gender is None:
        return None
    return lifted_total * q_points_factor(bodyweight, Q_POINTS[gender])
