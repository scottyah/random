"""Command line entry point."""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import signal
import sys
import threading
import time
from datetime import date
from pathlib import Path
from typing import Optional

import yaml

from .config import DEFAULT_CAMPGROUNDS, Config, load_config
from .heartbeat import build_heartbeat
from .models import PairHit
from .notify import build_notifiers, dispatch, format_body, format_subject
from .providers import ReserveCalifornia, ReserveCaliforniaError
from .scan import scan
from .state import AlertState

log = logging.getLogger("campscout")

# Roughly the centroid of the North County coastline, Encinitas → San Onofre.
NORTH_COUNTY_LAT = 33.15
NORTH_COUNTY_LON = -117.35


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )


def _client(config: Config) -> ReserveCalifornia:
    return ReserveCalifornia(**config.request)


# ---- commands ----------------------------------------------------------


def cmd_campgrounds(args: argparse.Namespace, config: Config) -> int:
    """Show what we know about each campground, configured or not."""
    for cg in config.campgrounds:
        status = "on " if cg.enabled else "off"
        ids = (
            f"place={cg.place_id or '?'} facility={cg.facility_id or '?'}"
            if not cg.configured
            else f"place={cg.place_id or '-'} facility={cg.facility_id}"
        )
        print(f"[{status}] {cg.key:<20} {cg.name}")
        print(f"        {cg.city}")
        print(f"        {ids}")
        if cg.map_url:
            print(f"        map:  {cg.map_url}")
        if cg.park_url:
            print(f"        park: {cg.park_url}")
        if cg.notes and args.verbose:
            print(f"        {' '.join(cg.notes.split())}")
        print()

    missing = [c.key for c in config.enabled_campgrounds() if not c.configured]
    if missing:
        print(f"Missing facility IDs: {', '.join(missing)}")
        print("Run:  python -m campscout discover --write")
    return 0


