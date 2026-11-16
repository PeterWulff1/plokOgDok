"""Class ranking for the point calculator (core/ranking.py)."""

from decimal import Decimal

from core.ranking import class_totals, place_among, top_percent


def _row(**over):
    row = {"gender": "M", "latest_bodyweight": Decimal("84.20"), "pr_total": 250,
           "is_active": True, "area": "Jylland"}  # fmt: skip
    return {**row, **over}


def test_class_totals_counts_active_danish_lifters_with_a_total():
    rows = [
        _row(pr_total=250),
        _row(pr_total=288, area=None),  # club without a region still counts
        _row(pr_total=300, is_active=False),
        _row(pr_total=310, area="Udland"),
        _row(pr_total=None),
        _row(pr_total=240, latest_bodyweight=None),
        _row(pr_total=200, latest_bodyweight=Decimal("60.00")),
        _row(pr_total=150, gender="F", latest_bodyweight=Decimal("60.00")),
    ]
    assert class_totals(rows) == {"M": {"-85": [288, 250], "-60": [200]}, "F": {"-61": [150]}}


def test_place_among_shares_the_better_place_on_a_tie():
    totals = [300, 288, 288, 250]
    assert place_among(totals, 301) == 1
    assert place_among(totals, 288) == 2
    assert place_among(totals, 260) == 4
    assert place_among(totals, 100) == 5
    assert place_among([], 100) == 1


def test_top_percent_rounds_up():
    assert top_percent(1, 85) == 2
    assert top_percent(12, 85) == 14
    assert top_percent(86, 85) == 100
    assert top_percent(1, 0) == 100
