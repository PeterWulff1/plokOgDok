"""Weight class order on competition pages (core/weight_classes.py, db.queries)."""

from core.weight_classes import weight_class_sort_key
from db import queries


def _sorted(labels):
    return sorted(labels, key=weight_class_sort_key)


def test_classes_sort_by_weight_not_text():
    labels = ["-110kg", "+110kg", "-70kg", "-95kg", "-85kg", "-60kg"]
    assert _sorted(labels) == ["-60kg", "-70kg", "-85kg", "-95kg", "-110kg", "+110kg"]


def test_open_class_follows_its_number_and_spaces_are_ignored():
    labels = ["+86kg", "-86kg", "-49 kg", "-53kg", "+87kg"]
    assert _sorted(labels) == ["-49 kg", "-53kg", "-86kg", "+86kg", "+87kg"]


def test_prefix_groups_then_weight():
    labels = ["45-49år -81kg", "35-39år -102kg", "-109kg", "35-39år -71kg", "45-49år +109kg"]
    assert _sorted(labels) == [
        "-109kg",
        "35-39år -71kg",
        "35-39år -102kg",
        "45-49år -81kg",
        "45-49år +109kg",
    ]


def test_ranges_sort_by_upper_limit_without_prefix():
    labels = ["96 - 102kg", "71 - 81kg", "55 - 59kg", "-64kg"]
    assert _sorted(labels) == ["55 - 59kg", "-64kg", "71 - 81kg", "96 - 102kg"]


def test_no_class_first_and_unknown_labels_last():
    labels = ["udenfor konkurrence", "-81kg", None]
    assert _sorted(labels) == [None, "-81kg", "udenfor konkurrence"]


def test_competition_results_orders_groups_by_weight(monkeypatch):
    # SQL returns classes in text order, as Postgres does.
    rows = [
        {"entry_id": i, "gender": g, "weight_class": wc}
        for i, (g, wc) in enumerate(
            [("F", "+86kg"), ("F", "-49kg"), ("M", "-110kg"), ("M", "-110kg"),
             ("M", "+110kg"), ("M", "-70kg"), ("M", "-95kg")]
        )
    ]  # fmt: skip
    monkeypatch.setattr(queries, "_all", lambda sql, params=(): [dict(r) for r in rows])
    monkeypatch.setattr(queries, "_attempt_slots", lambda ids: {i: {} for i in ids})
    groups = queries.competition_results(1)
    assert [(g["gender"], g["weight_class"]) for g in groups] == [
        ("F", "-49kg"),
        ("F", "+86kg"),
        ("M", "-70kg"),
        ("M", "-95kg"),
        ("M", "-110kg"),
        ("M", "+110kg"),
    ]
    assert len(groups[4]["entries"]) == 2
