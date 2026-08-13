"""Logic tests. No network: the provider is exercised against canned JSON."""

from __future__ import annotations

import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from campscout.adjacency import AdjacencyModel, parse_number_spec, parse_pair_spec
from campscout.config import SearchWindow, load_config
from campscout.desirability import DesirabilityModel
from campscout.geo import haversine_meters, percentile
from campscout.models import Site, Stay, parse_site_number
from campscout.providers import ReserveCalifornia
from campscout.scan import bookable_sites, find_pairs_for_campground
from campscout.state import AlertState


def site(number: int, unit_id: str | None = None, lat=None, lon=None) -> Site:
    return Site(
        facility_id="1",
        unit_id=unit_id or str(number),
        name=f"Site {number:03d}",
        number=number,
        lat=lat,
        lon=lon,
    )


class TestParsing(unittest.TestCase):
    def test_site_number_formats(self):
        self.assertEqual(parse_site_number("082"), 82)
        self.assertEqual(parse_site_number("Site 82"), 82)
        self.assertEqual(parse_site_number("Campsite 12A"), 12)
        self.assertIsNone(parse_site_number("Hike & Bike"))
        self.assertIsNone(parse_site_number(""))

    def test_number_spec(self):
        self.assertEqual(parse_number_spec("1-5"), {1, 2, 3, 4, 5})
        self.assertEqual(parse_number_spec("47,49,51"), {47, 49, 51})
        self.assertEqual(parse_number_spec("1-3,10"), {1, 2, 3, 10})
        self.assertEqual(parse_number_spec("5-3"), {3, 4, 5})  # reversed range
        self.assertEqual(parse_number_spec(None), set())
        self.assertEqual(parse_number_spec(7), {7})


class TestAdjacency(unittest.TestCase):
    def test_consecutive_numbers_are_adjacent(self):
        model = AdjacencyModel(mode="numeric")
        self.assertTrue(model.are_adjacent(site(10), site(11)))
        self.assertFalse(model.are_adjacent(site(10), site(12)))

    def test_groups_prevent_cross_loop_pairs(self):
        model = AdjacencyModel.from_config({"mode": "numeric", "groups": ["1-43", "44-99"]})
        # 43 and 44 are consecutive but sit in different loops.
        self.assertFalse(model.are_adjacent(site(43), site(44)))
        self.assertTrue(model.are_adjacent(site(42), site(43)))

    def test_breaks_and_extra_pairs(self):
        model = AdjacencyModel.from_config(
            {"mode": "numeric", "breaks": ["20-21"], "extra_pairs": ["47-49"]}
        )
        self.assertFalse(model.are_adjacent(site(20), site(21)))
        self.assertTrue(model.are_adjacent(site(47), site(49)))

    def test_geo_adjacency(self):
        # ~22m apart in latitude.
        a = site(1, lat=33.0000, lon=-117.3000)
        b = site(50, lat=33.0002, lon=-117.3000)
        model = AdjacencyModel(mode="geo", max_meters=35)
        self.assertTrue(model.are_adjacent(a, b))

        far = site(51, lat=33.0100, lon=-117.3000)
        self.assertFalse(model.are_adjacent(a, far))

    def test_either_mode_catches_both(self):
        model = AdjacencyModel(mode="either", max_meters=35)
        self.assertTrue(model.are_adjacent(site(10), site(11)))
        self.assertTrue(
            model.are_adjacent(
                site(10, lat=33.0, lon=-117.3), site(80, lat=33.0002, lon=-117.3)
            )
        )

    def test_site_is_not_adjacent_to_itself(self):
        model = AdjacencyModel(mode="either")
        self.assertFalse(model.are_adjacent(site(10), site(10)))

    def test_pairs_enumerates_each_once(self):
        model = AdjacencyModel(mode="numeric")
        pairs = model.pairs([site(1), site(2), site(3)])
        self.assertEqual(len(pairs), 2)
        self.assertEqual([(a.number, b.number) for a, b in pairs], [(1, 2), (2, 3)])

    def test_invalid_mode_rejected(self):
        with self.assertRaises(ValueError):
            AdjacencyModel.from_config({"mode": "telepathy"})

    def test_pair_spec_treats_dash_as_and_not_range(self):
        # "47-49" is the pair {47,49}, NOT the range 47..49.
        self.assertEqual(parse_pair_spec("47-49"), frozenset({47, 49}))
        self.assertEqual(parse_pair_spec("20,21"), frozenset({20, 21}))
        self.assertEqual(parse_pair_spec([47, 49]), frozenset({47, 49}))

    def test_malformed_break_rejected(self):
        with self.assertRaises(ValueError):
            AdjacencyModel.from_config({"breaks": ["1,2,3"]})  # 3 sites, not a pair
        with self.assertRaises(ValueError):
            AdjacencyModel.from_config({"breaks": ["7-7"]})  # same site twice


