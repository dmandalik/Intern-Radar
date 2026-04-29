from __future__ import annotations

import unittest

from internradar.parsers.season_parser import parse_season_and_year


class TestSeasonParser(unittest.TestCase):
    def test_parses_explicit_season_and_year_from_title(self) -> None:
        result = parse_season_and_year("Software Engineer Intern - Summer 2027", None)

        self.assertEqual(result.season, "summer")
        self.assertEqual(result.year, 2027)
        self.assertGreater(result.confidence, 0.9)

    def test_parses_year_only(self) -> None:
        result = parse_season_and_year("2027 Software Engineer Intern", None)

        self.assertIsNone(result.season)
        self.assertEqual(result.year, 2027)

    def test_infers_season_from_month(self) -> None:
        result = parse_season_and_year("Software Engineer Internship", "Program starts in June 2027.")

        self.assertEqual(result.season, "summer")
        self.assertEqual(result.year, 2027)

    def test_returns_none_values_when_no_season_or_year_exists(self) -> None:
        result = parse_season_and_year("Software Engineer Intern", "Build systems.")

        self.assertIsNone(result.season)
        self.assertIsNone(result.year)
        self.assertEqual(result.confidence, 0.0)

    def test_prefers_title_evidence_over_description(self) -> None:
        result = parse_season_and_year(
            "Summer Analyst 2027",
            "This role is also listed as Fall 2028 in some materials.",
        )

        self.assertEqual(result.season, "summer")
        self.assertEqual(result.year, 2027)
