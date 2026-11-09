"""DM Senior classes and qualifying totals (core/qualification.py)."""

from decimal import Decimal

import pytest

from core.models import Gender
from core.qualification import DM_SENIOR_CLASSES, dm_class, dm_class_label, dm_missing_kg


@pytest.mark.parametrize(
    ("gender", "bodyweight", "label", "total"),
    [
        (Gender.MALE, 40.0, "-60", 132),
        (Gender.MALE, 60.0, "-60", 132),
        (Gender.MALE, 60.01, "-65", 160),
        (Gender.MALE, 72.0, "-75", 190),
        (Gender.MALE, 110.0, "-110", 250),
        (Gender.MALE, 110.01, "+110", 230),
        (Gender.FEMALE, 49.0, "-49", 98),
        (Gender.FEMALE, 49.01, "-53", 114),
        (Gender.FEMALE, 86.0, "-86", 155),
        (Gender.FEMALE, 86.01, "+86", 145),
    ],
)
def test_dm_class(gender, bodyweight, label, total):
    cls = dm_class(gender, bodyweight)
    assert (cls.label, cls.qualifying_total) == (label, total)


def test_every_gender_has_eight_classes_ending_open():
    for classes in DM_SENIOR_CLASSES.values():
        assert len(classes) == 8
        assert classes[-1].ceiling is None
        assert all(c.ceiling is not None for c in classes[:-1])


def test_dm_class_label_for_database_rows():
    assert dm_class_label("M", Decimal("80.4")) == "-85"
    assert dm_class_label("F", Decimal("86.01")) == "+86"
    assert dm_class_label("M", None) is None
    assert dm_class_label(None, Decimal("80.4")) is None


def test_dm_missing_kg():
    cls = dm_class(Gender.MALE, 72.0)
    assert dm_missing_kg(cls, 178) == 12
    assert dm_missing_kg(cls, 190) == 0
    assert dm_missing_kg(cls, 200) == 0