class TestDesirability(unittest.TestCase):
    def setUp(self):
        self.model = DesirabilityModel.from_config(
            {
                "default": 15,
                "tiers": [
                    {"score": 100, "label": "bluff-front", "sites": "145-171"},
                    {"score": 90, "label": "ocean side", "sites": "1-43"},
                    {"score": 45, "label": "hookups", "sites": "101-116"},
                ],
                "exclude": {"sites": "94,128"},
            }
        )

    def test_first_matching_tier_wins(self):
        scored = self.model.score_all([site(150), site(20), site(105), site(200)])
        self.assertEqual(scored["150"], (100, "bluff-front"))
        self.assertEqual(scored["20"], (90, "ocean side"))
        self.assertEqual(scored["105"], (45, "hookups"))
        self.assertEqual(scored["200"][0], 15)

    def test_excluded_sites_filtered_out(self):
        keep = self.model.filter_sites([site(150), site(94), site(128)], min_score=0)
        self.assertIn("150", keep)
        self.assertNotIn("94", keep)
        self.assertNotIn("128", keep)

    def test_min_score_filter(self):
        keep = self.model.filter_sites([site(150), site(20), site(105)], min_score=90)
        self.assertEqual(set(keep), {"150", "20"})

    def test_geo_rule_detects_westernmost(self):
        model = DesirabilityModel.from_config(
            {"default": 10, "geo": {"mode": "west_percentile", "percentile": 50, "score": 100}}
        )
        # Ten sites in a west-to-east strip; the west half should be boosted.
        sites = [site(i, lat=33.0, lon=-117.30 - (10 - i) * 0.0005) for i in range(1, 11)]
        scored = model.score_all(sites)
        west = [s for s in sites if scored[s.unit_id][0] == 100]
        self.assertTrue(west)
        # Everything boosted must be west of everything not boosted.
        east_lons = [s.lon for s in sites if scored[s.unit_id][0] != 100]
        self.assertTrue(all(w.lon <= min(east_lons) for w in west))

    def test_geo_never_lowers_a_curated_score(self):
        model = DesirabilityModel.from_config(
            {
                "default": 10,
                "tiers": [{"score": 100, "label": "curated", "sites": "1-3"}],
                "geo": {"mode": "west_percentile", "percentile": 50, "score": 60},
            }
        )
        # Site 1 is curated at 100 but sits on the east (unboosted) side.
        sites = [site(i, lat=33.0, lon=-117.30 + i * 0.001) for i in range(1, 11)]
        scored = model.score_all(sites)
        self.assertEqual(scored["1"], (100, "curated"))

    def test_geo_ignored_when_too_few_located_sites(self):
        model = DesirabilityModel.from_config(
            {"default": 10, "geo": {"mode": "west_percentile", "percentile": 50, "score": 100}}
        )
        sites = [site(1, lat=33.0, lon=-117.3), site(2, lat=33.0, lon=-117.2)]
        scored = model.score_all(sites)
        self.assertTrue(all(v[0] == 10 for v in scored.values()))


class TestStays(unittest.TestCase):
    def test_weekday_window_expands_to_fridays(self):
        window = SearchWindow(
            label="weekend",
            nights=2,
            weekdays=[4],
            start=date(2026, 8, 1),
            end=date(2026, 8, 31),
        )
        stays = window.stays(today=date(2026, 7, 1))
        self.assertTrue(stays)
        self.assertTrue(all(s.checkin.weekday() == 4 for s in stays))
        self.assertTrue(all(s.nights == 2 for s in stays))

    def test_explicit_checkin(self):
        window = SearchWindow(label="labor day", nights=3, checkin=date(2026, 9, 4))
        stays = window.stays(today=date(2026, 8, 1))
        self.assertEqual(len(stays), 1)
        self.assertEqual(stays[0].checkout, date(2026, 9, 7))

    def test_past_dates_are_skipped(self):
        window = SearchWindow(label="x", nights=1, start=date(2026, 1, 1), end=date(2026, 1, 10))
        self.assertEqual(window.stays(today=date(2026, 6, 1)), [])

    def test_occupied_nights(self):
        stay = Stay(checkin=date(2026, 8, 14), nights=2)
        self.assertEqual(stay.occupied_nights(), [date(2026, 8, 14), date(2026, 8, 15)])


