from __future__ import annotations

import unittest

from internradar.verification.url_utils import (
    canonicalize_url,
    extract_domain,
    safe_url_hash,
    same_canonical_url,
)


class TestUrlUtils(unittest.TestCase):
    def test_canonicalize_removes_trailing_slash(self) -> None:
        self.assertEqual(
            canonicalize_url("https://Example.com/jobs/123/"),
            "https://example.com/jobs/123",
        )

    def test_canonicalize_removes_utm_params(self) -> None:
        self.assertEqual(
            canonicalize_url("https://example.com/jobs/123/?utm_source=x&utm_medium=y&id=1"),
            "https://example.com/jobs/123?id=1",
        )

    def test_canonicalize_preserves_important_path(self) -> None:
        self.assertEqual(
            canonicalize_url("https://example.com/jobs/path/to/posting/?id=1"),
            "https://example.com/jobs/path/to/posting?id=1",
        )

    def test_same_canonical_url_detects_equivalent_urls(self) -> None:
        self.assertTrue(
            same_canonical_url(
                "https://example.com/jobs/123/?utm_source=x",
                "https://EXAMPLE.com/jobs/123",
            ),
        )

    def test_invalid_or_empty_urls_are_handled_safely(self) -> None:
        self.assertEqual(canonicalize_url(None), "")
        self.assertEqual(canonicalize_url(""), "")
        self.assertEqual(extract_domain(None), "")
        self.assertEqual(safe_url_hash(""), "")
