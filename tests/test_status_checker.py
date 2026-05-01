from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from internradar.core.models import RawJob
from internradar.verification.status_checker import check_job_status


class TestStatusChecker(unittest.TestCase):
    def _raw_job(self, source_type: str = "custom_page") -> RawJob:
        return RawJob(
            source_type=source_type,
            source_name=source_type,
            company_name="Example",
            title="Software Engineer Intern",
            url="https://example.com/jobs/1",
        )

    def test_apply_signal_returns_open_or_likely_open(self) -> None:
        status = check_job_status(
            self._raw_job(),
            page_text="Apply now using the application form.",
            http_status=200,
        )

        self.assertIn(status.status, {"open", "likely_open"})
        self.assertTrue(status.evidence)

    def test_active_ats_listing_returns_open_or_likely_open(self) -> None:
        status = check_job_status(
            self._raw_job(source_type="greenhouse"),
            page_text="Software Engineer Intern",
            listed_in_current_source=True,
        )

        self.assertIn(status.status, {"open", "likely_open"})

    def test_404_returns_closed(self) -> None:
        status = check_job_status(self._raw_job(), http_status=404)

        self.assertEqual(status.status, "closed")
        self.assertGreaterEqual(status.confidence, 0.95)

    def test_closed_text_returns_closed(self) -> None:
        status = check_job_status(
            self._raw_job(),
            page_text="This job is closed and no longer accepting applications.",
        )

        self.assertEqual(status.status, "closed")

    def test_coming_soon_text_returns_coming_soon(self) -> None:
        status = check_job_status(
            self._raw_job(),
            page_text="Applications will open later. Check back soon.",
        )

        self.assertEqual(status.status, "coming_soon")

    def test_login_required_text_returns_requires_login(self) -> None:
        status = check_job_status(
            self._raw_job(),
            page_text="Login to apply. Sign in to continue.",
        )

        self.assertEqual(status.status, "requires_login")

    def test_weak_no_signal_does_not_return_high_confidence_open(self) -> None:
        status = check_job_status(
            self._raw_job(),
            page_text="Learn more about the company.",
            http_status=200,
            listed_in_current_source=False,
        )

        self.assertIn(status.status, {"unknown", "likely_open"})
        self.assertLess(status.confidence, 0.8)

    def test_evidence_is_nonempty_for_signal_based_statuses(self) -> None:
        status = check_job_status(
            self._raw_job(),
            page_text="Applications are closed.",
        )

        self.assertTrue(status.evidence)

    def test_status_checker_handles_empty_text_safely(self) -> None:
        status = check_job_status(self._raw_job(), page_text=None)

        self.assertEqual(status.status, "unknown")

    def test_old_unlisted_job_can_be_marked_stale(self) -> None:
        raw_job = self._raw_job()
        raw_job.posted_at = datetime.now(UTC) - timedelta(days=200)

        status = check_job_status(raw_job, listed_in_current_source=False)

        self.assertEqual(status.status, "stale")
