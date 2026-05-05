from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from internradar.core.database import initialize_database, load_user_actions, upsert_jobs
from internradar.core.models import ClassifiedRole, EligibilityInfo, Job, JobScores, JobStatusInfo
from internradar.review.user_actions import add_job_notes, set_job_action


def make_job(job_id: str = "job-1") -> Job:
    now = datetime(2026, 5, 4, 12, 0, tzinfo=UTC)
    return Job(
        id=job_id,
        company_id="firm",
        company_name="Example Firm",
        title="Software Engineer Intern",
        description="Build systems in C++ and Python.",
        apply_url=f"https://example.com/{job_id}/apply",
        source_url=f"https://example.com/{job_id}",
        source_type="greenhouse",
        role=ClassifiedRole(role_family="software_engineer_trading", confidence=0.9, evidence=["classified"]),
        season="Summer",
        year=2027,
        locations=["New York, NY"],
        remote_type="onsite",
        status=JobStatusInfo(status="open", confidence=0.9, evidence=["listed"], checked_at=now),
        eligibility=EligibilityInfo(confidence=0.2),
        scores=JobScores(),
        prestige_tier="A",
        tags=[],
        first_seen=now,
        last_seen=now,
        last_verified=now,
        content_hash=f"hash-{job_id}",
    )


class TestUserActions(unittest.TestCase):
    def test_create_saved_action(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cwd = Path(temp_dir)
            initialize_database(cwd)
            upsert_jobs([make_job()], cwd=cwd)

            state = set_job_action("job-1", action="saved", cwd=cwd)

            self.assertEqual(state["application_status"], "saved")
            self.assertEqual(state["saved"], "true")
            self.assertIn("created_at", state)
            self.assertIn("updated_at", state)

    def test_update_user_action_from_saved_to_applied(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cwd = Path(temp_dir)
            initialize_database(cwd)
            upsert_jobs([make_job()], cwd=cwd)

            set_job_action("job-1", action="saved", cwd=cwd)
            state = set_job_action("job-1", action="applied", cwd=cwd)

            self.assertEqual(state["application_status"], "applied")
            self.assertEqual(state["saved"], "true")
            self.assertEqual(state["applied"], "true")

    def test_add_notes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cwd = Path(temp_dir)
            initialize_database(cwd)
            upsert_jobs([make_job()], cwd=cwd)

            state = add_job_notes("job-1", notes="Applied with systems resume.", cwd=cwd)

            self.assertEqual(state["notes"], "Applied with systems resume.")

    def test_actions_persist_across_db_reload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cwd = Path(temp_dir)
            initialize_database(cwd)
            upsert_jobs([make_job()], cwd=cwd)

            set_job_action("job-1", action="saved", cwd=cwd)
            add_job_notes("job-1", notes="Follow up next week.", cwd=cwd)

            state = load_user_actions(cwd=cwd)["job-1"]
            self.assertEqual(state["application_status"], "saved")
            self.assertEqual(state["notes"], "Follow up next week.")
