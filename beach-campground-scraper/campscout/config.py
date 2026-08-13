"""Config loading: curated campground data + user settings."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import yaml

from .adjacency import AdjacencyModel
from .desirability import DesirabilityModel
from .models import Stay

PKG_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PKG_DIR.parent
DEFAULT_CAMPGROUNDS = PROJECT_DIR / "data" / "campgrounds.yaml"
DEFAULT_CONFIG = PROJECT_DIR / "config.yaml"

_ENV_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _expand_env(value: Any) -> Any:
    """Recursively expand ${VAR} so secrets live in the environment, not the file."""
    if isinstance(value, str):
        return _ENV_RE.sub(lambda m: os.environ.get(m.group(1), ""), value)
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env(v) for v in value]
    return value


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping at the top level")
    return _expand_env(data)


def _as_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value).strip())


@dataclass
class Campground:
    key: str
    name: str
    park: str = ""
    city: str = ""
    place_id: Optional[str] = None
    facility_id: Optional[str] = None
    enabled: bool = True
    notes: str = ""
    map_url: str = ""
    park_url: str = ""
    min_score: Optional[int] = None
    adjacency: AdjacencyModel = field(default_factory=AdjacencyModel)
    desirability: DesirabilityModel = field(default_factory=DesirabilityModel)

    @property
    def configured(self) -> bool:
        """Facility ID is what the availability API actually needs."""
        return bool(self.facility_id)

    @classmethod
    def from_dict(cls, raw: dict) -> "Campground":
        return cls(
            key=str(raw["key"]),
            name=str(raw.get("name", raw["key"])),
            park=str(raw.get("park", "")),
            city=str(raw.get("city", "")),
            place_id=str(raw["place_id"]) if raw.get("place_id") else None,
            facility_id=str(raw["facility_id"]) if raw.get("facility_id") else None,
            enabled=bool(raw.get("enabled", True)),
            notes=str(raw.get("notes", "")).strip(),
            map_url=str(raw.get("map_url", "")),
            park_url=str(raw.get("park_url", "")),
            min_score=int(raw["min_score"]) if raw.get("min_score") is not None else None,
            adjacency=AdjacencyModel.from_config(raw.get("adjacency")),
            desirability=DesirabilityModel.from_config(raw.get("desirability")),
        )


@dataclass
class SearchWindow:
    """A rule that expands into concrete candidate stays."""

    label: str
    nights: int = 2
    checkin: Optional[date] = None
    start: Optional[date] = None
    end: Optional[date] = None
    weekdays: list[int] = field(default_factory=list)

    @classmethod
    def from_dict(cls, raw: dict) -> "SearchWindow":
        return cls(
            label=str(raw.get("label", "")),
            nights=int(raw.get("nights", 2)),
            checkin=_as_date(raw.get("checkin")),
            start=_as_date(raw.get("start")),
            end=_as_date(raw.get("end")),
            weekdays=[int(d) for d in raw.get("weekdays", []) or []],
        )

    def stays(self, today: Optional[date] = None, horizon_days: int = 180) -> list[Stay]:
        """Expand into every check-in date this window covers.

        ReserveCalifornia opens bookings 6 months out, so the default horizon
        matches; there is nothing to find past it.
        """
        today = today or date.today()
        if self.nights < 1:
            raise ValueError(f"search window {self.label!r} needs nights >= 1")

        if self.checkin:
            return [Stay(checkin=self.checkin, nights=self.nights, label=self.label)]

        start = max(self.start or today, today)
        end = self.end or (today + timedelta(days=horizon_days))
        if end <= start:
            return []

        out: list[Stay] = []
        cur = start
        while cur < end:
            if not self.weekdays or cur.weekday() in self.weekdays:
                out.append(Stay(checkin=cur, nights=self.nights, label=self.label))
            cur += timedelta(days=1)
        return out


@dataclass
class Config:
    campgrounds: list[Campground] = field(default_factory=list)
    windows: list[SearchWindow] = field(default_factory=list)
    min_score: int = 70
    horizon_days: int = 180
    poll_seconds: int = 600
    cooldown_hours: int = 12
    state_path: Path = PROJECT_DIR / "data" / "state.json"
    cache_dir: Path = PROJECT_DIR / "data" / "cache"
    notifiers: list[dict] = field(default_factory=list)
    request: dict = field(default_factory=dict)
    heartbeat: dict = field(default_factory=dict)
    stale_after_hours: float = 3.0

    def enabled_campgrounds(self) -> list[Campground]:
        return [c for c in self.campgrounds if c.enabled]

    def all_stays(self, today: Optional[date] = None) -> list[Stay]:
        seen: set[tuple[date, int]] = set()
        stays: list[Stay] = []
        for window in self.windows:
            for stay in window.stays(today=today, horizon_days=self.horizon_days):
                ident = (stay.checkin, stay.nights)
                if ident in seen:
                    continue
                seen.add(ident)
                stays.append(stay)
        return sorted(stays, key=lambda s: (s.checkin, s.nights))

    def campground(self, key: str) -> Campground:
        for cg in self.campgrounds:
            if cg.key == key:
                return cg
        known = ", ".join(c.key for c in self.campgrounds)
        raise KeyError(f"unknown campground {key!r}; known: {known}")


def _merge_campgrounds(base: list[dict], overrides: list[dict]) -> list[dict]:
    """User config overlays curated data, keyed by `key`. Shallow per-field."""
    by_key: dict[str, dict] = {}
    order: list[str] = []
    for raw in base:
        key = str(raw["key"])
        by_key[key] = dict(raw)
        order.append(key)
    for raw in overrides:
        key = str(raw["key"])
        if key in by_key:
            by_key[key].update(raw)
        else:
            by_key[key] = dict(raw)
            order.append(key)
    return [by_key[k] for k in order]


def load_config(
    config_path: Optional[Path] = None,
    campgrounds_path: Optional[Path] = None,
) -> Config:
    campgrounds_path = Path(campgrounds_path or DEFAULT_CAMPGROUNDS)
    config_path = Path(config_path or DEFAULT_CONFIG)

    curated = _load_yaml(campgrounds_path).get("campgrounds", []) or []
    user = _load_yaml(config_path)
    merged = _merge_campgrounds(curated, user.get("campgrounds", []) or [])

    search = user.get("search", {}) or {}
    windows = [SearchWindow.from_dict(w) for w in search.get("windows", []) or []]

    paths = user.get("paths", {}) or {}
    return Config(
        campgrounds=[Campground.from_dict(c) for c in merged],
        windows=windows,
        min_score=int(search.get("min_score", 70)),
        horizon_days=int(search.get("horizon_days", 180)),
        poll_seconds=int(user.get("poll_seconds", 600)),
        cooldown_hours=int(user.get("cooldown_hours", 12)),
        state_path=Path(paths.get("state", PROJECT_DIR / "data" / "state.json")),
        cache_dir=Path(paths.get("cache", PROJECT_DIR / "data" / "cache")),
        notifiers=user.get("notifiers", []) or [],
        request=user.get("request", {}) or {},
        heartbeat=user.get("heartbeat", {}) or {},
        stale_after_hours=float(user.get("stale_after_hours", 3.0)),
    )