class TestBookable(unittest.TestCase):
    def test_requires_every_night(self):
        stay = Stay(checkin=date(2026, 8, 14), nights=2)
        free = {
            "a": {date(2026, 8, 14), date(2026, 8, 15)},
            "b": {date(2026, 8, 14)},  # Saturday already taken
            "c": {date(2026, 8, 14), date(2026, 8, 15), date(2026, 8, 16)},
        }
        self.assertEqual(bookable_sites(free, stay), {"a", "c"})

    def test_allowed_filter(self):
        stay = Stay(checkin=date(2026, 8, 14), nights=1)
        free = {"a": {date(2026, 8, 14)}, "b": {date(2026, 8, 14)}}
        self.assertEqual(bookable_sites(free, stay, allowed={"a"}), {"a"})


class TestFindPairs(unittest.TestCase):
    def _campground(self, **overrides):
        from campscout.config import Campground

        cfg = {
            "key": "test",
            "name": "Test Beach",
            "facility_id": "1",
            "adjacency": {"mode": "numeric"},
            "desirability": {
                "default": 10,
                "tiers": [{"score": 100, "label": "oceanfront", "sites": "1-10"}],
            },
        }
        cfg.update(overrides)
        return Campground.from_dict(cfg)

    def test_finds_adjacent_desirable_pair(self):
        cg = self._campground()
        sites = {str(n): site(n) for n in (1, 2, 50, 51)}
        night = date(2026, 8, 14)
        free = {uid: {night} for uid in sites}
        stays = [Stay(checkin=night, nights=1)]

        hits = find_pairs_for_campground(cg, sites, free, stays, min_score=90)
        self.assertEqual(len(hits), 1)
        self.assertEqual({hits[0].site_a.number, hits[0].site_b.number}, {1, 2})

    def test_no_pair_when_only_one_side_free(self):
        cg = self._campground()
        sites = {str(n): site(n) for n in (1, 2)}
        night = date(2026, 8, 14)
        free = {"1": {night}, "2": set()}
        hits = find_pairs_for_campground(cg, sites, free, [Stay(night, 1)], min_score=90)
        self.assertEqual(hits, [])

    def test_no_pair_when_neighbour_is_undesirable(self):
        # Site 10 is oceanfront, 11 is not; they are adjacent but 11 fails min_score.
        cg = self._campground()
        sites = {str(n): site(n) for n in (10, 11)}
        night = date(2026, 8, 14)
        free = {uid: {night} for uid in sites}
        hits = find_pairs_for_campground(cg, sites, free, [Stay(night, 1)], min_score=90)
        self.assertEqual(hits, [])

    def test_dedupe_key_is_order_independent(self):
        cg = self._campground()
        sites = {str(n): site(n) for n in (1, 2)}
        night = date(2026, 8, 14)
        free = {uid: {night} for uid in sites}
        hits = find_pairs_for_campground(cg, sites, free, [Stay(night, 1)], min_score=90)
        key = hits[0].dedupe_key
        self.assertIn("|1|2", key)


