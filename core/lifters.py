"""Rules for combining a lifter's per-competition data into one lifter record."""

from collections import Counter
from collections.abc import Iterable

from core.models import Gender


def derive_birth_year(year_age_pairs: Iterable[tuple[int, int]]) -> int | None:
    """Birth year from (competition year, age shown at that competition) pairs.

    If vlstat's age is "calendar year - birth year", every pair gives the same value.
    If it's the exact age on the day, values differ by one, and the smaller is correct.
    A spread of more than one year means bad data, so we return None.
    """
    candidates = {year - age for year, age in year_age_pairs}
    if not candidates or max(candidates) - min(candidates) > 1:
        return None
    return min(candidates)


def resolve_gender(genders: Iterable[Gender | None]) -> Gender | None:
    """The only gender seen, or None if there's none or they conflict."""
    seen = Counter(g for g in genders if g is not None)
    return next(iter(seen)) if len(seen) == 1 else None