def cmd_maps(args: argparse.Namespace, config: Config) -> int:
    """Print (and optionally download) the official State Parks site maps."""
    out_dir = Path(args.out or (config.cache_dir / "maps"))
    if args.download:
        out_dir.mkdir(parents=True, exist_ok=True)

    exit_code = 0
    for cg in config.campgrounds:
        if not (cg.map_url or cg.park_url):
            continue
        print(f"{cg.name}")
        if cg.map_url:
            print(f"  site map : {cg.map_url}")
        if cg.park_url:
            print(f"  park page: {cg.park_url}")

        if args.download and cg.map_url:
            dest = out_dir / f"{cg.key}.pdf"
            try:
                import requests

                resp = requests.get(cg.map_url, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
                resp.raise_for_status()
                dest.write_bytes(resp.content)
                print(f"  saved    : {dest} ({len(resp.content):,} bytes)")
            except Exception as exc:  # noqa: BLE001 - report and continue
                # These URLs are best-known, not verified; State Parks also
                # reshuffles PDF paths. Fall back to the park page.
                print(f"  DOWNLOAD FAILED: {exc}")
                print(f"  -> find the current map linked from {cg.park_url or 'parks.ca.gov'}")
                exit_code = 1
        print()
    return exit_code


def cmd_discover(args: argparse.Namespace, config: Config) -> int:
    """Resolve real place/facility IDs from the API and optionally save them."""
    client = _client(config)
    try:
        places = client.search_places(
            latitude=args.lat, longitude=args.lon, nearby_limit=args.limit
        )
    except ReserveCaliforniaError as exc:
        log.error("place search failed: %s", exc)
        log.error(
            "If this is a network/policy block, run from a host with plain "
            "outbound HTTPS to calirdr.usedirect.com."
        )
        return 2

    log.info("found %d places within the search radius", len(places))

    rows: list[tuple[str, str, str, str]] = []
    for place in places:
        name = str(place.get("Name", "")).strip()
        place_id = str(place.get("PlaceId", "")).strip()
        if not place_id:
            continue
        if args.filter and args.filter.lower() not in name.lower():
            continue

        facilities = place.get("Facilities")
        facility_items: list[dict] = []
        if isinstance(facilities, dict):
            facility_items = [f for f in facilities.values() if isinstance(f, dict)]
        elif isinstance(facilities, list):
            facility_items = [f for f in facilities if isinstance(f, dict)]
        if not facility_items:
            try:
                facility_items = client.facilities_for_place(int(place_id))
            except (ReserveCaliforniaError, ValueError) as exc:
                log.debug("no facilities for place %s: %s", place_id, exc)

        if not facility_items:
            rows.append((name, place_id, "-", "(no facilities returned)"))
        for fac in facility_items:
            rows.append(
                (
                    name,
                    place_id,
                    str(fac.get("FacilityId", "")),
                    str(fac.get("Name", "")).strip(),
                )
            )

    if not rows:
        log.warning("nothing matched; try a wider --miles or drop --filter")
        return 1

    print(f"\n{'PARK':<38} {'PLACE':>7} {'FACILITY':>9}  CAMPGROUND")
    print("-" * 96)
    for park, place_id, facility_id, fac_name in rows:
        print(f"{park[:38]:<38} {place_id:>7} {facility_id:>9}  {fac_name}")
    print()

    if args.write:
        return _write_discovered_ids(rows, config, args.campgrounds)

    print("Re-run with --write to save matching IDs into data/campgrounds.yaml.")
    return 0


def _write_discovered_ids(
    rows: list[tuple[str, str, str, str]],
    config: Config,
    campgrounds_path: Optional[Path] = None,
) -> int:
    """Match discovered facilities to configured campgrounds by park name."""
    path = Path(campgrounds_path or DEFAULT_CAMPGROUNDS)
    with path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    updated = 0
    for entry in raw.get("campgrounds", []) or []:
        key = entry.get("key")
        try:
            cg = config.campground(str(key))
        except KeyError:
            continue
        needle = (cg.park or cg.name).lower()
        # Prefer a facility whose park name matches and that looks like a
        # campground rather than a day-use or group-only facility.
        matches = [r for r in rows if needle and needle in r[0].lower() and r[2] not in ("", "-")]
        if not matches:
            continue
        park, place_id, facility_id, fac_name = matches[0]
        if len(matches) > 1:
            log.warning(
                "[%s] %d facilities matched %r; picked %s (%s). Check the table "
                "above and edit data/campgrounds.yaml if that's the wrong one.",
                key,
                len(matches),
                park,
                facility_id,
                fac_name,
            )
        entry["place_id"] = place_id
        entry["facility_id"] = facility_id
        updated += 1
        log.info("[%s] place_id=%s facility_id=%s (%s)", key, place_id, facility_id, fac_name)

    if not updated:
        log.warning("no configured campground matched a discovered park name; nothing written")
        return 1

    try:
        with path.open("w", encoding="utf-8") as fh:
            yaml.safe_dump(raw, fh, sort_keys=False, allow_unicode=True, width=100)
    except OSError as exc:
        # Typical in Kubernetes: campgrounds.yaml came from a read-only
        # ConfigMap mount. Discovery is a bootstrap step, not a runtime one.
        log.error("could not write %s: %s", path, exc)
        log.error(
            "If this path is a read-only mount, run `discover` without --write, "
            "then paste the IDs into your ConfigMap."
        )
        return 2
    log.info("wrote %d campground ID(s) to %s", updated, path)
    return 0


def cmd_sites(args: argparse.Namespace, config: Config) -> int:
    """Dump the real site roster for a campground (this is the live site map)."""
    cg = config.campground(args.campground)
    if not cg.configured:
        log.error("[%s] has no facility_id; run `discover --write` first", cg.key)
        return 2

    client = _client(config)
    try:
        sites = client.list_sites(cg.facility_id)
    except ReserveCaliforniaError as exc:
        log.error("site lookup failed: %s", exc)
        return 2

    if not sites:
        log.warning("facility %s returned no sites", cg.facility_id)
        return 1

    scored = cg.desirability.score_all(sites)
    sites.sort(key=lambda s: (s.number if s.number is not None else 10**9, s.name))
    located = sum(1 for s in sites if s.has_coords)

    print(f"\n{cg.name} — facility {cg.facility_id} — {len(sites)} sites "
          f"({located} with coordinates)\n")
    print(f"{'SITE':<12} {'UNIT ID':>9} {'SCORE':>5}  {'ADA':<4} {'LAT,LON':<24} WHY")
    print("-" * 100)
    for site in sites:
        score, reason = scored[site.unit_id]
        coords = f"{site.lat:.5f},{site.lon:.5f}" if site.has_coords else "-"
        excluded = " [excluded]" if cg.desirability.is_excluded(site) else ""
        print(
            f"{site.label[:12]:<12} {site.unit_id:>9} {score:>5}  "
            f"{'yes' if site.is_ada else 'no':<4} {coords:<24} {reason}{excluded}"
        )

    if not located:
        print(
            "\nNote: this facility returned no coordinates, so the geo rules are "
            "inactive here.\nDesirability and adjacency fall back to site-number "
            "ranges in data/campgrounds.yaml."
        )

    if args.json:
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        payload = [
            {
                "unit_id": s.unit_id,
                "name": s.name,
                "number": s.number,
                "lat": s.lat,
                "lon": s.lon,
                "is_ada": s.is_ada,
                "vehicle_length": s.vehicle_length,
                "score": scored[s.unit_id][0],
                "reason": scored[s.unit_id][1],
            }
            for s in sites
        ]
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"\nwrote {out}")
    return 0


