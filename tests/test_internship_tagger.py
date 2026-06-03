from __future__ import annotations

import unittest

from internradar.parsers.internship_tagger import (
    INTERNSHIP_TAG,
    apply_internship_tag,
    detect_internship,
)


class TestInternshipTagger(unittest.TestCase):
    def test_detects_plain_internship_title(self) -> None:
        result = detect_internship("Quantitative Research Intern")
        self.assertTrue(result.is_internship)
        self.assertEqual(result.program_type, "internship")
        self.assertEqual(result.confidence, 0.95)

    def test_detects_internship_word_variants(self) -> None:
        for title in ("Software Internship - Summer 2026", "Trading Interns Wanted", "Intern, Engineering"):
            with self.subTest(title=title):
                self.assertTrue(detect_internship(title).is_internship)

    def test_detects_co_op_variants(self) -> None:
        for title in ("Engineering Co-op", "Software Coop", "Hardware Co op"):
            with self.subTest(title=title):
                self.assertTrue(detect_internship(title).is_internship)

    def test_detects_summer_analyst(self) -> None:
        self.assertTrue(detect_internship("2026 Summer Analyst Program").is_internship)

    def test_detects_uk_placement_and_vacation_scheme(self) -> None:
        for title in (
            "Industrial Placement - Quant",
            "Placement Year Student",
            "Vacation Scheme 2026",
            "Spring Week Insight",
            "Insight Programme",
        ):
            with self.subTest(title=title):
                self.assertTrue(detect_internship(title).is_internship)

    def test_detects_multilingual_internships(self) -> None:
        for title in (
            "Praktikum Quantitative Research",
            "Werkstudent Softwareentwicklung",
            "Stagiaire Développeur",
            "Becario de Trading",
            "Prácticas de Verano",
            "Tirocinio Quantitativo",
            "Estágio em Engenharia",
            "实习生",
            "サマーインターンシップ",
            "여름 인턴십",
        ):
            with self.subTest(title=title):
                self.assertTrue(detect_internship(title).is_internship)

    def test_does_not_flag_full_time_titles(self) -> None:
        for title in (
            "Quantitative Researcher",
            "Software Engineer",
            "New Grad Software Engineer",
            "Graduate Program 2026",
            "Senior Developer",
        ):
            with self.subTest(title=title):
                self.assertFalse(detect_internship(title).is_internship)

    def test_guards_against_substring_false_positives(self) -> None:
        for title in (
            "Internal Audit Manager",
            "International Markets Analyst",
            "Staging Environment Engineer",
            "Cooperative Strategy Lead",
        ):
            with self.subTest(title=title):
                self.assertFalse(detect_internship(title).is_internship)

    def test_bare_english_stage_is_not_an_internship(self) -> None:
        result = detect_internship(
            "Commodities Broker Trader",
            "You will manage risk at every stage of the trade lifecycle.",
        )
        self.assertFalse(result.is_internship)

    def test_passing_mention_of_internships_does_not_flag_full_time_role(self) -> None:
        result = detect_internship(
            "Quantitative Python Developer",
            "We also offer internships and graduate roles across the firm.",
        )
        self.assertFalse(result.is_internship)

    def test_role_defining_description_phrase_flags_internship(self) -> None:
        for description in (
            "This is a 10-week internship based in New York.",
            "Join our summer internship program for students.",
            "Apply to the internship position today.",
        ):
            with self.subTest(description=description):
                self.assertTrue(detect_internship("Some Title", description).is_internship)

    def test_description_match_has_lower_confidence(self) -> None:
        result = detect_internship(
            "Quantitative Developer",
            "This role can convert from our summer internship program.",
        )
        self.assertTrue(result.is_internship)
        self.assertEqual(result.confidence, 0.6)

    def test_title_match_outweighs_description(self) -> None:
        result = detect_internship("Trading Intern", "Full description here.")
        self.assertEqual(result.confidence, 0.95)

    def test_apply_internship_tag_merges_tag_once(self) -> None:
        is_internship, tags = apply_internship_tag("Research Intern", None, ["quant"])
        self.assertTrue(is_internship)
        self.assertIn(INTERNSHIP_TAG, tags)
        self.assertEqual(tags.count(INTERNSHIP_TAG), 1)

    def test_apply_internship_tag_does_not_duplicate_existing(self) -> None:
        is_internship, tags = apply_internship_tag("Research Intern", None, [INTERNSHIP_TAG])
        self.assertTrue(is_internship)
        self.assertEqual(tags.count(INTERNSHIP_TAG), 1)

    def test_apply_internship_tag_leaves_non_internship_untouched(self) -> None:
        is_internship, tags = apply_internship_tag("Senior Engineer", None, ["quant"])
        self.assertFalse(is_internship)
        self.assertNotIn(INTERNSHIP_TAG, tags)


if __name__ == "__main__":
    unittest.main()
