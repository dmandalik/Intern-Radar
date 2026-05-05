from __future__ import annotations

import unittest
from datetime import UTC, datetime

from typer.testing import CliRunner

from internradar.cli import app
from internradar.core.database import initialize_database, load_user_actions, upsert_jobs
from internradar.core.models import ClassifiedRole, EligibilityInfo, Job, JobScores, JobStatusInfo


def make_job(*, job_id: str = "job-review", status: str = "unknown", role_confidence: float = 0.4) -> Job:
    now = datetime(2026, 5, 4, 12, 0, tzinfo=UTC)
    return Job(
        id=job_id,
        company_id="firm",
        company_name="Example Firm",
        title="Review Me",
        description="Build systems in C++.",
        apply_url="https://example.com/apply",
        source_url="https://example.com/source",
        source_type="greenhouse",
        role=ClassifiedRole(role_family="software_engineer_trading", confidence=role_confidence, evidence=["weak"]),
        season=None,
        year=None,
        locations=["New York, NY"],
        remote_type="onsite",
        status=JobStatusInfo(status=status, confidence=0.3, evidence=["unclear"], checked_at=now),
        eligibility=EligibilityInfo(confidence=0.2),
        scores=JobScores(hidden_gem_score=85.0, opportunity_score=90.0, explanation=["High score"]),
        prestige_tier="A",
        tags=[],
        first_seen=now,
        last_seen=now,
        last_verified=now,
        content_hash="hash-review",
    )


class TestReviewCommand(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = CliRunner()

    def test_review_command_can_mark_saved(self) -> None:
        with self.runner.isolated_filesystem():
            initialize_database()
            upsert_jobs([make_job()])

            result = self.runner.invoke(app, ["review", "--limit", "1"], input="s\n")
            state = load_user_actions()["job-review"]

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Marked saved.", result.stdout)
        self.assertEqual(state["application_status"], "saved")

    def test_review_command_can_add_notes(self) -> None:
        with self.runner.isolated_filesystem():
            initialize_database()
            upsert_jobs([make_job()])

            result = self.runner.invoke(app, ["review", "--limit", "1"], input="e\nNeed to verify location\n")
            state = load_user_actions()["job-review"]

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Saved notes.", result.stdout)
        self.assertEqual(state["notes"], "Need to verify location")
