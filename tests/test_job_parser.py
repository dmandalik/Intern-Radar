from __future__ import annotations

import unittest
from datetime import UTC, datetime

from internradar.core.models import Company, Job, RawJob
from internradar.parsers.job_parser import generate_stable_job_id, normalize_raw_job


class TestJobParser(unittest.TestCase):
    def test_same_ats_id_produces_same_stable_id(self) -> None:
        company = Company(id="hudson-river-trading", name="Hudson River Trading")
        first = RawJob(
            source_type="greenhouse",
            source_name="Greenhouse",
            company_id=company.id,
            company_name=company.name,
            title="Software Engineer Intern",
            url="https://boards.greenhouse.io/hrt/jobs/123?gh_jid=123",
            raw_payload={"id": 123},
        )
        second = RawJob(
            source_type="greenhouse",
            source_name="Greenhouse",
            company_id=company.id,
            company_name=company.name,
            title="Software Engineer Intern",
            url="https://boards.greenhouse.io/hrt/jobs/123?ref=homepage",
            raw_payload={"id": 123},
        )

        self.assertEqual(
            generate_stable_job_id(first, company=company),
            generate_stable_job_id(second, company=company),
        )

    def test_different_urls_produce_different_ids_when_no_ats_id_exists(self) -> None:
        company = Company(id="example", name="Example")
        first = RawJob(
            source_type="custom_page",
            source_name="Custom Career Page",
            company_id=company.id,
            company_name=company.name,
            title="Software Engineer Intern",
            url="https://example.com/jobs/1",
        )
        second = RawJob(
            source_type="custom_page",
            source_name="Custom Career Page",
            company_id=company.id,
            company_name=company.name,
            title="Software Engineer Intern",
            url="https://example.com/jobs/2",
        )

        self.assertNotEqual(
            generate_stable_job_id(first, company=company),
            generate_stable_job_id(second, company=company),
        )

    def test_normalize_raw_job_creates_valid_job(self) -> None:
        company = Company(
            id="hudson-river-trading",
            name="Hudson River Trading",
            default_prestige_tier="S+",
        )
        raw_job = RawJob(
            source_type="greenhouse",
            source_name="Greenhouse",
            company_id=company.id,
            company_name=company.name,
            title="<b>Software Engineer Intern</b> - Summer 2027",
            url="https://boards.greenhouse.io/hrt/jobs/123?utm_source=test",
            apply_url="https://boards.greenhouse.io/hrt/jobs/123/apply?utm_campaign=test",
            location_raw="New York, NY / Chicago, IL",
            description_raw="<p>Work on low latency trading systems in C++.</p>",
            department="Engineering",
            posted_at=datetime(2026, 4, 1, 12, 0, tzinfo=UTC),
            raw_payload={"id": 123},
        )

        job = normalize_raw_job(raw_job, company=company)
        payload = job.model_dump(mode="json")

        self.assertIsInstance(job, Job)
        self.assertEqual(job.company_id, company.id)
        self.assertEqual(job.title, "Software Engineer Intern - Summer 2027")
        self.assertEqual(job.description, "Work on low latency trading systems in C++.")
        self.assertEqual(job.apply_url, "https://boards.greenhouse.io/hrt/jobs/123/apply")
        self.assertEqual(job.source_url, "https://boards.greenhouse.io/hrt/jobs/123")
        self.assertEqual(job.season, "summer")
        self.assertEqual(job.year, 2027)
        self.assertEqual(job.locations, ["New York, NY", "Chicago, IL"])
        self.assertIsNone(job.remote_type)
        self.assertEqual(job.role.role_family, "unknown")
        self.assertEqual(job.role.confidence, 0.0)
        self.assertEqual(job.status.status, "unknown")
        self.assertEqual(job.scores.opportunity_score, 0.0)
        self.assertEqual(job.prestige_tier, "S+")
        self.assertTrue(job.id.startswith("hudson-river-trading-greenhouse-123"))
        self.assertIsNotNone(job.content_hash)
        self.assertEqual(payload["season"], "summer")
        self.assertEqual(payload["locations"], ["New York, NY", "Chicago, IL"])

    def test_normalize_raw_job_handles_missing_optional_fields(self) -> None:
        raw_job = RawJob(
            source_type="custom_page",
            source_name="Custom Career Page",
            company_name="Example Company",
            title="Internship 2027",
            url="https://example.com/jobs/internship",
        )

        job = normalize_raw_job(raw_job)

        self.assertEqual(job.company_id, "example-company")
        self.assertEqual(job.company_name, "Example Company")
        self.assertEqual(job.apply_url, "")
        self.assertEqual(job.source_url, "https://example.com/jobs/internship")
        self.assertEqual(job.year, 2027)
        self.assertEqual(job.locations, [])
        self.assertIsNone(job.remote_type)
        self.assertIsNone(job.description)

    def test_normalized_job_is_json_serializable(self) -> None:
        raw_job = RawJob(
            source_type="lever",
            source_name="Lever",
            company_name="Example Company",
            title="Software Engineer Intern",
            url="https://jobs.example.com/posting/1",
            description_raw="<p>Build systems.</p>",
        )

        payload = normalize_raw_job(raw_job).model_dump(mode="json")

        self.assertEqual(payload["title"], "Software Engineer Intern")
        self.assertEqual(payload["description"], "Build systems.")
        self.assertIn("first_seen", payload)
        self.assertEqual(payload["status"]["status"], "unknown")

    def test_existing_job_preserves_first_seen(self) -> None:
        original_first_seen = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        raw_job = RawJob(
            source_type="lever",
            source_name="Lever",
            company_name="Example Company",
            title="Software Engineer Intern",
            url="https://jobs.example.com/posting/1",
            raw_payload={"id": "abc123"},
        )
        existing = normalize_raw_job(raw_job)
        existing.first_seen = original_first_seen

        updated = normalize_raw_job(raw_job, existing_job=existing)

        self.assertEqual(updated.first_seen, original_first_seen)
