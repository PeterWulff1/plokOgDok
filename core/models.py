"""Shared Pydantic models. The single definition of a lifter, competition, entry and attempt.

Reuse these everywhere (scraper, seed, admin page). Don't create parallel models.
"""

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Gender(StrEnum):
    MALE = "M"
    FEMALE = "F"


class Discipline(StrEnum):
    SNATCH = "snatch"
    CLEAN_AND_JERK = "cj"


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Attempt(_Frozen):
    discipline: Discipline
    attempt_number: int = Field(ge=1, le=3)
    weight_kg: int = Field(gt=0, lt=400)
    is_successful: bool


class Lifter(_Frozen):
    vlstat_id: int | None = None
    name: str = Field(min_length=1)
    gender: Gender | None = None
    birth_year: int | None = Field(default=None, ge=1900, le=2100)


class Competition(_Frozen):
    vlstat_id: int | None = None
    name: str = Field(min_length=1)
    date: date
    location: str | None = None


class Entry(_Frozen):
    """One lifter's result at one competition, as stated by the source."""

    # None for lifters added through the admin page without a vlstat profile.
    lifter_vlstat_id: int | None = None
    lifter_name: str = Field(min_length=1)
    gender: Gender | None
    # None when the competition groups lifters by gender only (e.g. CWC).
    weight_class: str | None = Field(default=None, min_length=1)
    bodyweight: Decimal | None = Field(default=None, gt=0, lt=400, decimal_places=2)
    club: str | None = None
    reported_age: int | None = Field(default=None, ge=5, le=110)
    # The total the source displays (vlstat: 0 = no total). Used only to detect bad data.
    reported_total: int | None = Field(default=None, ge=0, lt=1000)
    attempts: tuple[Attempt, ...] = ()

    @model_validator(mode="after")
    def _unique_attempt_slots(self) -> "Entry":
        slots = [(a.discipline, a.attempt_number) for a in self.attempts]
        if len(slots) != len(set(slots)):
            raise ValueError("duplicate attempt slot (discipline, attempt_number)")
        return self


class CalendarEvent(_Frozen):
    """One event from the federation's calendar (vaegtloeftning.dk/kalender)."""

    source_id: int = Field(gt=0)
    title: str = Field(min_length=1)
    # Danish local time, as the source gives it (naive).
    starts_at: datetime
    ends_at: datetime
    all_day: bool
    venue: str | None = None
    city: str | None = None
    country: str | None = None
    url: str = Field(pattern=r"^https://vaegtloeftning\.dk/")
    source_modified: datetime

    @model_validator(mode="after")
    def _ends_after_start(self) -> "CalendarEvent":
        if self.ends_at < self.starts_at:
            raise ValueError("event ends before it starts")
        return self
