"""Club identity. A club is the raw `entry.club` text; its URL slug is derived here."""

import re
import unicodedata
from collections.abc import Iterable

# vlstat placeholders that aren't clubs and get no page (mirrored in migration 014).
PLACEHOLDER_CLUBS = frozenset({"Andre", "ingen klub"})

_DANISH = str.maketrans({"æ": "ae", "ø": "oe", "å": "aa"})


def _fold(text: str) -> str:
    """Lowercase ASCII with words joined by "-": "Århus Atlet Klub" -> "aarhus-atlet-klub"."""
    text = unicodedata.normalize("NFKD", text.strip().lower().translate(_DANISH))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def club_slug(name: str | None) -> str | None:
    """URL slug for a club name, e.g. "Århus Atlet Klub" -> "aarhus-atlet-klub".

    None for a missing name or a placeholder, so callers know not to link it.
    """
    if not name or name.strip() in PLACEHOLDER_CLUBS:
        return None
    return _fold(name) or None


def find_club(names: Iterable[str], slug: str) -> str | None:
    """The club name whose slug is `slug`, or None."""
    return next((n for n in names if club_slug(n) == slug), None)


def match_clubs(clubs: Iterable[dict], query: str, limit: int = 4) -> list[dict]:
    """Clubs (rows with a "club" key) whose name contains `query`, ignoring case and
    Danish spelling ("aarhus" finds "Århus"). Prefix matches first; otherwise input order."""
    q = _fold(query)
    if len(q) < 2:
        return []
    hits = [c for c in clubs if q in _fold(c["club"])]
    hits.sort(key=lambda c: not _fold(c["club"]).startswith(q))
    return hits[:limit]
