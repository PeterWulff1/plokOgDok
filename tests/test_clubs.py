import pytest

from core.clubs import club_slug, find_club, match_clubs


@pytest.mark.parametrize(
    ("name", "slug"),
    [
        ("AK Jyden", "ak-jyden"),
        ("Århus Atlet Klub", "aarhus-atlet-klub"),
        ("Bagsværd VK", "bagsvaerd-vk"),
        ("HG Vægtløftning/Styrkeløft", "hg-vaegtloeftning-styrkeloeft"),
        ("VK 49", "vk-49"),
        ("Olofströms FK", "olofstroms-fk"),
        ("  Gladsaxe Crossfit ", "gladsaxe-crossfit"),
    ],
)
def test_club_slug(name, slug):
    assert club_slug(name) == slug


@pytest.mark.parametrize("name", [None, "", "Andre", "ingen klub", "---"])
def test_no_slug_for_missing_or_placeholder_clubs(name):
    assert club_slug(name) is None


def test_find_club():
    names = ["AK Jyden", "Århus Atlet Klub"]
    assert find_club(names, "aarhus-atlet-klub") == "Århus Atlet Klub"
    assert find_club(names, "ak-viking") is None


CLUBS = [
    {"club": "Århus Atlet Klub"},
    {"club": "AK Jyden"},
    {"club": "Århus Crossfit Vægtløftning"},
    {"club": "Sportshøjskolen"},
]


def test_match_clubs_ignores_case_and_danish_spelling():
    assert [c["club"] for c in match_clubs(CLUBS, "aarhus")] == [
        "Århus Atlet Klub", "Århus Crossfit Vægtløftning"]  # fmt: skip
    assert [c["club"] for c in match_clubs(CLUBS, "ÅRH")] == [
        "Århus Atlet Klub", "Århus Crossfit Vægtløftning"]  # fmt: skip
    assert [c["club"] for c in match_clubs(CLUBS, "højskol")] == ["Sportshøjskolen"]


def test_match_clubs_prefix_first_and_limit():
    assert [c["club"] for c in match_clubs(CLUBS, "ak")][0] == "AK Jyden"
    assert len(match_clubs(CLUBS, "a", limit=4)) == 0  # too short
    assert len(match_clubs(CLUBS, "us", limit=1)) == 1