class TestGridParsing(unittest.TestCase):
    """Canned UseDirect grid payload -> Sites + free dates."""

    GRID = {
        "Facility": {
            "FacilityId": 674,
            "Name": "Test Campground",
            "Units": {
                "100": {
                    "UnitId": 100,
                    "Name": "Site 001",
                    "ShortName": "001",
                    "IsAda": False,
                    "AllowWebBooking": True,
                    "VehicleLength": 24,
                    "MapInfo": {"Latitude": 33.01, "Longitude": -117.31},
                    "Slices": {
                        "2026-08-14": {"Date": "2026-08-14", "IsFree": True, "IsBlocked": False},
                        "2026-08-15": {"Date": "2026-08-15", "IsFree": True, "IsBlocked": False},
                    },
                },
                "101": {
                    "UnitId": 101,
                    "Name": "Site 002",
                    "ShortName": "002",
                    "AllowWebBooking": True,
                    "MapInfo": {},
                    "Slices": {
                        # Free but blocked, and walk-in only: neither is bookable.
                        "2026-08-14": {"Date": "2026-08-14", "IsFree": True, "IsBlocked": True},
                        "2026-08-15": {"Date": "2026-08-15", "IsFree": True, "IsWalkin": True},
                    },
                },
                "102": {
                    "UnitId": 102,
                    "Name": "Site 003",
                    "ShortName": "003",
                    "AllowWebBooking": False,  # not web-bookable, must be dropped
                    "Slices": {"2026-08-14": {"Date": "2026-08-14", "IsFree": True}},
                },
            },
        }
    }

    def test_parses_units_and_slices(self):
        client = ReserveCalifornia.__new__(ReserveCalifornia)  # no network setup
        units = ReserveCalifornia._units_from_grid(self.GRID)
        self.assertEqual(len(units), 3)

        parsed = [ReserveCalifornia._site_from_unit("674", u) for u in units]
        by_id = {s.unit_id: s for s in parsed}
        self.assertEqual(by_id["100"].number, 1)
        self.assertEqual(by_id["100"].lat, 33.01)
        self.assertEqual(by_id["100"].vehicle_length, 24)
        self.assertIsNone(by_id["101"].lat)
        self.assertFalse(by_id["102"].web_bookable)
        del client

    def test_availability_respects_blocked_and_walkin(self):
        client = ReserveCalifornia.__new__(ReserveCalifornia)
        client.grid = lambda facility_id, start, end: self.GRID  # type: ignore[method-assign]

        sites, free = ReserveCalifornia.availability(
            client, "674", date(2026, 8, 14), date(2026, 8, 16)
        )
        self.assertIn("100", sites)
        self.assertNotIn("102", sites)  # dropped: not web bookable
        self.assertEqual(free["100"], {date(2026, 8, 14), date(2026, 8, 15)})
        self.assertEqual(free["101"], set())  # blocked + walk-in


class TestState(unittest.TestCase):
    def setUp(self):
        import tempfile

        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "state.json"

    def tearDown(self):
        self.dir.cleanup()

    def test_cooldown(self):
        state = AlertState(self.path, cooldown_hours=12)
        self.assertTrue(state.should_notify("k", now=1000))
        state.mark_notified(["k"], now=1000)
        self.assertFalse(state.should_notify("k", now=1000 + 3600))
        self.assertTrue(state.should_notify("k", now=1000 + 13 * 3600))

    def test_roundtrip(self):
        state = AlertState(self.path, cooldown_hours=12)
        state.mark_notified(["k"], now=1000)
        state.save()
        reloaded = AlertState(self.path, cooldown_hours=12)
        self.assertFalse(reloaded.should_notify("k", now=2000))

    def test_corrupt_file_does_not_crash(self):
        self.path.write_text("{ not json", encoding="utf-8")
        state = AlertState(self.path, cooldown_hours=12)
        self.assertTrue(state.should_notify("anything"))

    def test_prune(self):
        state = AlertState(self.path, cooldown_hours=12)
        state.mark_notified(["old"], now=0)
        state.mark_notified(["new"], now=100 * 24 * 3600)
        removed = state.prune(keep_seconds=90 * 24 * 3600, now=100 * 24 * 3600)
        self.assertEqual(removed, 1)


class TestGeo(unittest.TestCase):
    def test_haversine_known_distance(self):
        # 0.001 degrees of latitude is ~111m.
        d = haversine_meters(33.0, -117.0, 33.001, -117.0)
        self.assertAlmostEqual(d, 111.2, delta=1.0)

    def test_percentile(self):
        self.assertEqual(percentile([1, 2, 3, 4, 5], 0), 1)
        self.assertEqual(percentile([1, 2, 3, 4, 5], 100), 5)
        self.assertEqual(percentile([1, 2, 3, 4, 5], 50), 3)


