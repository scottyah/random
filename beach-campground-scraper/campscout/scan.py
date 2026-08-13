"""The scan: availability -> bookable stays -> desirable sites -> adjacent pairs."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

from .config import Campground, Config
from .models import PairHit, Site, Stay
from .providers import ReserveCalifornia, ReserveCaliforniaError

log = logging.getLogger(__name__)


def bookable_sites(
    free: dict[str, set[date]], stay: Stay, allowed: Optional[set[str]] = None
) -> set[str]:
    """Unit IDs free for *every* night of `stay`.

    A pair is only useful if both sites cover the whole trip, so partial
    coverage is not a hit.
    """
    nights = stay.occupied_nights()
    out = set()
    for unit_id, days in free.items():
        if allowed is not None and unit_id not in allowed:
            continue
        if all(night in days for night in nights):
            out.add(unit_id)
    return out


def find_pairs_for_campground(
    campground: Campground,
    sites: dict[str, Site],
    free: dict[str, set[date]],
    stays: list[Stay],
    min_score: int,
    booking_url: str = "",
) -> list[PairHit]:
    """All adjacent desirable pairs across every candidate stay."""
    site_list = list(sites.values())
    if not site_list:
        return []

    keep = campground.desirability.filter_sites(site_list, min_score)
    if not keep:
        log.info("[%s] no sites clear min_score=%d", campground.key, min_score)
        return []

    log.info("[%s] %d/%d sites are desirable enough", campground.key, len(keep), len(site_list))

    hits: list[PairHit] = []
    for stay in stays:
        open_ids = bookable_sites(free, stay, allowed=set(keep))
        if len(open_ids) < 2:
            continue
        open_sites = [sites[uid] for uid in open_ids]
        for site_a, site_b in campground.adjacency.pairs(open_sites):
            score_a, reason_a = keep[site_a.unit_id]
            score_b, reason_b = keep[site_b.unit_id]
            hits.append(
                PairHit(
                    campground_key=campground.key,
                    campground_name=campground.name,
                    stay=stay,
                    site_a=site_a,
                    site_b=site_b,
                    score_a=score_a,
                    score_b=score_b,
                    reason_a=reason_a,
                    reason_b=reason_b,
                    booking_url=booking_url,
                )
            )
    return hits


def scan(
    config: Config,
    client: Optional[ReserveCalifornia] = None,
    today: Optional[date] = None,
    stats: Optional[dict] = None,
) -> list[PairHit]:
    """Run one full pass over every enabled, configured campground.

    `stats`, if given, is filled in with counters the caller needs for the
    heartbeat: how many campgrounds were actually reached, how many sites were
    inspected, and any per-campground errors. Passed as an out-param rather
    than folded into the return value so the common case stays a plain list.
    """
    today = today or date.today()
    client = client or ReserveCalifornia(**config.request)
    stats = stats if stats is not None else {}
    stats.setdefault("campgrounds_ok", 0)
    stats.setdefault("campgrounds_attempted", 0)
    stats.setdefault("sites_checked", 0)
    stats.setdefault("errors", [])

    stays = config.all_stays(today=today)
    if not stays:
        log.warning("no search windows produced any candidate stays; check config.yaml")
        stats["errors"].append("no candidate stays; check search.windows in config.yaml")
        return []

    horizon_end = max(s.checkout for s in stays)
    horizon_start = min(s.checkin for s in stays)
    log.info(
        "scanning %s → %s (%d candidate stays)",
        horizon_start,
        horizon_end,
        len(stays),
    )

    all_hits: list[PairHit] = []
    for campground in config.enabled_campgrounds():
        if not campground.configured:
            log.warning(
                "[%s] no facility_id yet — run `campscout discover --write` first; skipping",
                campground.key,
            )
            stats["errors"].append(f"{campground.key}: no facility_id (run `discover --write`)")
            continue

        stats["campgrounds_attempted"] += 1
        try:
            sites, free = client.availability(
                campground.facility_id, horizon_start, horizon_end
            )
        except ReserveCaliforniaError as exc:
            # One flaky park should not abort the whole run.
            log.error("[%s] availability lookup failed: %s", campground.key, exc)
            stats["errors"].append(f"{campground.key}: {exc}")
            continue

        stats["campgrounds_ok"] += 1
        stats["sites_checked"] += len(sites)
        log.info("[%s] %d sites returned", campground.key, len(sites))
        min_score = campground.min_score if campground.min_score is not None else config.min_score
        hits = find_pairs_for_campground(
            campground,
            sites,
            free,
            stays,
            min_score,
            booking_url=client.booking_url(campground.place_id, campground.facility_id),
        )
        log.info("[%s] %d adjacent desirable pair(s)", campground.key, len(hits))
        all_hits.extend(hits)

    # Best pairs first, then soonest.
    all_hits.sort(key=lambda h: (-h.min_score, h.stay.checkin))
    return all_hits


def default_windows_hint(today: Optional[date] = None) -> str:  # pragma: no cover - help text
    today = today or date.today()
    return (
        "Example: weekends for the next 6 months\n"
        "  search:\n"
        "    windows:\n"
        "      - label: weekend\n"
        "        nights: 2\n"
        "        weekdays: [4]   # Friday check-in (Mon=0)\n"
        f"        start: '{today:%Y-%m-%d}'\n"
        f"        end: '{today + timedelta(days=180):%Y-%m-%d}'\n"
    )
