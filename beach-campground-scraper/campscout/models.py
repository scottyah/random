"""Core value types shared across the scraper."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterator, Optional

_LEADING_NUM = re.compile(r"(\d+)")


def parse_site_number(name: str) -> Optional[int]:
    """Pull the numeric part out of a site name.

    ReserveCalifornia names sites inconsistently across parks: "082", "Site 82",
    "Campsite 82", "82A". We only need the integer for numeric adjacency.
    """
    if not name:
        return None
    match = _LEADING_NUM.search(name)
    return int(match.group(1)) if match else None


@dataclass(frozen=True)
class Site:
    """A single reservable campsite ("unit" in UseDirect's vocabulary)."""

    facility_id: str
    unit_id: str
    name: str
    number: Optional[int] = None
    loop: Optional[str] = None
    is_ada: bool = False
    vehicle_length: int = 0
    lat: Optional[float] = None
    lon: Optional[float] = None
    web_bookable: bool = True
    unit_type_id: Optional[int] = None

    @property
    def label(self) -> str:
        return self.name or f"unit {self.unit_id}"

    @property
    def has_coords(self) -> bool:
        return self.lat is not None and self.lon is not None


@dataclass(frozen=True)
class Stay:
    """A concrete check-in date plus a length, i.e. one thing you could book."""

    checkin: date
    nights: int
    label: str = ""

    @property
    def checkout(self) -> date:
        return self.checkin + timedelta(days=self.nights)

    def occupied_nights(self) -> list[date]:
        """The nights that must be free for this stay to be bookable."""
        return [self.checkin + timedelta(days=i) for i in range(self.nights)]

    def __str__(self) -> str:  # pragma: no cover - display only
        base = f"{self.checkin:%a %b %d} → {self.checkout:%a %b %d} ({self.nights}n)"
        return f"{base} [{self.label}]" if self.label else base


@dataclass(frozen=True)
class PairHit:
    """Two adjacent, desirable, simultaneously-available sites."""

    campground_key: str
    campground_name: str
    stay: Stay
    site_a: Site
    site_b: Site
    score_a: int
    score_b: int
    reason_a: str
    reason_b: str
    booking_url: str = ""

    @property
    def min_score(self) -> int:
        return min(self.score_a, self.score_b)

    @property
    def dedupe_key(self) -> str:
        """Stable identity so we don't re-alert on the same find every poll."""
        lo, hi = sorted([self.site_a.unit_id, self.site_b.unit_id])
        return f"{self.campground_key}|{self.stay.checkin:%Y-%m-%d}|{self.stay.nights}|{lo}|{hi}"

    def describe(self) -> str:
        return (
            f"{self.campground_name}: sites {self.site_a.label} + {self.site_b.label} "
            f"({self.stay}) score {self.min_score}"
        )


def daterange(start: date, end: date) -> Iterator[date]:
    """Yield every date in [start, end)."""
    cur = start
    while cur < end:
        yield cur
        cur += timedelta(days=1)