class TestBundledConfig(unittest.TestCase):
    """The shipped campgrounds.yaml must actually load and be sane."""

    def test_loads(self):
        config = load_config(config_path=Path("/nonexistent-config.yaml"))
        keys = {c.key for c in config.campgrounds}
        self.assertIn("san_elijo", keys)
        self.assertIn("south_carlsbad", keys)
        self.assertIn("san_onofre_bluffs", keys)

    def test_san_elijo_scoring_matches_research(self):
        config = load_config(config_path=Path("/nonexistent-config.yaml"))
        cg = config.campground("san_elijo")
        scored = cg.desirability.score_all([site(150), site(20), site(105), site(300)])
        self.assertEqual(scored["150"][0], 100)  # bluff-front 145-171
        self.assertEqual(scored["20"][0], 90)  # ocean side 1-43
        self.assertEqual(scored["105"][0], 45)  # inland hookups
        self.assertEqual(scored["300"][0], 15)  # default

    def test_san_elijo_excludes_group_and_hikebike(self):
        config = load_config(config_path=Path("/nonexistent-config.yaml"))
        cg = config.campground("san_elijo")
        self.assertTrue(cg.desirability.is_excluded(site(94)))
        self.assertTrue(cg.desirability.is_excluded(site(128)))
        self.assertFalse(cg.desirability.is_excluded(site(150)))

    def test_shipped_ids_look_like_real_api_ids(self):
        # IDs were resolved from the live API via `discover --write` on
        # 2026-08-12 (Tyler-hosted ReserveCalifornia backend). Anything
        # non-numeric here (CHANGEME, null) means someone hand-edited badly.
        config = load_config(config_path=Path("/nonexistent-config.yaml"))
        for cg in config.campgrounds:
            if not cg.enabled:
                continue
            self.assertTrue(cg.facility_ids, f"{cg.key} lost its facility_ids")
            for fid in cg.facility_ids:
                self.assertTrue(fid.isdigit(), f"{cg.key}: bad facility_id {fid!r}")
            self.assertTrue(
                cg.place_id and cg.place_id.isdigit(), f"{cg.key}: bad place_id"
            )

    def test_san_elijo_watches_every_section(self):
        # San Elijo is three facilities. The score-100 bluff-front row
        # (sites 145-171) is in the Northern Section (666); watching only
        # the discover-default Middle Section would silently miss it.
        config = load_config(config_path=Path("/nonexistent-config.yaml"))
        cg = config.campground("san_elijo")
        self.assertIn("666", cg.facility_ids)
        self.assertGreaterEqual(len(cg.facility_ids), 3)


class TestMultiFacility(unittest.TestCase):
    def test_facility_ids_list_and_singular_shorthand(self):
        from campscout.config import Campground

        multi = Campground.from_dict({"key": "m", "facility_ids": [665, 666]})
        self.assertEqual(multi.facility_ids, ["665", "666"])
        self.assertEqual(multi.facility_id, "665")
        self.assertTrue(multi.configured)

        single = Campground.from_dict({"key": "s", "facility_id": "42"})
        self.assertEqual(single.facility_ids, ["42"])
        self.assertTrue(single.configured)

    def test_scan_merges_facilities_so_pairs_span_sections(self):
        """Two adjacent free sites split across facilities must still pair."""
        import tempfile

        import yaml

        from campscout.scan import scan

        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "config.yaml"
            cfg.write_text(
                yaml.safe_dump(
                    {
                        "search": {
                            "min_score": 0,
                            "horizon_days": 30,
                            "windows": [{"label": "w", "nights": 2, "weekdays": [4]}],
                        },
                        "paths": {"state": str(Path(tmp) / "state.json")},
                    }
                ),
                encoding="utf-8",
            )
            cg = Path(tmp) / "campgrounds.yaml"
            cg.write_text(
                yaml.safe_dump(
                    {
                        "campgrounds": [
                            {
                                "key": "split",
                                "name": "Split Park",
                                "place_id": "7",
                                "facility_ids": ["100", "200"],
                                "adjacency": {"mode": "numeric"},
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            config = load_config(config_path=cfg, campgrounds_path=cg)

        per_facility = {
            "100": site(10, unit_id="u10"),
            "200": site(11, unit_id="u11"),
        }

        class StubClient:
            calls: list[str] = []

            def availability(self, facility_id, start, end):
                self.calls.append(facility_id)
                s = per_facility[facility_id]
                nights = {start + timedelta(days=i) for i in range((end - start).days)}
                return {s.unit_id: s}, {s.unit_id: set(nights)}

            def booking_url(self, place_id, facility_id):
                return f"https://example.test/{place_id}/{facility_id}"

        stats: dict = {}
        hits = scan(config, client=StubClient(), today=date(2026, 8, 12), stats=stats)
        self.assertEqual(StubClient.calls, ["100", "200"])
        self.assertEqual(stats["campgrounds_ok"], 1)
        self.assertEqual(stats["sites_checked"], 2)
        self.assertTrue(hits, "adjacent pair spanning two facilities was not found")
        numbers = {s.number for h in hits for s in (h.site_a, h.site_b)}
        self.assertEqual(numbers, {10, 11})


if __name__ == "__main__":
    unittest.main(verbosity=2)
