from __future__ import annotations

import unittest

from internradar.parsers.text_cleaner import clean_text, clean_text_lower


class TestTextCleaner(unittest.TestCase):
    def test_clean_text_strips_html_and_scripts(self) -> None:
        value = "<div><script>alert(1)</script><p>Work on <b>systems</b>.</p></div>"

        self.assertEqual(clean_text(value), "Work on systems .")

    def test_clean_text_normalizes_whitespace(self) -> None:
        value = "Software\xa0Engineer\n\nIntern"

        self.assertEqual(clean_text(value), "Software Engineer Intern")

    def test_clean_text_preserves_programming_terms(self) -> None:
        value = "<p>Work on low latency trading systems in C++, C#, F#, and .NET.</p>"

        cleaned = clean_text(value)

        self.assertIn("C++", cleaned)
        self.assertIn("C#", cleaned)
        self.assertIn("F#", cleaned)
        self.assertIn(".NET", cleaned)

    def test_clean_text_returns_empty_string_for_none(self) -> None:
        self.assertEqual(clean_text(None), "")
        self.assertEqual(clean_text(""), "")

    def test_clean_text_lower_casefolds_cleaned_text(self) -> None:
        self.assertEqual(clean_text_lower("<p>Software Engineer Intern</p>"), "software engineer intern")
