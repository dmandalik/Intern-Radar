from __future__ import annotations

import sqlite3
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from internradar.core.database import create_scan_run, initialize_database, record_user_action, upsert_jobs
from internradar.core.models import ClassifiedRole, EligibilityInfo, Job, JobScores, JobStatusInfo


class TestDatabaseInitialization(unittest.TestCase):
    def test_initialize_database_creates_file_and_tables(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cwd = Path(temp_dir)

            database_path = initialize_database(cwd)

            self.assertEqual(database_path, cwd / ".internradar" / "internradar.sqlite3")
            self.assertTrue(database_path.exists())

            with sqlite3.connect(database_path) as connection:
                table_names = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'",
                    )
                }

            self.assertEqual(
                table_names & {
                    "scan_runs",
                    "companies",
                    "jobs",
                    "user_actions",
                    "job_snapshots",
                },
                {"scan_runs", "companies", "jobs", "user_actions", "job_snapshots"},
            )

    def test_initialize_database_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cwd = Path(temp_dir)

            first_path = initialize_database(cwd)
            second_path = initialize_database(cwd)

            self.assertEqual(first_path, second_path)
            self.assertTrue(second_path.exists())

    def test_initialize_database_repairs_legacy_job_foreign_keys(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cwd = Path(temp_dir)
            state_dir = cwd / ".internradar"
            state_dir.mkdir(parents=True, exist_ok=True)
            database_path = state_dir / "internradar.sqlite3"

            with sqlite3.connect(database_path) as connection:
                connection.execute("PRAGMA foreign_keys = ON")
                connection.execute(
                    """
                    CREATE TABLE jobs (
                        id INTEGER PRIMARY KEY,
                        external_id TEXT,
                        company_id INTEGER,
                        title TEXT,
                        source_url TEXT,
                        status TEXT,
                        location TEXT,
                        created_at TEXT,
                        updated_at TEXT
                    )
                    """,
                )
                connection.execute(
                    """
                    INSERT INTO jobs (id, external_id, company_id, title, source_url, status, location, created_at, updated_at)
                    VALUES (1, 'legacy-job-1', 101, 'Legacy Trading Intern', 'https://example.com/jobs/1', 'open', 'New York, NY', '2026-04-01T09:00:00+00:00', '2026-04-02T09:00:00+00:00')
                    """,
                )
                connection.execute(
                    """
                    CREATE TABLE user_actions (
                        id INTEGER PRIMARY KEY,
                        job_id INTEGER NOT NULL,
                        action_type TEXT NOT NULL,
                        action_value TEXT,
                        notes TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        FOREIGN KEY (job_id) REFERENCES jobs (id)
                    )
                    """,
                )
                connection.execute(
                    """
                    CREATE TABLE job_snapshots (
                        id INTEGER PRIMARY KEY,
                        job_id INTEGER NOT NULL,
                        scan_run_id INTEGER,
                        payload_json TEXT NOT NULL,
                        captured_at TEXT NOT NULL,
                        FOREIGN KEY (job_id) REFERENCES jobs (id)
                    )
                    """,
                )
                connection.commit()

            initialize_database(cwd)

            now = datetime(2026, 5, 1, 12, 0, tzinfo=UTC)
            job = Job(
                id="legacy-job-1",
                company_id="legacy-company",
                company_name="Legacy Company",
                title="Legacy Trading Intern",
                description="Migrated legacy job.",
                apply_url="https://example.com/jobs/1/apply",
                source_url="https://example.com/jobs/1",
                source_type="legacy",
                role=ClassifiedRole(role_family="unknown", confidence=0.0),
                season="Summer",
                year=2027,
                locations=["New York, NY"],
                remote_type="onsite",
                status=JobStatusInfo(status="open", confidence=0.8, evidence=["legacy migration"], checked_at=now),
                eligibility=EligibilityInfo(),
                scores=JobScores(),
                first_seen=now,
                last_seen=now,
                last_verified=now,
            )

            scan_run_id = create_scan_run(started_at=now, pack="test_pack", cwd=cwd)
            upsert_jobs([job], scan_run_id=scan_run_id, cwd=cwd)
            record_user_action(
                job.id,
                action_type="application_status",
                action_value="saved",
                created_at=now,
                updated_at=now,
                cwd=cwd,
            )

            with sqlite3.connect(database_path) as connection:
                user_actions_sql = connection.execute(
                    "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'user_actions'",
                ).fetchone()[0]
                snapshots_sql = connection.execute(
                    "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'job_snapshots'",
                ).fetchone()[0]
                user_action_count = connection.execute("SELECT COUNT(*) FROM user_actions").fetchone()[0]
                snapshot_count = connection.execute("SELECT COUNT(*) FROM job_snapshots").fetchone()[0]

            self.assertNotIn("jobs_legacy", user_actions_sql.casefold())
            self.assertNotIn("jobs_legacy", snapshots_sql.casefold())
            self.assertEqual(user_action_count, 1)
            self.assertEqual(snapshot_count, 1)
