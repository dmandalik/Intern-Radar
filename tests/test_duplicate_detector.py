from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from internradar.core.models import ClassifiedRole, EligibilityInfo, Job, JobScores, JobStatusInfo
from internradar.verification.duplicate_detector import deduplicate_jobs, find_duplicates


class TestDuplicateDetector(unittest.TestCase):
    def _job(
        self,
        *,
        company_id: str = "company-1",
        title: str = "Software Engineer Intern, Trading Systems",
        source_type: str = "greenhouse",
        apply_url: str = "https://example.com/jobs/1/apply",
        source_url: str = "https://example.com/jobs/1",
        season: str | None = "summer",
        year: int | None = 2027,
        description: str | None = "Short description.",
        first_seen: datetime | None = None,
        last_seen: datetime | None = None,
        last_verified: datetime | None = None,
        locations: list[str] | None = None,
    ) -> Job:
        now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        return Job(
            id=f"{company_id}-{source_type}-{title[:8]}",
            company_id=company_id,
            company_name=company_id,
            title=title,
            description=description,
            apply_url=apply_url,
            source_url=source_url,
            source_type=source_type,
            role=ClassifiedRole(role_family="unknown", confidence=0.0),
            season=season,
            year=year,
            locations=locations or ["New York, NY"],
            remote_type=None,
            status=JobStatusInfo(status="unknown", confidence=0.2, checked_at=now),
            eligibility=EligibilityInfo(),
            scores=JobScores(),
            first_seen=first_seen or now,
            last_seen=last_seen or now,
            last_verified=last_verified or now,
            content_hash="abc123",
        )

    def test_same_apply_url_merges(self) -> None:
        jobs = [
            self._job(apply_url="https://example.com/jobs/1/apply?utm_source=x"),
            self._job(apply_url="https://example.com/jobs/1/apply"),
        ]

        groups = find_duplicates(jobs)

        self.assertEqual(len(groups), 1)
        self.assertIn("same canonical apply URL", groups[0].reasons)

    def test_same_source_url_merges(self) -> None:
        jobs = [
            self._job(source_url="https://example.com/jobs/1?utm_source=x", title="Software Engineer Intern"),
            self._job(source_url="https://example.com/jobs/1", title="Software Engineer Intern"),
        ]

        self.assertEqual(len(find_duplicates(jobs)), 1)

    def test_same_listing_source_url_with_different_titles_does_not_merge(self) -> None:
        jobs = [
            self._job(
                source_type="custom_page",
                source_url="https://imc.com/us/search-careers",
                apply_url="",
                title="Principal Machine Learning Engineer",
            ),
            self._job(
                source_type="custom_page",
                source_url="https://imc.com/us/search-careers",
                apply_url="",
                title="Software Engineer – AI Powered Engineering",
            ),
        ]

        self.assertEqual(find_duplicates(jobs), [])

    def test_same_ats_id_merges(self) -> None:
        jobs = [
            self._job(
                source_type="greenhouse",
                source_url="https://boards.greenhouse.io/example/jobs/123",
                apply_url="https://boards.greenhouse.io/example/jobs/123/apply",
            ),
            self._job(
                source_type="greenhouse",
                source_url="https://job-boards.greenhouse.io/example/jobs/123",
                apply_url="https://job-boards.greenhouse.io/example/jobs/123/apply",
            ),
        ]

        groups = find_duplicates(jobs)

        self.assertEqual(len(groups), 1)
        self.assertIn("same ATS job ID", groups[0].reasons)

    def test_similar_title_same_company_merges(self) -> None:
        jobs = [
            self._job(title="Software Engineer Intern, Trading Systems"),
            self._job(title="Software Engineering Intern - Trading Systems"),
        ]

        self.assertEqual(len(find_duplicates(jobs)), 1)

    def test_same_title_different_company_does_not_merge(self) -> None:
        jobs = [
            self._job(company_id="company-1"),
            self._job(company_id="company-2"),
        ]

        self.assertEqual(find_duplicates(jobs), [])

    def test_similar_title_different_season_does_not_merge_without_url_match(self) -> None:
        jobs = [
            self._job(
                title="Software Engineer Intern",
                season="summer",
                year=2027,
                source_url="https://example.com/jobs/1",
                apply_url="https://example.com/jobs/1/apply",
            ),
            self._job(
                title="Software Engineering Intern",
                season="fall",
                year=2028,
                source_url="https://example.com/jobs/2",
                apply_url="https://example.com/jobs/2/apply",
            ),
        ]

        self.assertEqual(find_duplicates(jobs), [])

    def test_richer_description_is_preserved(self) -> None:
        short = self._job(description="Short.")
        rich = self._job(description="A much richer description with more implementation detail.")

        merged = deduplicate_jobs([short, rich])[0]

        self.assertEqual(merged.description, rich.description)

    def test_first_seen_and_last_seen_are_preserved(self) -> None:
        now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        early = self._job(first_seen=now - timedelta(days=5), last_seen=now - timedelta(days=2))
        late = self._job(first_seen=now - timedelta(days=1), last_seen=now + timedelta(days=3))

        merged = deduplicate_jobs([early, late])[0]

        self.assertEqual(merged.first_seen, early.first_seen)
        self.assertEqual(merged.last_seen, late.last_seen)

    def test_duplicate_detection_is_deterministic(self) -> None:
        jobs = [
            self._job(title="Software Engineer Intern, Trading Systems"),
            self._job(title="Software Engineering Intern - Trading Systems"),
        ]

        first = [job.id for job in deduplicate_jobs(jobs)]
        second = [job.id for job in deduplicate_jobs(jobs)]

        self.assertEqual(first, second)

    def test_merge_prefers_specific_source_and_apply_urls(self) -> None:
        generic = self._job(
            source_type="custom_page",
            title="Principal Machine Learning Engineer",
            source_url="https://imc.com/us/search-careers",
            apply_url="https://imc.com/us/search-careers",
            description="Listing description.",
        )
        specific = self._job(
            source_type="custom_page",
            title="Principal Machine Learning Engineer",
            source_url="https://imc.com/us/careers/jobs/4721116101",
            apply_url="https://imc.com/us/careers/jobs/4721116101/apply",
            description="Full role description with details.",
        )

        merged = deduplicate_jobs([generic, specific])[0]

        self.assertEqual(merged.source_url, "https://imc.com/us/careers/jobs/4721116101")
        self.assertEqual(merged.apply_url, "https://imc.com/us/careers/jobs/4721116101/apply")
