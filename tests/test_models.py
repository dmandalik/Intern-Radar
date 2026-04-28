from __future__ import annotations

import unittest
from datetime import UTC, datetime

from pydantic import ValidationError

from internradar.core.models import (
    ClassifiedRole,
    Company,
    EligibilityInfo,
    Job,
    JobScores,
    JobStatusInfo,
    RawJob,
)


class TestCoreModels(unittest.TestCase):
    def test_company_can_be_created_with_minimal_fields(self) -> None:
        company = Company(id="company-1", name="Example Company")

        self.assertEqual(company.id, "company-1")
        self.assertEqual(company.name, "Example Company")
        self.assertEqual(company.aliases, [])
        self.assertEqual(company.categories, [])

    def test_raw_job_stores_raw_payload(self) -> None:
        raw_job = RawJob(
            source_type="ats",
            source_name="example-source",
            company_name="Example Company",
            title="Software Engineer Intern",
            url="https://example.com/jobs/1",
            raw_payload={"job_id": 123, "extra": {"team": "platform"}},
        )

        self.assertEqual(raw_job.raw_payload["job_id"], 123)
        self.assertEqual(raw_job.raw_payload["extra"]["team"], "platform")

    def test_job_status_info_rejects_invalid_statuses(self) -> None:
        with self.assertRaises(ValidationError):
            JobStatusInfo(
                status="not_a_real_status",
                confidence=0.5,
                checked_at=datetime.now(UTC),
            )

    def test_job_scores_default_all_scores_to_zero(self) -> None:
        scores = JobScores()

        self.assertEqual(scores.prestige_score, 0.0)
        self.assertEqual(scores.role_fit_score, 0.0)
        self.assertEqual(scores.technical_depth_score, 0.0)
        self.assertEqual(scores.hidden_gem_score, 0.0)
        self.assertEqual(scores.freshness_score, 0.0)
        self.assertEqual(scores.eligibility_score, 0.0)
        self.assertEqual(scores.opportunity_score, 0.0)
        self.assertEqual(scores.explanation, [])

    def test_eligibility_info_defaults_unknown_optional_fields(self) -> None:
        eligibility = EligibilityInfo()

        self.assertEqual(eligibility.degree_levels, [])
        self.assertEqual(eligibility.graduation_years, [])
        self.assertEqual(eligibility.majors, [])
        self.assertIsNone(eligibility.citizenship_requirement)
        self.assertIsNone(eligibility.sponsorship)
        self.assertIsNone(eligibility.minimum_gpa)
        self.assertEqual(eligibility.class_years, [])
        self.assertFalse(eligibility.requires_phd)
        self.assertFalse(eligibility.requires_masters)
        self.assertIsNone(eligibility.undergrad_friendly)
        self.assertIsNone(eligibility.freshman_sophomore_friendly)
        self.assertEqual(eligibility.confidence, 0.0)
        self.assertEqual(eligibility.raw_evidence, [])

    def test_full_job_can_be_created_and_serialized(self) -> None:
        now = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
        job = Job(
            id="job-1",
            company_id="company-1",
            company_name="Example Company",
            title="Software Engineer Intern",
            description="Build systems.",
            apply_url="https://example.com/apply",
            source_url="https://example.com/jobs/1",
            source_type="ats",
            role=ClassifiedRole(
                role_family="software_engineering",
                role_subtype="backend",
                confidence=0.92,
                evidence=["software engineer", "backend"],
            ),
            season="summer",
            year=2026,
            locations=["New York, NY"],
            remote_type="hybrid",
            status=JobStatusInfo(
                status="open",
                confidence=0.95,
                evidence=["active posting"],
                checked_at=now,
            ),
            eligibility=EligibilityInfo(
                degree_levels=["bachelors"],
                graduation_years=[2027],
                undergrad_friendly=True,
            ),
            scores=JobScores(role_fit_score=0.8, explanation=["Matches engineering focus"]),
            prestige_tier="tier_2",
            tags=["internship", "backend"],
            first_seen=now,
            last_seen=now,
            last_verified=now,
            content_hash="abc123",
        )

        payload = job.model_dump(mode="json")

        self.assertEqual(payload["id"], "job-1")
        self.assertEqual(payload["role"]["role_family"], "software_engineering")
        self.assertEqual(payload["status"]["status"], "open")
        self.assertEqual(payload["eligibility"]["graduation_years"], [2027])
        self.assertEqual(payload["first_seen"], "2026-01-15T12:00:00Z")

    def test_mutable_fields_do_not_share_state(self) -> None:
        first_company = Company(id="company-1", name="First")
        second_company = Company(id="company-2", name="Second")
        first_company.aliases.append("Alias One")

        first_job = RawJob(
            source_type="ats",
            source_name="source-a",
            company_name="First",
            title="Role A",
            url="https://example.com/a",
        )
        second_job = RawJob(
            source_type="ats",
            source_name="source-b",
            company_name="Second",
            title="Role B",
            url="https://example.com/b",
        )
        first_job.raw_payload["id"] = 1

        self.assertEqual(second_company.aliases, [])
        self.assertEqual(second_job.raw_payload, {})
