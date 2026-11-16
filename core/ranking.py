"""Where a total would place among Denmark's active lifters in a weight class.

Used by the point calculator: the page carries the totals from class_totals(), and
app/static/js/points.js mirrors place_among() and top_percent() (tests/test_points_js.py)."""

import math
from collections.abc import Iterable, Sequence

from core.qualification import dm_class_label

FOREIGN_AREA = "Udland"  # vl.v_lifter_data.area for foreign guest clubs


def class_totals(rows: Iterable[dict]) -> dict[str, dict[str, list[int]]]:
    """Best totals per gender and DVF class, highest first: {"M": {"-85": [301, 288, ...]}}.

    `rows` come from vl.v_lifter_data. Only active lifters (a competition within the last
    year) from Danish clubs count, each in the class of their latest weigh-in, with their
    best total since 2019. The same lifters the data page lists for that class."""
    out: dict[str, dict[str, list[int]]] = {}
    for r in rows:
        label = dm_class_label(r["gender"], r["latest_bodyweight"])
        if label is None or r["pr_total"] is None:
            continue
        if not r["is_active"] or r["area"] == FOREIGN_AREA:
            continue
        out.setdefault(r["gender"], {}).setdefault(label, []).append(int(r["pr_total"]))
    for classes in out.values():
        for totals in classes.values():
            totals.sort(reverse=True)
    return out


def place_among(totals: Sequence[float], total: float) -> int:
    """The place `total` would take: 1 + the number of strictly better totals. A tie
    shares the better place."""
    return 1 + sum(1 for t in totals if t > total)


def top_percent(place: int, others: int) -> int:
    """ "Top N %" for a place in a field of `others` lifters plus yourself, rounded up so it
    never flatters: place 1 of 86 is top 2 %, last place is top 100 %."""
    return math.ceil(100 * place / (others + 1))
