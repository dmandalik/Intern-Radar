from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from internradar.core.database import (
    complete_scan_run,
    create_scan_run,
    initialize_database,
    load_jobs_by_ids,
    upsert_jobs,
)
from internradar.core.models import ClassifiedRole, EligibilityInfo, Job, JobScores, JobStatusInfo


def _build_job(*, description: str = "Build low latency systems.", last_seen: datetime | None = None) -> Job:
    now = last_seen or datetime(2026, 4, 30, 12, 0, tzinfo=UTC)
    return Job(
        id="hudson-river-trading-greenhouse-123",
        company_id="hudson-river-trading",
        company_name="Hudson River Trading",
        title="Software Engineer Intern, Trading Systems",
        description=description,
        apply_url="https://boards.greenhouse.io/hrt/jobs/123/apply",
        source_url="https://boards.greenhouse.io/hrt/jobs/123",
        source_type="greenhouse",
        role=ClassifiedRole(
            role_family="trading_systems_engineer",
            confidence=0.91,
            evidence=["title matched strong keyword \"trading systems\""],
        ),
        season="Summer",
        year=2027,
        locations=["New York, NY"],
        remote_type="onsite",
        status=JobStatusInfo(
            status="open",
            confidence=0.92,
            evidence=["job is listed in the current greenhouse source feed"],
            checked_at=now,
        ),
        eligibility=EligibilityInfo(
            degree_levels=["bachelors"],
            graduation_years=[2027, 2028],
            majors=["computer science"],
            confidence=0.55,
            raw_evidence=["Currently pursuing a Bachelor's degree in Computer Science"],
        ),
        scores=JobScores(),
        prestige_tier="S+",
        tags=["internship"],
        first_seen=datetime(2026, 4, 1, 9, 0, tzinfo=UTC),
        last_seen=now,
        last_verified=now,
        content_hash="abc123def4567890",
    )


class TestDatabaseJobs(unittest.TestCase):
    def test_upsert_and_load_jobs_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cwd = Path(temp_dir)
            database_path = initialize_database(cwd)
            scan_run_id = create_scan_run(
                started_at=datetime(2026, 4, 30, 10, 0, tzinfo=UTC),
                pack="test_pack",
                trigger="scan:test_pack",
                cwd=cwd,
            )

            job = _build_job()
            result = upsert_jobs(
                [job],
                raw_records_by_id={
                    job.id: {
                        "merged_records": 1,
                        "records": [{"source_type": "greenhouse", "raw_payload": {"id": 123}}],
                    },
                },
                scan_run_id=scan_run_id,
                cwd=cwd,
            )
            complete_scan_run(
                scan_run_id=scan_run_id,
                completed_at=datetime(2026, 4, 30, 10, 5, tzinfo=UTC),
                status="completed",
                summary={"pack": "test_pack", "firms_selected": 1, "jobs_saved": 1},
                cwd=cwd,
            )

            self.assertEqual(result.inserted, 1)
            self.assertEqual(result.updated, 0)
            self.assertEqual(result.snapshots, 1)

            loaded = load_jobs_by_ids([job.id], cwd=cwd)
            self.assertIn(job.id, loaded)
            self.assertEqual(loaded[job.id].role.role_family, "trading_systems_engineer")
            self.assertEqual(loaded[job.id].status.status, "open")
            self.assertEqual(loaded[job.id].eligibility.majors, ["computer science"])

            with sqlite3.connect(database_path) as connection:
                row = connection.execute(
                    """
                    SELECT locations_json, eligibility_json, scores_json, role_evidence_json, status_evidence_json, raw_json
                    FROM jobs WHERE id = ?
                    """,
                    (job.id,),
                ).fetchone()
                snapshot_count = connection.execute("SELECT COUNT(*) FROM job_snapshots").fetchone()[0]

            self.assertEqual(json.loads(row[0]), ["New York, NY"])
            self.assertIsInstance(json.loads(row[1]), dict)
            self.assertIsInstance(json.loads(row[2]), dict)
            self.assertEqual(json.loads(row[3]), ["title matched strong keyword \"trading systems\""])
            self.assertEqual(json.loads(row[4]), ["job is listed in the current greenhouse source feed"])
            self.assertEqual(json.loads(row[5])["merged_records"], 1)
            self.assertEqual(snapshot_count, 1)

    def test_upsert_preserves_first_seen_and_marks_changed_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cwd = Path(temp_dir)
            initialize_database(cwd)

            original = _build_job(last_seen=datetime(2026, 4, 30, 10, 0, tzinfo=UTC))
            upsert_jobs([original], cwd=cwd)

            updated = _build_job(
                description="Build low latency systems and market data pipelines.",
                last_seen=datetime(2026, 4, 30, 11, 0, tzinfo=UTC),
            ).model_copy(
                update={
                    "first_seen": original.first_seen,
                    "content_hash": "changed-hash-1234",
                },
            )
            result = upsert_jobs([updated], cwd=cwd)
            loaded = load_jobs_by_ids([updated.id], cwd=cwd)[updated.id]

            self.assertEqual(result.inserted, 0)
            self.assertEqual(result.updated, 1)
            self.assertEqual(result.changed, 1)
            self.assertEqual(loaded.first_seen, original.first_seen)
            self.assertEqual(loaded.last_seen, updated.last_seen)
            self.assertEqual(loaded.description, updated.description)
