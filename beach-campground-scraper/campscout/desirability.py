"""Scoring which sites are worth waking you up for.

Two ways to express "desirable", and they compose:

  - Explicit tiers by site number, for knowledge you already have
    ("145-171 are the bluff-front sites"). First matching tier wins, so order
    tiers best-first.
  - A geo rule, for knowledge you don't. All four of these campgrounds are
    linear strips running north-south along the coast, so the oceanfront row is
    simply the westernmost sites. Once `discover` has pulled real coordinates,
    this classifies the good sites without anyone hand-maintaining a range list.

The geo rule only ever raises a score, never lowers one, so hand-curated tiers
stay authoritative where you've supplied them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional

from .adjacency import parse_number_spec
from .geo import percentile
from .models import Site

WEST_PERCENTILE = "west_percentile"
VALID_GEO_MODES = {WEST_PERCENTILE}

# Below this many located sites the percentile split is noise, not signal.
_MIN_SITES_FOR_GEO = 8


@dataclass
class Tier:
    score: int
    label: str
    numbers: set[int]


@dataclass
class GeoRule:
    mode: str = WEST_PERCENTILE
    percentile: float = 35.0
    score: int = 100
    label: str = "oceanfront (auto-detected from coordinates)"


@dataclass
class DesirabilityModel:
    default: int = 0
    tiers: list[Tier] = field(default_factory=list)
    excluded: set[int] = field(default_factory=set)
    geo: Optional[GeoRule] = None

    @classmethod
    def from_config(cls, cfg: Optional[dict]) -> "DesirabilityModel":
        cfg = cfg or {}
        tiers = []
        for raw in cfg.get("tiers", []) or []:
            tiers.append(
                Tier(
                    score=int(raw["score"]),
                    label=str(raw.get("label", "")),
                    numbers=parse_number_spec(raw.get("sites")),
                )
            )

        geo_cfg = cfg.get("geo")
        geo = None
        if geo_cfg:
            mode = str(geo_cfg.get("mode", WEST_PERCENTILE)).lower()
            if mode not in VALID_GEO_MODES:
                raise ValueError(
                    f"desirability geo mode must be one of {sorted(VALID_GEO_MODES)}, got {mode!r}"
                )
            geo = GeoRule(
                mode=mode,
                percentile=float(geo_cfg.get("percentile", 35.0)),
                score=int(geo_cfg.get("score", 100)),
                label=str(geo_cfg.get("label", GeoRule.label)),
            )

        return cls(
            default=int(cfg.get("default", 0)),
            tiers=tiers,
            excluded=parse_number_spec((cfg.get("exclude") or {}).get("sites")),
            geo=geo,
        )

    def is_excluded(self, site: Site) -> bool:
        return site.number is not None and site.number in self.excluded

    def _base_score(self, site: Site) -> tuple[int, str]:
        if site.number is not None:
            for tier in self.tiers:
                if site.number in tier.numbers:
                    return tier.score, tier.label
        return self.default, "default"

    def score_all(self, sites: Iterable[Site]) -> dict[str, tuple[int, str]]:
        """Score every site at once, keyed by unit_id.

        Batch rather than per-site because the geo rule is relative: a site is
        "oceanfront" only with respect to the rest of its campground.
        """
        sites = list(sites)
        scored = {s.unit_id: self._base_score(s) for s in sites}

        located = [s for s in sites if s.has_coords]
        if self.geo and len(located) >= _MIN_SITES_FOR_GEO:
            longitudes = [s.lon for s in located]
            cutoff = percentile(longitudes, self.geo.percentile)
            for site in located:
                # Westernmost == smallest longitude == closest to the water.
                if site.lon <= cutoff:
                    current, _ = scored[site.unit_id]
                    if self.geo.score > current:
                        scored[site.unit_id] = (self.geo.score, self.geo.label)

        return scored

    def filter_sites(self, sites: Iterable[Site], min_score: int) -> dict[str, tuple[int, str]]:
        """Return {unit_id: (score, reason)} for sites clearing `min_score`."""
        scored = self.score_all(sites)
        keep = {}
        by_id = {s.unit_id: s for s in sites}
        for unit_id, (score, reason) in scored.items():
            site = by_id[unit_id]
            if self.is_excluded(site):
                continue
            if score >= min_score:
                keep[unit_id] = (score, reason)
        return keep
