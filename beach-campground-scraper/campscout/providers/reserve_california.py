"""Client for the ReserveCalifornia (UseDirect "RDR") backend.

All four target campgrounds are California State Parks, so they share this one
backend -- the same JSON API the reservecalifornia.com front-end calls.

Endpoint note: the discovery endpoints (park/facility listing) have moved
around between UseDirect releases, and this client could not be exercised
against the live host at authoring time. So `search_places` and
`facilities_for_place` try a short list of known endpoint spellings and use
whichever answers, logging the winner. The availability endpoint
(`POST /search/grid`) is the stable one and is used directly.
"""

from __future__ import annotations

import logging
import random
import time
from datetime import date, timedelta
from typing import Any, Iterable, Optional

import requests

from ..models import Site, parse_site_number

log = logging.getLogger(__name__)

# The grid endpoint degrades past roughly a month; chunk long horizons.
MAX_GRID_DAYS = 30

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
)


class ReserveCaliforniaError(RuntimeError):
    pass


def _first_float(payload: dict, *keys: str) -> Optional[float]:
    """MapInfo key casing varies by facility; take the first key that parses."""
    for key in keys:
        if key in payload and payload[key] not in (None, "", 0):
            try:
                return float(payload[key])
            except (TypeError, ValueError):
                continue
    return None


