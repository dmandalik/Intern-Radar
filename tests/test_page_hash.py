from __future__ import annotations

import unittest

from internradar.verification.page_hash import hash_job_content, hash_text


class TestPageHash(unittest.TestCase):
    def test_same_text_gives_same_hash(self) -> None:
        self.assertEqual(hash_text("Apply now"), hash_text("Apply now"))

    def test_different_text_gives_different_hash(self) -> None:
        self.assertNotEqual(hash_text("Apply now"), hash_text("Applications closed"))

    def test_whitespace_normalization_is_stable(self) -> None:
        self.assertEqual(hash_text("Apply   now"), hash_text("Apply now"))

    def test_hash_job_content_is_deterministic(self) -> None:
        self.assertEqual(
            hash_job_content("Role", "Description", "https://example.com/job/1"),
            hash_job_content("Role", "Description", "https://example.com/job/1/"),
        )
