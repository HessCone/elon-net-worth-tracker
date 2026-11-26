#!/usr/bin/env python3
"""Unit tests for the Forbes parser. The fixture is a captured public response."""
import json
import os
import sys
import unittest
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import fetch

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixture_rtb.json")


def load_fixture():
    with open(FIXTURE, encoding="utf-8") as handle:
        return json.loads(handle.read(), parse_float=Decimal)


class FetchTests(unittest.TestCase):
    def setUp(self):
        self.fx = load_fixture()
        self.parsed = fetch.parse_rtb_entry(self.fx, "forbes-profile", fetch.PROFILE_URL)

    def test_fixture_is_elon_realtime(self):
        self.assertIsNotNone(self.parsed)
        self.assertEqual(self.parsed["name"], "Elon Musk")
        self.assertFalse(self.parsed["fallback"])
        self.assertEqual(self.parsed["source_id"], "forbes-profile")

    def test_holdings_sum_matches_forbes_total(self):
        rows, private, included, note = fetch.build_holdings(self.parsed)
        self.assertTrue(included, note)
        self.assertIsNotNone(private)
        worth = fetch.millions_to_usd(self.fx["finalWorth"])
        gap = abs(sum(row["value_usd"] for row in rows) + private - worth)
        self.assertLessEqual(gap, 1000)
        kinds = {(row["company"], row["kind"]) for row in rows}
        self.assertIn(("Tesla", "shares"), kinds)
        self.assertTrue(any(row["kind"] == "options" for row in rows))

    def test_millions_conversion(self):
        self.assertEqual(fetch.millions_to_usd(Decimal("1.5")), 1_500_000)
        self.assertEqual(fetch.millions_to_usd(Decimal("0.0000015")), 2)

    def test_rejects_other_people(self):
        other = dict(self.fx)
        other["personName"] = "Someone Else"
        other["uri"] = "someone-else"
        self.assertIsNone(fetch.parse_rtb_entry(other, "forbes-profile", fetch.PROFILE_URL))

    def test_ajax_fallback_has_total_only(self):
        change = self.fx["finalWorth"] - self.fx["estWorthPrev"]
        ajax = {
            "name": "Elon Musk",
            "uri": "elon-musk",
            "worth": self.fx["finalWorth"],
            "worthChange": change,
            "timestamp": self.fx["timestamp"],
            "rank": self.fx["rank"],
        }
        parsed = fetch.parse_ajax_entry(ajax, fetch.AJAX_URL)
        self.assertTrue(parsed["fallback"])
        self.assertIsNone(parsed["financial_assets"])
        rows, private, included, note = fetch.build_holdings(parsed)
        self.assertFalse(included)
        self.assertEqual(rows, [])
        self.assertIn("total only", note)
        self.assertEqual(
            fetch.millions_to_usd(parsed["worth_millions"]),
            fetch.millions_to_usd(self.fx["finalWorth"]),
        )

    def test_seed_keeps_points_an_hour_apart(self):
        points = fetch.seed_points(self.fx["wealthHistory"])
        self.assertGreater(len(points), 40)
        stamps = [fetch.parse_time(point["t"]) for point in points]
        self.assertEqual(stamps, sorted(stamps))
        gaps = [b - a for a, b in zip(stamps, stamps[1:])]
        self.assertTrue(all(gap >= fetch.SEED_GAP_SEC for gap in gaps))
        self.assertTrue(any(3600 <= gap <= 3700 for gap in gaps))
        self.assertTrue(all(point["seeded"] and point["rounded"] for point in points))

    def test_live_point_replaces_nearby_rounded_seed(self):
        seeded = fetch.seed_points(self.fx["wealthHistory"])
        last = seeded[-1]
        live_time = fetch.iso_from_ms(fetch.parse_time(last["t"]) * 1000 + 60_000)
        live = fetch.history_point(live_time, last["worth_usd"] + 1000, "forbes-profile", False, False)
        merged = fetch.upsert_live(seeded, live)
        self.assertEqual(len(merged), len(seeded))
        self.assertFalse(merged[-1]["seeded"])
        self.assertEqual(merged[-1]["worth_usd"], live["worth_usd"])

    def test_profile_wrapper(self):
        payload = {"person": {"name": "Elon Musk", "uri": "elon-musk", "personLists": [self.fx]}}
        parsed = fetch.parse_profile(payload, fetch.PROFILE_URL)
        self.assertEqual(parsed["source_id"], "forbes-profile")
        worth = fetch.validate(parsed, now=__import__("datetime").datetime(2026, 11, 26, 2, 0, tzinfo=__import__("datetime").timezone.utc))
        self.assertGreater(worth, fetch.MIN_USD)


if __name__ == "__main__":
    unittest.main()