def _run_once(
    config: Config, notifiers, state: AlertState, dry_run: bool
) -> tuple[list[PairHit], bool]:
    """Run one pass. Returns (hits, healthy).

    `healthy` is False when the run genuinely failed, as distinct from
    succeeding and finding nothing. Callers turn that into an exit code, which
    is what makes a broken CronJob show up as failed instead of quietly green.
    """
    heartbeat = build_heartbeat(config.heartbeat)

    # Warn before scanning if the last successful run is old: the gap itself is
    # the signal that something was down while you assumed it was watching.
    if state.last_success and state.is_stale(config.stale_after_hours):
        age_h = (state.seconds_since_success() or 0) / 3600
        log.warning(
            "last successful scan was %.1fh ago (threshold %.1fh) — "
            "the watcher was not running for part of that time",
            age_h,
            config.stale_after_hours,
        )

    stats: dict = {}
    try:
        hits = scan(config, stats=stats)
    except Exception as exc:  # noqa: BLE001 - record, ping, then re-raise upward
        state.record_run(ok=False, error=str(exc))
        state.save()
        if heartbeat.enabled:
            heartbeat.failure()
        raise

    # A run that reached nothing is a failure, not a quiet "nothing available".
    reached_anything = stats.get("campgrounds_ok", 0) > 0
    if not reached_anything:
        problems = "; ".join(stats.get("errors", [])) or "no campgrounds reached"
        log.error("scan reached no campgrounds: %s", problems)
        state.record_run(ok=False, error=problems)
        state.save()
        if heartbeat.enabled:
            heartbeat.failure()
        return [], False

    state.record_run(
        ok=True,
        pairs_found=len(hits),
        sites_checked=stats.get("sites_checked", 0),
    )
    if stats.get("errors"):
        log.warning("partial scan: %s", "; ".join(stats["errors"]))

    fresh = [h for h in hits if state.should_notify(h.dedupe_key)]
    if hits:
        log.info("%d pair(s) found, %d new since last alert", len(hits), len(fresh))
    else:
        log.info("no adjacent desirable pairs available right now")

    if fresh and dry_run:
        print(format_subject(fresh))
        print(format_body(fresh))
        log.info("dry run: not sending notifications, not recording alert state")
    elif fresh:
        if dispatch(notifiers, fresh):
            state.mark_notified(h.dedupe_key for h in fresh)
            state.record_alert(len(fresh))
        else:
            # Nothing got through, so don't burn the cooldown -- retry next pass.
            log.error("no notifier succeeded; leaving alert state unchanged so we retry")

    state.prune()
    state.save()
    if heartbeat.enabled:
        heartbeat.success()
    return hits, True


def cmd_scan(args: argparse.Namespace, config: Config) -> int:
    state = AlertState(config.state_path, config.cooldown_hours)
    notifiers = build_notifiers(config.notifiers)
    hits, healthy = _run_once(config, notifiers, state, args.dry_run)

    # A run that reached nothing is a real failure: exit non-zero so a k8s Job
    # is marked failed and a misconfigured deploy doesn't sit green forever.
    if not healthy:
        return 1
    # "Nothing available" is the normal outcome, not an error: exiting non-zero
    # here would make cron mail you a failure every single quiet run.
    if not hits and args.fail_if_none:
        return 3
    return 0


def cmd_watch(args: argparse.Namespace, config: Config) -> int:
    state = AlertState(config.state_path, config.cooldown_hours)
    notifiers = build_notifiers(config.notifiers)
    interval = max(120, config.poll_seconds)
    if interval != config.poll_seconds:
        log.warning("poll_seconds raised to %ds to stay polite to the API", interval)

    # As PID 1 in a container Python gets no default SIGTERM action, so without
    # this `docker stop` / a k8s pod eviction would stall until SIGKILL.
    stop = threading.Event()

    def _handle(signum, _frame):
        log.info("received %s, finishing current pass then exiting", signal.Signals(signum).name)
        stop.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(sig, _handle)
        except ValueError:  # not on the main thread
            pass

    log.info("watching every %ds — SIGTERM or Ctrl-C to stop", interval)
    while not stop.is_set():
        started = time.monotonic()
        try:
            _run_once(config, notifiers, state, args.dry_run)
        except Exception as exc:  # noqa: BLE001 - a watcher must not die on one bad pass
            log.exception("scan pass failed: %s", exc)

        # Jitter so repeated runs don't hit the API on a predictable beat.
        sleep_for = max(0.0, interval - (time.monotonic() - started)) + random.uniform(0, 30)
        # Interruptible sleep: a stop signal shouldn't wait out the interval.
        if stop.wait(sleep_for):
            break

    log.info("stopped cleanly")
    return 0