class ReserveCalifornia:
    # ReserveCalifornia's backend moved from calirdr.usedirect.com (whose DNS
    # now sinkholes to 0.0.0.0) to Tyler Technologies' platform in 2026. The
    # live value is published at https://www.reservecalifornia.com/config.json
    # under "rdrApiUrl" — check there first if this ever starts failing.
    BASE = "https://california-rdr.prod.cali.rd12.recreation-management.tylerapp.com/rdr"
    WEB = "https://www.reservecalifornia.com"

    PLACE_SEARCH_PATHS = ("/search/place", "/search/places")
    FACILITY_LIST_PATHS = ("/search/facilities", "/fd/facilities")

    def __init__(
        self,
        timeout: float = 30.0,
        user_agent: str = DEFAULT_USER_AGENT,
        min_interval: float = 1.0,
        max_retries: int = 3,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.timeout = timeout
        self.min_interval = min_interval
        self.max_retries = max_retries
        self._last_call = 0.0
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "User-Agent": user_agent,
                "Accept": "application/json, text/plain, */*",
                "Content-Type": "application/json",
                "Origin": self.WEB,
                "Referer": f"{self.WEB}/",
            }
        )

    # ---- transport -----------------------------------------------------

    def _throttle(self) -> None:
        """Stay well under anything that looks like abuse."""
        elapsed = time.monotonic() - self._last_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_call = time.monotonic()

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = f"{self.BASE}{path}"
        last_error: Optional[Exception] = None
        for attempt in range(self.max_retries):
            self._throttle()
            try:
                resp = self.session.request(method, url, timeout=self.timeout, **kwargs)
            except requests.RequestException as exc:
                last_error = exc
                log.warning("%s %s failed (%s), attempt %d", method, path, exc, attempt + 1)
            else:
                if resp.status_code == 200:
                    try:
                        return resp.json()
                    except ValueError as exc:
                        raise ReserveCaliforniaError(
                            f"{method} {path} returned non-JSON (status 200, "
                            f"{len(resp.content)} bytes)"
                        ) from exc
                # 4xx other than 429 is a real answer -- do not hammer it.
                if 400 <= resp.status_code < 500 and resp.status_code != 429:
                    raise ReserveCaliforniaError(
                        f"{method} {path} -> HTTP {resp.status_code}: {resp.text[:300]}"
                    )
                last_error = ReserveCaliforniaError(
                    f"{method} {path} -> HTTP {resp.status_code}"
                )
                log.warning("%s %s -> HTTP %s, attempt %d", method, path, resp.status_code, attempt + 1)

            if attempt < self.max_retries - 1:
                backoff = (2**attempt) + random.uniform(0, 0.5)
                time.sleep(backoff)

        raise ReserveCaliforniaError(f"{method} {path} failed after {self.max_retries} attempts: {last_error}")

    def _post(self, path: str, payload: dict) -> Any:
        return self._request("POST", path, json=payload)

    def _get(self, path: str, params: Optional[dict] = None) -> Any:
        return self._request("GET", path, params=params)

    # ---- discovery -----------------------------------------------------

    def search_places(
        self,
        latitude: float,
        longitude: float,
        nearby_limit: int = 50,
        start: Optional[date] = None,
    ) -> list[dict]:
        """Find parks near a point. Returns raw place dicts."""
        start = start or date.today() + timedelta(days=30)
        payload = {
            "PlaceId": 0,
            "Latitude": latitude,
            "Longitude": longitude,
            "HighlightedPlaceId": 0,
            "StartDate": start.strftime("%Y-%m-%d"),
            "Nights": 1,
            "CountNearby": True,
            "NearbyLimit": nearby_limit,
            "NearbyOnlyAvailable": False,
            "NearbyCountLimit": nearby_limit,
            "Sort": "Distance",
            "CustomerId": "0",
            "RefreshFavourites": False,
            "IsADA": False,
            "UnitCategoryId": 0,
            "SleepingUnitId": 0,
            "MinVehicleLength": 0,
            "UnitTypesGroupIds": [],
        }

        errors = []
        for path in self.PLACE_SEARCH_PATHS:
            try:
                data = self._post(path, payload)
            except ReserveCaliforniaError as exc:
                errors.append(f"{path}: {exc}")
                continue
            log.info("place search resolved via %s", path)
            return self._extract_places(data)

        raise ReserveCaliforniaError("no place-search endpoint responded; tried " + "; ".join(errors))

    @staticmethod
    def _extract_places(data: Any) -> list[dict]:
        """Normalize the several shapes the place search has used."""
        if isinstance(data, list):
            return data
        if not isinstance(data, dict):
            return []
        places: list[dict] = []
        selected = data.get("SelectedPlace")
        if isinstance(selected, dict):
            places.append(selected)
        for key in ("NearbyPlaces", "Places", "Results"):
            value = data.get(key)
            if isinstance(value, list):
                places.extend(p for p in value if isinstance(p, dict))
            elif isinstance(value, dict):
                places.extend(p for p in value.values() if isinstance(p, dict))
        return places

    def facilities_for_place(self, place_id: int, start: Optional[date] = None) -> list[dict]:
        """List the campgrounds (facilities) inside a park."""
        start = start or date.today() + timedelta(days=30)
        payload = {
            "PlaceId": int(place_id),
            "Latitude": 0,
            "Longitude": 0,
            "HighlightedPlaceId": 0,
            "StartDate": start.strftime("%Y-%m-%d"),
            "Nights": 1,
            "CountNearby": False,
            "Sort": "Distance",
            "CustomerId": "0",
            "IsADA": False,
            "UnitCategoryId": 0,
            "SleepingUnitId": 0,
            "MinVehicleLength": 0,
            "UnitTypesGroupIds": [],
        }
        for path in self.PLACE_SEARCH_PATHS:
            try:
                data = self._post(path, payload)
            except ReserveCaliforniaError:
                continue
            for place in self._extract_places(data):
                if str(place.get("PlaceId")) != str(place_id):
                    continue
                facilities = place.get("Facilities")
                if isinstance(facilities, dict):
                    return [f for f in facilities.values() if isinstance(f, dict)]
                if isinstance(facilities, list):
                    return facilities
        return []

    # ---- availability --------------------------------------------------

    def grid(self, facility_id: str, start: date, end: date) -> dict:
        """Raw availability grid for one facility over [start, end)."""
        payload = {
            "FacilityId": str(facility_id),
            "StartDate": start.strftime("%Y-%m-%d"),
            "EndDate": end.strftime("%Y-%m-%d"),
            "UnitSort": "orderby",
            "IsADA": False,
            "RestrictADA": False,
            "MinVehicleLength": 0,
            "UnitCategoryId": 0,
            "UnitTypesGroupIds": [],
            "SleepingUnitId": 0,
            "InSeasonOnly": True,
            "WebOnly": True,
        }
        return self._post("/search/grid", payload)

    @staticmethod
    def _units_from_grid(grid: dict) -> list[dict]:
        facility = grid.get("Facility") or {}
        units = facility.get("Units")
        if isinstance(units, dict):
            return [u for u in units.values() if isinstance(u, dict)]
        if isinstance(units, list):
            return [u for u in units if isinstance(u, dict)]
        return []

    @classmethod
    def _site_from_unit(cls, facility_id: str, unit: dict) -> Site:
        name = str(unit.get("Name") or unit.get("ShortName") or "").strip()
        short = str(unit.get("ShortName") or "").strip()
        map_info = unit.get("MapInfo") if isinstance(unit.get("MapInfo"), dict) else {}
        return Site(
            facility_id=str(facility_id),
            unit_id=str(unit.get("UnitId")),
            name=name or short,
            number=parse_site_number(short) or parse_site_number(name),
            loop=(str(unit.get("Loop")).strip() or None) if unit.get("Loop") else None,
            is_ada=bool(unit.get("IsAda")),
            vehicle_length=int(unit.get("VehicleLength") or 0),
            lat=_first_float(map_info, "Latitude", "latitude", "Lat"),
            lon=_first_float(map_info, "Longitude", "longitude", "Long", "Lng"),
            web_bookable=bool(unit.get("AllowWebBooking", True)),
            unit_type_id=unit.get("UnitTypeId"),
        )

    def list_sites(self, facility_id: str, start: Optional[date] = None) -> list[Site]:
        """The full site roster for a facility, with coordinates when present."""
        start = start or date.today() + timedelta(days=45)
        grid = self.grid(facility_id, start, start + timedelta(days=2))
        return [self._site_from_unit(facility_id, u) for u in self._units_from_grid(grid)]

    def availability(
        self, facility_id: str, start: date, end: date
    ) -> tuple[dict[str, Site], dict[str, set[date]]]:
        """Free nights per site over [start, end).

        Returns ({unit_id: Site}, {unit_id: {free dates}}). A date is "free"
        only when the slice says free, not blocked, and not walk-in only.
        """
        sites: dict[str, Site] = {}
        free: dict[str, set[date]] = {}

        window_start = start
        while window_start < end:
            window_end = min(window_start + timedelta(days=MAX_GRID_DAYS), end)
            grid = self.grid(facility_id, window_start, window_end)

            for unit in self._units_from_grid(grid):
                site = self._site_from_unit(facility_id, unit)
                if not site.web_bookable:
                    continue
                sites.setdefault(site.unit_id, site)
                bucket = free.setdefault(site.unit_id, set())

                slices = unit.get("Slices")
                iterable: Iterable[Any]
                if isinstance(slices, dict):
                    iterable = slices.values()
                elif isinstance(slices, list):
                    iterable = slices
                else:
                    continue

                for sl in iterable:
                    if not isinstance(sl, dict):
                        continue
                    raw = str(sl.get("Date") or "")[:10]
                    if not raw:
                        continue
                    try:
                        day = date.fromisoformat(raw)
                    except ValueError:
                        continue
                    if sl.get("IsFree") and not sl.get("IsBlocked") and not sl.get("IsWalkin"):
                        bucket.add(day)

            window_start = window_end

        return sites, free

    # ---- links ---------------------------------------------------------

    def booking_url(self, place_id: Optional[str], facility_id: str) -> str:
        if place_id:
            return f"{self.WEB}/Web/Default.aspx#!park/{place_id}/{facility_id}"
        return f"{self.WEB}/Web/Default.aspx#!park/0/{facility_id}"
