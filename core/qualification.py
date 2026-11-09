"""DM Senior qualifying totals, as Dansk Vægtløftnings-Forbund publishes them on
vaegtloeftning.dk/kvalifikation-og-tilmelding (read 2026-11-09).

The site shows these classes, on the data page and in the point calculator. They differ
from the IWF 2025 classes in vl.weight_class_2025. See docs/decisions.md."""

from dataclasses import dataclass
from decimal import Decimal

from core.models import Gender


@dataclass(frozen=True)
class DmClass:
    label: str
    ceiling: int | None  # None for the open class above the top limit
    qualifying_total: int


def _classes(limits: list[tuple[int, int]], open_total: int) -> tuple[DmClass, ...]:
    """Build a gender's classes from (ceiling, total) pairs, lightest first."""
    closed = [DmClass(f"-{ceiling}", ceiling, total) for ceiling, total in limits]
    return (*closed, DmClass(f"+{limits[-1][0]}", None, open_total))


DM_SENIOR_CLASSES: dict[Gender, tuple[DmClass, ...]] = {
    Gender.MALE: _classes(
        [(60, 132), (65, 160), (70, 178), (75, 190), (85, 217), (95, 233), (110, 250)],
        open_total=230,
    ),
    Gender.FEMALE: _classes(
        [(49, 98), (53, 114), (57, 128), (61, 135), (69, 157), (77, 164), (86, 155)],
        open_total=145,
    ),
}


def dm_class(gender: Gender, bodyweight: float) -> DmClass:
    """The class a bodyweight falls in: the lightest whose ceiling it doesn't exceed."""
    return next(
        c for c in DM_SENIOR_CLASSES[gender] if c.ceiling is None or bodyweight <= c.ceiling
    )


def dm_class_label(gender: str | None, bodyweight: Decimal | float | None) -> str | None:
    """The class label for a database row, or None when gender or bodyweight is unknown."""
    if gender is None or bodyweight is None:
        return None
    return dm_class(Gender(gender), float(bodyweight)).label


def dm_missing_kg(cls: DmClass, total: float) -> float:
    """Kilos a total is short of the class's requirement; 0 when it is met."""
    return max(cls.qualifying_total - total, 0)