def _ago(seconds: Optional[float]) -> str:
    if seconds is None:
        return "never"
    if seconds < 90:
        return f"{int(seconds)}s ago"
    if seconds < 5400:
        return f"{seconds / 60:.0f} min ago"
    if seconds < 172800:
        return f"{seconds / 3600:.1f} hours ago"
    return f"{seconds / 86400:.1f} days ago"


def _scheduler_status() -> list[str]:
    """Best-effort check for whether anything is scheduled to run us.

    Only *active* schedulers count. `systemctl is-active` prints "unknown" or
    "inactive" for a unit that was never installed, and treating that as a
    finding would report an unscheduled host as scheduled.
    """
    import shutil
    import subprocess

    findings: list[str] = []

    if shutil.which("systemctl"):
        try:
            result = subprocess.run(
                ["systemctl", "is-active", "campscout.timer"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            state = result.stdout.strip()
            if state == "active":
                findings.append("systemd timer campscout.timer: active")
        except (subprocess.SubprocessError, OSError):
            pass

    if shutil.which("crontab"):
        try:
            result = subprocess.run(
                ["crontab", "-l"], capture_output=True, text=True, timeout=5
            )
            lines = [
                ln.strip()
                for ln in result.stdout.splitlines()
                if "campscout" in ln and not ln.strip().startswith("#")
            ]
            if lines:
                findings.append(f"crontab: {len(lines)} campscout entry/entries")
                findings.extend(f"    {ln}" for ln in lines)
        except (subprocess.SubprocessError, OSError):
            pass

    return findings


def cmd_status(args: argparse.Namespace, config: Config) -> int:
    """Answer the only question that matters: is this actually watching?"""
    state = AlertState(config.state_path, config.cooldown_hours)
    runs = state.runs
    age = state.seconds_since_success()
    stale = state.is_stale(config.stale_after_hours)

    # Probe mode: staleness only, one line, no setup advice. A k8s Deployment
    # running `watch` has no cron or systemd timer, so the scheduling check
    # would fail forever and restart-loop a perfectly healthy pod.
    if getattr(args, "check", False):
        if stale:
            print(f"STALE: last successful scan {_ago(age)}")
            return 1
        print(f"OK: last successful scan {_ago(age)}")
        return 0

    if age is None:
        verdict = "NOT RUNNING — no successful scan has ever completed"
    elif stale:
        verdict = f"STALE — last successful scan {_ago(age)}, expected within {config.stale_after_hours}h"
    else:
        verdict = f"OK — last successful scan {_ago(age)}"

    print()
    print("=" * 68)
    print(f"  {verdict}")
    print("=" * 68)

    print("\nScan history")
    print(f"  last success   : {_ago(age)}")
    print(f"  last attempt   : {_ago(state.seconds_since_attempt())}")
    print(f"  total scans    : {runs.get('total_scans', 0)}")
    print(f"  sites checked  : {runs.get('last_sites_checked', 0)} (last run)")
    print(f"  pairs found    : {runs.get('last_pairs_found', 0)} (last run)")
    print(f"  alerts sent    : {runs.get('total_alerts', 0)} total, last {_ago(state.seconds_since_alert())}")
    if runs.get("last_error"):
        print(f"  last error     : {runs['last_error']}")

    print("\nWhat it is watching")
    enabled = config.enabled_campgrounds()
    ready = [c for c in enabled if c.configured]
    for cg in enabled:
        mark = "ok " if cg.configured else "NOT CONFIGURED"
        print(f"  [{mark:>14}] {cg.name}")
    stays = config.all_stays()
    print(f"  {len(stays)} candidate stays, min_score {config.min_score}, "
          f"{config.horizon_days}d horizon")

    print("\nScheduling")
    findings = _scheduler_status()
    if findings:
        for line in findings:
            print(f"  {line}")
    else:
        print("  no systemd timer or crontab entry found for campscout")
        print("  (if you run `watch` in tmux/screen this check cannot see it)")

    heartbeat = build_heartbeat(config.heartbeat)
    print("\nDead-man's switch")
    if heartbeat.enabled:
        print(f"  configured: {heartbeat.url}")
        print("  an outside service will alert you if these pings stop")
    else:
        print("  NOT configured — if this host dies you will not be told;")
        print("  silence will look exactly like 'nothing available'.")
        print("  Set heartbeat.url in config.yaml (healthchecks.io is free).")

    print()

    problems = []
    if not ready:
        problems.append("no campground has a facility_id — run `discover --write`")
    if age is None:
        problems.append("never completed a scan — run `campscout scan`")
    if not findings:
        problems.append("nothing scheduled — install the timer or a cron entry")
    if problems:
        print("To start actually watching:")
        for i, problem in enumerate(problems, 1):
            print(f"  {i}. {problem}")
        print()
        return 1
    return 0 if not stale else 1


def cmd_test_notify(args: argparse.Namespace, config: Config) -> int:
    """Prove the notification path works before relying on it."""
    from .models import Site, Stay

    demo = PairHit(
        campground_key="san_elijo",
        campground_name="San Elijo State Beach (TEST)",
        stay=Stay(checkin=date.today(), nights=2, label="test"),
        site_a=Site(facility_id="0", unit_id="1", name="Site 146", number=146),
        site_b=Site(facility_id="0", unit_id="2", name="Site 147", number=147),
        score_a=100,
        score_b=100,
        reason_a="bluff-front, north section",
        reason_b="bluff-front, north section",
        booking_url="https://www.reservecalifornia.com/",
    )
    notifiers = build_notifiers(config.notifiers)
    delivered = dispatch(notifiers, [demo])
    log.info("delivered to %d/%d notifier(s)", delivered, len(notifiers))
    return 0 if delivered else 1


# ---- parser ------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="campscout",
        description="Watch North County San Diego beach campgrounds for adjacent open sites.",
    )
    # Paths are also settable by env var so a container can point at mounted
    # ConfigMaps without rewriting the command line.
    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default=os.environ.get("CAMPSCOUT_CONFIG") or None,
        help="path to config.yaml (env: CAMPSCOUT_CONFIG)",
    )
    parser.add_argument(
        "--campgrounds",
        type=Path,
        default=os.environ.get("CAMPSCOUT_CAMPGROUNDS") or None,
        help="path to campgrounds.yaml (env: CAMPSCOUT_CAMPGROUNDS)",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("campgrounds", help="list configured campgrounds")
    p.set_defaults(func=cmd_campgrounds)

    p = sub.add_parser("maps", help="show / download official site maps")
    p.add_argument("--download", action="store_true", help="save the map PDFs locally")
    p.add_argument("--out", type=Path, help="download directory")
    p.set_defaults(func=cmd_maps)

    p = sub.add_parser("discover", help="resolve place/facility IDs from the API")
    p.add_argument("--lat", type=float, default=NORTH_COUNTY_LAT)
    p.add_argument("--lon", type=float, default=NORTH_COUNTY_LON)
    p.add_argument("--limit", type=int, default=50, help="max nearby places")
    p.add_argument("--filter", help="only show parks whose name contains this")
    p.add_argument("--write", action="store_true", help="save IDs into data/campgrounds.yaml")
    p.set_defaults(func=cmd_discover)

    p = sub.add_parser("sites", help="dump the live site roster for one campground")
    p.add_argument("campground", help="campground key, e.g. san_elijo")
    p.add_argument("--json", type=Path, help="also write the roster to this JSON file")
    p.set_defaults(func=cmd_sites)

    p = sub.add_parser("scan", help="run one pass and notify")
    p.add_argument("--dry-run", action="store_true", help="print instead of sending")
    p.add_argument(
        "--fail-if-none",
        action="store_true",
        help="exit 3 when nothing is available (for scripting; off by default so cron stays quiet)",
    )
    p.set_defaults(func=cmd_scan)

    p = sub.add_parser("watch", help="poll on an interval")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_watch)

    p = sub.add_parser("status", help="is it actually running? when did it last check?")
    p.add_argument(
        "--check",
        action="store_true",
        help="probe mode: one line, exit non-zero only if scans are stale "
        "(for k8s liveness probes and healthchecks)",
    )
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("test-notify", help="send a fake alert to check your notifier setup")
    p.set_defaults(func=cmd_test_notify)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _setup_logging(args.verbose)

    try:
        config = load_config(config_path=args.config, campgrounds_path=args.campgrounds)
    except (OSError, ValueError, KeyError) as exc:
        log.error("could not load config: %s", exc)
        return 2

    try:
        return args.func(args, config)
    except KeyboardInterrupt:
        log.info("stopped")
        return 130
    except KeyError as exc:
        log.error("%s", exc)
        return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
