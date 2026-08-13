"""Full pipeline test against a stubbed ReserveCalifornia backend.

The live API was unreachable from the authoring environment, so this stands in
for it: a realistic grid payload flows through availability parsing,
desirability scoring, adjacency detection, dedupe state and notification.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from campscout.config import Campground, Config, SearchWindow
from campscout.notify import format_body, format_subject
from campscout.providers import ReserveCalifornia
from campscout.scan import scan
from campscout.state import AlertState

CHECKIN = date(2026, 9, 4)  # a Friday


class StubClient(ReserveCalifornia):
    """A ReserveCalifornia that answers from a canned layout, no network."""

    def __init__(self, free_numbers: dict[int, list[date]], with_coords: bool = True):
        self.free_numbers = free_numbers
        self.with_coords = with_coords
        self.grid_calls = 0

    def grid(self, facility_id, start, end):  # type: ignore[override]
        self.grid_calls += 1
        units = {}
        # 20 sites in a north-south strip: evens on the ocean (west) side,
        # odds inland, mirroring how these bluff campgrounds are laid out.
        for number in range(1, 21):
            lon = -117.3200 if number % 2 == 0 else -117.3180
            lat = 33.0100 + number * 0.00012
            slices = {}
            cur = start
            while cur < end:
                is_free = cur in self.free_numbers.get(number, [])
                slices[cur.isoformat()] = {
                    "Date": cur.isoformat(),
                    "IsFree": is_free,
                    "IsBlocked": False,
                }
                cur += timedelta(days=1)
            units[str(number)] = {
                "UnitId": number,
                "Name": f"Site {number:03d}",
                "ShortName": f"{number:03d}",
                "AllowWebBooking": True,
                "MapInfo": {"Latitude": lat, "Longitude": lon} if self.with_coords else {},
                "Slices": slices,
            }
        return {"Facility": {"FacilityId": facility_id, "Units": units}}

    def booking_url(self, place_id, facility_id):  # type: ignore[override]
        return f"https://example.test/park/{place_id}/{facility_id}"


def make_config(min_score: int = 90, adjacency: dict | None = None) -> Config:
    campground = Campground.from_dict(
        {
            "key": "test_beach",
            "name": "Test State Beach",
            "facility_id": "999",
            "place_id": "111",
            "adjacency": adjacency or {"mode": "numeric"},
            "desirability": {
                "default": 10,
                "geo": {"mode": "west_percentile", "percentile": 50, "score": 100},
            },
        }
    )
    return Config(
        campgrounds=[campground],
        windows=[SearchWindow(label="weekend", nights=2, checkin=CHECKIN)],
        min_score=min_score,
    )


class TestEndToEnd(unittest.TestCase):
    def test_finds_adjacent_oceanfront_pair(self):
        # Sites 8 and 10 (both ocean-side evens) are open for both nights.
        nights = [CHECKIN, CHECKIN + timedelta(days=1)]
        client = StubClient({8: nights, 10: nights, 9: nights})
        # 9 is inland (odd) so 8+9 and 9+10 must be rejected on desirability;
        # 8+10 is rejected on adjacency under numeric mode.
        config = make_config(adjacency={"mode": "numeric"})
        hits = scan(config, client=client, today=date(2026, 8, 1))
        self.assertEqual(hits, [])

        # With the odd/even road crossing declared, 8+10 becomes a real pair.
        config = make_config(adjacency={"mode": "numeric", "extra_pairs": ["8-10"]})
        hits = scan(config, client=client, today=date(2026, 8, 1))
        self.assertEqual(len(hits), 1)
        self.assertEqual({hits[0].site_a.number, hits[0].site_b.number}, {8, 10})
        self.assertEqual(hits[0].min_score, 100)
        self.assertIn("example.test", hits[0].booking_url)

    def test_geo_adjacency_finds_neighbours_without_number_rules(self):
        nights = [CHECKIN, CHECKIN + timedelta(days=1)]
        client = StubClient({8: nights, 10: nights})
        # Sites 8 and 10 are ~27m apart in the stub layout.
        config = make_config(adjacency={"mode": "geo", "max_meters": 35})
        hits = scan(config, client=client, today=date(2026, 8, 1))
        self.assertEqual(len(hits), 1)
        self.assertEqual({hits[0].site_a.number, hits[0].site_b.number}, {8, 10})

    def test_partial_night_coverage_is_not_a_hit(self):
        # Both ocean-side and adjacent, but site 10 is only free the first night.
        client = StubClient({8: [CHECKIN, CHECKIN + timedelta(days=1)], 10: [CHECKIN]})
        config = make_config(adjacency={"mode": "geo", "max_meters": 35})
        hits = scan(config, client=client, today=date(2026, 8, 1))
        self.assertEqual(hits, [])

    def test_undesirable_pair_is_ignored(self):
        nights = [CHECKIN, CHECKIN + timedelta(days=1)]
        # 7 and 9 are both inland (odd/east), so they never clear min_score.
        client = StubClient({7: nights, 9: nights})
        config = make_config(adjacency={"mode": "numeric", "extra_pairs": ["7-9"]})
        hits = scan(config, client=client, today=date(2026, 8, 1))
        self.assertEqual(hits, [])

    def test_falls_back_to_numbers_when_api_gives_no_coordinates(self):
        nights = [CHECKIN, CHECKIN + timedelta(days=1)]
        client = StubClient({8: nights, 9: nights}, with_coords=False)
        campground = Campground.from_dict(
            {
                "key": "test_beach",
                "name": "Test State Beach",
                "facility_id": "999",
                "adjacency": {"mode": "either"},
                "desirability": {
                    "default": 10,
                    "tiers": [{"score": 95, "label": "curated ocean row", "sites": "1-12"}],
                    "geo": {"mode": "west_percentile", "percentile": 50, "score": 100},
                },
            }
        )
        config = Config(
            campgrounds=[campground],
            windows=[SearchWindow(label="w", nights=2, checkin=CHECKIN)],
            min_score=90,
        )
        hits = scan(config, client=client, today=date(2026, 8, 1))
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].reason_a, "curated ocean row")

    def test_dedupe_suppresses_repeat_alerts(self):
        nights = [CHECKIN, CHECKIN + timedelta(days=1)]
        client = StubClient({8: nights, 10: nights})
        config = make_config(adjacency={"mode": "geo", "max_meters": 35})
        hits = scan(config, client=client, today=date(2026, 8, 1))
        self.assertEqual(len(hits), 1)

        with tempfile.TemporaryDirectory() as tmp:
            state = AlertState(Path(tmp) / "state.json", cooldown_hours=12)
            key = hits[0].dedupe_key
            self.assertTrue(state.should_notify(key))
            state.mark_notified([key])
            self.assertFalse(state.should_notify(key))

            # Same find on the next poll must not re-alert.
            again = scan(config, client=client, today=date(2026, 8, 1))
            self.assertFalse(state.should_notify(again[0].dedupe_key))

    def test_message_formatting(self):
        nights = [CHECKIN, CHECKIN + timedelta(days=1)]
        client = StubClient({8: nights, 10: nights})
        config = make_config(adjacency={"mode": "geo", "max_meters": 35})
        hits = scan(config, client=client, today=date(2026, 8, 1))
        subject = format_subject(hits)
        body = format_body(hits)
        self.assertIn("Test State Beach", subject)
        self.assertIn("Site 008", body)
        self.assertIn("Site 010", body)
        self.assertIn("example.test", body)

    def test_long_horizon_is_chunked(self):
        client = StubClient({})
        config = Config(
            campgrounds=[
                Campground.from_dict(
                    {"key": "t", "name": "T", "facility_id": "9", "adjacency": {"mode": "numeric"}}
                )
            ],
            windows=[SearchWindow(label="w", nights=2, weekdays=[4])],
            horizon_days=180,
        )
        scan(config, client=client, today=date(2026, 8, 1))
        # ~180 days at 30 days per request.
        self.assertGreaterEqual(client.grid_calls, 6)

    def test_unconfigured_campground_is_skipped_not_fatal(self):
        client = StubClient({})
        config = Config(
            campgrounds=[Campground.from_dict({"key": "t", "name": "T"})],  # no facility_id
            windows=[SearchWindow(label="w", nights=2, checkin=CHECKIN)],
        )
        self.assertEqual(scan(config, client=client, today=date(2026, 8, 1)), [])
        self.assertEqual(client.grid_calls, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
