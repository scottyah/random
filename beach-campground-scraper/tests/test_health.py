"""Tests for the "is it actually running?" machinery.

The failure mode these guard against: a dead scraper is silent, and a
campground with no openings is also silent. Those must not be confusable.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from campscout.config import Campground, Config, SearchWindow
from campscout.heartbeat import Heartbeat, build_heartbeat
from campscout.providers import ReserveCaliforniaError
from campscout.scan import scan
from campscout.state import AlertState

HOUR = 3600.0


class TestHeartbeatState(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "state.json"

    def tearDown(self):
        self.dir.cleanup()

    def test_never_run_is_stale(self):
        state = AlertState(self.path)
        self.assertIsNone(state.last_success)
        self.assertTrue(state.is_stale(3.0))

    def test_recent_success_is_not_stale(self):
        state = AlertState(self.path)
        state.record_run(ok=True, pairs_found=0, sites_checked=170, now=1000)
        self.assertFalse(state.is_stale(3.0, now=1000 + HOUR))
        self.assertTrue(state.is_stale(3.0, now=1000 + 4 * HOUR))

    def test_failed_run_does_not_refresh_success(self):
        state = AlertState(self.path)
        state.record_run(ok=True, now=1000)
        state.record_run(ok=False, error="API down", now=1000 + 5 * HOUR)
        # A failing run must not make things look healthy.
        self.assertEqual(state.last_success, 1000)
        self.assertTrue(state.is_stale(3.0, now=1000 + 5 * HOUR))
        self.assertEqual(state.runs["last_error"], "API down")

    def test_counters_accumulate_and_persist(self):
        state = AlertState(self.path)
        state.record_run(ok=True, pairs_found=2, sites_checked=170, now=1000)
        state.record_alert(2, now=1000)
        state.record_run(ok=True, pairs_found=0, sites_checked=170, now=2000)
        state.save()

        reloaded = AlertState(self.path)
        self.assertEqual(reloaded.runs["total_scans"], 2)
        self.assertEqual(reloaded.runs["total_alerts"], 2)
        self.assertEqual(reloaded.runs["last_pairs_found"], 0)
        self.assertEqual(reloaded.last_success, 2000)

    def test_seconds_since_helpers(self):
        state = AlertState(self.path)
        self.assertIsNone(state.seconds_since_attempt())
        self.assertIsNone(state.seconds_since_alert())
        state.record_run(ok=True, now=1000)
        state.record_alert(1, now=1000)
        self.assertAlmostEqual(state.seconds_since_attempt(now=1600), 600)
        self.assertAlmostEqual(state.seconds_since_alert(now=1600), 600)

    def test_corrupt_state_reports_never_run_rather_than_healthy(self):
        self.path.write_text("{ garbage", encoding="utf-8")
        state = AlertState(self.path)
        # Must fail safe: unknown health reads as stale, never as OK.
        self.assertTrue(state.is_stale(3.0))


class TestHeartbeatPing(unittest.TestCase):
    def test_disabled_when_no_url(self):
        self.assertFalse(build_heartbeat({}).enabled)
        self.assertFalse(build_heartbeat(None).enabled)

    def test_fail_url_derived_from_url(self):
        hb = build_heartbeat({"url": "https://hc-ping.com/abc"})
        self.assertTrue(hb.enabled)
        self.assertEqual(hb.fail_url, "https://hc-ping.com/abc/fail")

    def test_explicit_fail_url_wins(self):
        hb = build_heartbeat({"url": "https://x/a", "fail_url": "https://x/b"})
        self.assertEqual(hb.fail_url, "https://x/b")

    def test_ping_failure_is_swallowed(self):
        # An unreachable heartbeat must never break the scan it reports on.
        hb = Heartbeat(url="http://127.0.0.1:1/never", timeout=0.2)
        self.assertFalse(hb.success())


class _BrokenClient:
    """Every campground lookup fails."""

    def __init__(self):
        self.calls = 0

    def availability(self, facility_id, start, end):
        self.calls += 1
        raise ReserveCaliforniaError("connection refused")

    def booking_url(self, place_id, facility_id):
        return ""


class TestScanStats(unittest.TestCase):
    def _config(self, facility_id="999"):
        return Config(
            campgrounds=[
                Campground.from_dict(
                    {"key": "t", "name": "T", "facility_id": facility_id}
                )
            ],
            windows=[SearchWindow(label="w", nights=2, checkin=date(2026, 9, 4))],
        )

    def test_total_api_failure_is_distinguishable_from_no_availability(self):
        client = _BrokenClient()
        stats: dict = {}
        hits = scan(self._config(), client=client, today=date(2026, 8, 1), stats=stats)

        # Same empty result as "nothing available"...
        self.assertEqual(hits, [])
        # ...but the stats make the difference unambiguous.
        self.assertEqual(stats["campgrounds_ok"], 0)
        self.assertEqual(stats["campgrounds_attempted"], 1)
        self.assertTrue(stats["errors"])
        self.assertIn("connection refused", stats["errors"][0])

    def test_unconfigured_campground_is_recorded_as_an_error(self):
        config = Config(
            campgrounds=[Campground.from_dict({"key": "t", "name": "T"})],
            windows=[SearchWindow(label="w", nights=2, checkin=date(2026, 9, 4))],
        )
        stats: dict = {}
        scan(config, client=_BrokenClient(), today=date(2026, 8, 1), stats=stats)
        self.assertEqual(stats["campgrounds_ok"], 0)
        self.assertIn("facility_id", stats["errors"][0])

    def test_no_search_windows_is_recorded_as_an_error(self):
        config = Config(
            campgrounds=[Campground.from_dict({"key": "t", "name": "T", "facility_id": "9"})],
            windows=[],
        )
        stats: dict = {}
        scan(config, client=_BrokenClient(), today=date(2026, 8, 1), stats=stats)
        self.assertTrue(stats["errors"])

    def test_successful_scan_reports_sites_checked(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from test_end_to_end import StubClient

        client = StubClient({})
        stats: dict = {}
        scan(self._config(), client=client, today=date(2026, 8, 1), stats=stats)
        self.assertEqual(stats["campgrounds_ok"], 1)
        self.assertEqual(stats["sites_checked"], 20)
        self.assertEqual(stats["errors"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
