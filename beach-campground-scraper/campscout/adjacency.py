"""Deciding whether two campsites are actually next to each other.

Site numbering is *usually* sequential along a loop, so site 82 and 83 are
neighbors. That heuristic breaks in two directions, and both matter here:

  - False positives: consecutive numbers that are not neighbors, because the
    numbering wraps to a new loop, jumps the park road, or has a restroom
    building between them. Handled by `groups` + `breaks`.
  - False negatives: neighbors with non-consecutive numbers (odd/even rows on
    opposite sides of a road). Handled by `extra_pairs`.

When the provider gives us real coordinates we can skip the guessing entirely
and measure distance, which is why `mode: either` is the recommended default.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional

from .geo import haversine_meters
from .models import Site

NUMERIC = "numeric"
GEO = "geo"
EITHER = "either"
VALID_MODES = {NUMERIC, GEO, EITHER}


def parse_number_spec(spec: object) -> set[int]:
    """Parse "1-43,47,49,51" (or a list of those) into a set of ints."""
    if spec is None:
        return set()
    if isinstance(spec, (list, tuple)):
        out: set[int] = set()
        for item in spec:
            out |= parse_number_spec(item)
        return out
    if isinstance(spec, int):
        return {spec}

    numbers: set[int] = set()
    for chunk in str(spec).split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            lo_s, _, hi_s = chunk.partition("-")
            lo, hi = int(lo_s.strip()), int(hi_s.strip())
            if lo > hi:
                lo, hi = hi, lo
            numbers.update(range(lo, hi + 1))
        else:
            numbers.add(int(chunk))
    return numbers


def parse_pair_spec(spec: object) -> frozenset[int]:
    """Parse a two-site spec like "20-21", "47,49", or [47, 49].

    Deliberately NOT `parse_number_spec`: there, "47-49" is the range 47..49,
    but a pair is always exactly two sites, so a dash can only mean "and".
    Reusing the range parser here silently turned "47-49" into three sites.
    """
    if isinstance(spec, (list, tuple)):
        numbers = [int(x) for x in spec]
    else:
        text = str(spec).replace("-", ",")
        numbers = [int(part.strip()) for part in text.split(",") if part.strip()]

    unique = frozenset(numbers)
    if len(unique) != 2:
        raise ValueError(
            f"expected exactly 2 distinct site numbers, got {spec!r} -> {sorted(unique)}"
        )
    return unique


def _pair(a: int, b: int) -> frozenset[int]:
    return frozenset((a, b))


@dataclass
class AdjacencyModel:
    """Configurable notion of "these two sites are next to each other"."""

    mode: str = EITHER
    groups: list[set[int]] = field(default_factory=list)
    breaks: set[frozenset[int]] = field(default_factory=set)
    extra_pairs: set[frozenset[int]] = field(default_factory=set)
    max_meters: float = 40.0

    @classmethod
    def from_config(cls, cfg: Optional[dict]) -> "AdjacencyModel":
        cfg = cfg or {}
        mode = str(cfg.get("mode", EITHER)).lower()
        if mode not in VALID_MODES:
            raise ValueError(f"adjacency mode must be one of {sorted(VALID_MODES)}, got {mode!r}")

        groups = [parse_number_spec(g) for g in cfg.get("groups", []) or []]
        groups = [g for g in groups if g]

        breaks = set()
        for entry in cfg.get("breaks", []) or []:
            try:
                breaks.add(parse_pair_spec(entry))
            except ValueError as exc:
                raise ValueError(f"adjacency break {entry!r} is invalid: {exc}") from exc

        extra = set()
        for entry in cfg.get("extra_pairs", []) or []:
            try:
                extra.add(parse_pair_spec(entry))
            except ValueError as exc:
                raise ValueError(f"adjacency extra_pair {entry!r} is invalid: {exc}") from exc

        return cls(
            mode=mode,
            groups=groups,
            breaks=breaks,
            extra_pairs=extra,
            max_meters=float(cfg.get("max_meters", 40.0)),
        )

    def _same_group(self, a: int, b: int) -> bool:
        """With no groups configured the whole campground is one group."""
        if not self.groups:
            return True
        return any(a in g and b in g for g in self.groups)

    def numeric_adjacent(self, a: Site, b: Site) -> bool:
        if a.number is None or b.number is None:
            return False
        if abs(a.number - b.number) != 1:
            return False
        if _pair(a.number, b.number) in self.breaks:
            return False
        return self._same_group(a.number, b.number)

    def geo_adjacent(self, a: Site, b: Site) -> bool:
        if not (a.has_coords and b.has_coords):
            return False
        return haversine_meters(a.lat, a.lon, b.lat, b.lon) <= self.max_meters

    def are_adjacent(self, a: Site, b: Site) -> bool:
        if a.unit_id == b.unit_id:
            return False
        if a.number is not None and b.number is not None:
            if _pair(a.number, b.number) in self.extra_pairs:
                return True
        if self.mode == NUMERIC:
            return self.numeric_adjacent(a, b)
        if self.mode == GEO:
            return self.geo_adjacent(a, b)
        return self.numeric_adjacent(a, b) or self.geo_adjacent(a, b)

    def pairs(self, sites: Iterable[Site]) -> list[tuple[Site, Site]]:
        """Every adjacent pair among `sites`, each unordered pair once."""
        ordered = sorted(sites, key=lambda s: (s.number if s.number is not None else 10**9, s.unit_id))
        found: list[tuple[Site, Site]] = []
        for i, a in enumerate(ordered):
            for b in ordered[i + 1 :]:
                if self.are_adjacent(a, b):
                    found.append((a, b))
        return found
