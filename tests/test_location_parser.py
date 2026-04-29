from __future__ import annotations

import unittest

from internradar.parsers.location_parser import parse_location


class TestLocationParser(unittest.TestCase):
    def test_splits_locations_on_slash(self) -> None:
        result = parse_location("New York, NY / Chicago, IL")

        self.assertEqual(result.locations, ["New York, NY", "Chicago, IL"])
        self.assertIsNone(result.remote_type)

    def test_splits_locations_on_semicolon(self) -> None:
        result = parse_location("New York, NY; London, UK")

        self.assertEqual(result.locations, ["New York, NY", "London, UK"])

    def test_detects_remote(self) -> None:
        result = parse_location("Remote")

        self.assertEqual(result.locations, ["Remote"])
        self.assertEqual(result.remote_type, "remote")

    def test_detects_hybrid_and_strips_prefix(self) -> None:
        result = parse_location("Hybrid - Chicago")

        self.assertEqual(result.locations, ["Chicago"])
        self.assertEqual(result.remote_type, "hybrid")

    def test_preserves_unknown_location(self) -> None:
        result = parse_location("United States")

        self.assertEqual(result.locations, ["United States"])
        self.assertIsNone(result.remote_type)
