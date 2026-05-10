from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from typer.testing import CliRunner

from internradar.cli import app
from internradar.core.database import initialize_database, upsert_jobs
from internradar.core.models import ClassifiedRole, EligibilityInfo, Job, JobScores, JobStatusInfo


def make_job(
    *,
    job_id: str,
    title: str,
    status: str,
    hidden_gem_score: float,
    application_status: str = "",
) -> Job:
    from datetime import UTC, datetime

    now = datetime(2026, 5, 2, 12, 0, tzinfo=UTC)
    return Job(
        id=job_id,
        company_id="firm",
        company_name="Example Firm",
        title=title,
        description="Build systems in C++ and Python.",
        apply_url=f"https://example.com/{job_id}/apply",
        source_url=f"https://example.com/{job_id}",
        source_type="greenhouse",
        role=ClassifiedRole(role_family="software_engineer_trading", confidence=0.9, evidence=["classified"]),
        season="Summer",
        year=2027,
        locations=["New York, NY"],
        remote_type="onsite",
        status=JobStatusInfo(status=status, confidence=0.9, evidence=["status"], checked_at=now),
        eligibility=EligibilityInfo(
            degree_levels=["bachelors"],
            graduation_years=[2027],
            majors=["computer science"],
            confidence=0.4,
            raw_evidence=["Bachelor's degree in Computer Science"],
        ),
        scores=JobScores(
            prestige_score=80,
            role_fit_score=95,
            technical_depth_score=85,
            hidden_gem_score=hidden_gem_score,
            freshness_score=90,
            eligibility_score=88,
            opportunity_score=92 - hidden_gem_score / 10.0,
            explanation=["Ranked for strong technical fit."],
        ),
        prestige_tier="A",
        tags=[],
        first_seen=now,
        last_seen=now,
        last_verified=now,
        content_hash=f"hash-{job_id}",
    )


class TestExportCommand(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = CliRunner()

    def test_export_command_errors_helpfully_when_no_jobs_exist(self) -> None:
        with self.runner.isolated_filesystem():
            initialize_database()
            result = self.runner.invoke(app, ["export", "--format", "csv"])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("Run `internradar scan` first", result.stdout)

    def test_export_command_all_creates_all_formats(self) -> None:
        with self.runner.isolated_filesystem():
            database_path = initialize_database()
            self._seed_database(database_path)
            result = self.runner.invoke(app, ["export", "--all"])

            export_dir = Path(".internradar/exports")
            files = {path.suffix for path in export_dir.iterdir()}

        self.assertEqual(result.exit_code, 0)
        self.assertTrue({".csv", ".json", ".xlsx", ".html", ".md"} <= files)

    def test_filters_work_for_open_jobs_and_hidden_gems(self) -> None:
        with self.runner.isolated_filesystem():
            database_path = initialize_database()
            self._seed_database(database_path)

            result = self.runner.invoke(
                app,
                ["export", "--format", "json", "--status", "open", "--hidden-gems"],
            )
            exported_path = self._exported_path_from_stdout(result.stdout)
            payload = json.loads(exported_path.read_text())

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["jobs"][0]["status"]["status"], "open")
        self.assertGreaterEqual(payload["jobs"][0]["scores"]["hidden_gem_score"], 70)

    def test_export_command_applied_filter_uses_user_actions(self) -> None:
        with self.runner.isolated_filesystem():
            database_path = initialize_database()
            self._seed_database(database_path)

            result = self.runner.invoke(
                app,
                ["export", "--format", "csv", "--applied"],
            )
            exported_path = self._exported_path_from_stdout(result.stdout)
            csv_text = exported_path.read_text(encoding="utf-8")

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Closed Role", csv_text)
        self.assertNotIn("Open Hidden Gem", csv_text)

    def test_export_command_ignores_artificial_demo_rows(self) -> None:
        with self.runner.isolated_filesystem():
            initialize_database()
            jobs = [
                make_job(job_id="job-real", title="Real Role", status="open", hidden_gem_score=80),
                make_job(job_id="job-demo", title="Demo Role", status="open", hidden_gem_score=80),
            ]
            upsert_jobs(
                jobs,
                raw_records_by_id={
                    "job-real": {"source": "greenhouse"},
                    "job-demo": {"artificial_demo_data": True},
                },
            )

            result = self.runner.invoke(app, ["export", "--format", "json"])
            exported_path = self._exported_path_from_stdout(result.stdout)
            payload = json.loads(exported_path.read_text())

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["jobs"][0]["id"], "job-real")

    def _seed_database(self, database_path: Path) -> None:
        jobs = [
            make_job(job_id="job-open", title="Open Hidden Gem", status="open", hidden_gem_score=81),
            make_job(job_id="job-soon", title="Soon Role", status="coming_soon", hidden_gem_score=55),
            make_job(job_id="job-closed", title="Closed Role", status="closed", hidden_gem_score=12),
        ]
        upsert_jobs(jobs)
        with sqlite3.connect(database_path) as connection:
            connection.execute(
                """
                INSERT INTO user_actions (job_id, action_type, action_value, notes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("job-open", "saved", "true", "Watch this one", "2026-05-02T12:00:00+00:00", "2026-05-02T12:00:00+00:00"),
            )
            connection.execute(
                """
                INSERT INTO user_actions (job_id, action_type, action_value, notes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("job-closed", "applied", "true", "Already applied", "2026-05-02T12:05:00+00:00", "2026-05-02T12:05:00+00:00"),
            )
            connection.commit()

    def _exported_path_from_stdout(self, stdout: str) -> Path:
        for line in stdout.splitlines():
            if line.startswith("Created export: "):
                return Path(line.replace("Created export: ", "", 1).strip())
        raise AssertionError(f"No export path found in stdout: {stdout!r}")
