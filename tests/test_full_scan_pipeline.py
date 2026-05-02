from __future__ import annotations

import json
import sqlite3
import unittest
from pathlib import Path
from unittest import mock

from typer.testing import CliRunner

from internradar.cli import app
from internradar.collectors.registry import CollectorRegistry
from internradar.core.database import initialize_database
from internradar.core.models import Company, RawJob


class MutableGreenhouseCollector:
    source_type = "greenhouse"

    def __init__(self) -> None:
        self.version = 1

    def can_collect(self, company: Company) -> bool:
        return company.id == "hudson-river-trading"

    def collect(self, company: Company, config: dict[str, object]) -> list[RawJob]:
        del config
        description = (
            "<p>Apply now to work on low latency trading systems in C++ and Python.</p>"
            "<p>Currently pursuing a Bachelor's degree in Computer Science or related engineering field.</p>"
            "<p>Expected graduation date between December 2026 and June 2028.</p>"
            "<p>We do not sponsor visas for this position.</p>"
        )
        if self.version == 2:
            description += "<p>Experience with market data systems is preferred.</p>"
        return [
            RawJob(
                source_type=self.source_type,
                source_name="Fake Greenhouse",
                company_id=company.id,
                company_name=company.name,
                title="Software Engineer Intern, Trading Systems",
                url="https://boards.greenhouse.io/hrt/jobs/123",
                apply_url="https://boards.greenhouse.io/hrt/jobs/123/apply",
                location_raw="New York, NY",
                description_raw=description,
                department="Engineering",
                raw_payload={"id": 123, "board": "hrt"},
            ),
        ]


class CustomPageCollectorDouble:
    source_type = "custom_page"

    def can_collect(self, company: Company) -> bool:
        return company.id in {"hudson-river-trading", "broken-capital"}

    def collect(self, company: Company, config: dict[str, object]) -> list[RawJob]:
        del config
        if company.id == "broken-capital":
            raise RuntimeError("request timed out")
        return [
            RawJob(
                source_type=self.source_type,
                source_name="Custom Career Page",
                company_id=company.id,
                company_name=company.name,
                title="Software Engineer Intern, Trading Systems",
                url="https://careers.hrt.com/software-engineer-intern-trading-systems",
                apply_url="https://boards.greenhouse.io/hrt/jobs/123/apply",
                location_raw="New York, NY",
                description_raw=(
                    "<h1>Software Engineer Intern, Trading Systems</h1>"
                    "<p>Apply now for our Summer 2027 internship in New York.</p>"
                ),
                department="Engineering",
                raw_payload={"source": "custom"},
            ),
        ]


class LeverInfrastructureCollector:
    source_type = "lever"

    def can_collect(self, company: Company) -> bool:
        return company.id == "jane-street"

    def collect(self, company: Company, config: dict[str, object]) -> list[RawJob]:
        del config
        return [
            RawJob(
                source_type=self.source_type,
                source_name="Fake Lever",
                company_id=company.id,
                company_name=company.name,
                title="Infrastructure Engineer Intern",
                url="https://jobs.lever.co/jane-street/abc123",
                apply_url="https://jobs.lever.co/jane-street/abc123/apply",
                location_raw="Chicago, IL",
                description_raw=(
                    "Apply now to build distributed systems and observability tooling. "
                    "Undergraduate students in Computer Science or Engineering graduating in 2027 are welcome."
                ),
                department="Infrastructure",
                raw_payload={"id": "abc123"},
            ),
        ]


class TestFullScanPipeline(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = CliRunner()

    def test_full_pipeline_saves_normalized_jobs_and_snapshots(self) -> None:
        greenhouse = MutableGreenhouseCollector()
        registry = CollectorRegistry([greenhouse, CustomPageCollectorDouble(), LeverInfrastructureCollector()])

        with self.runner.isolated_filesystem():
            self._write_test_pack()
            database_path = initialize_database()

            with mock.patch("internradar.commands.scan.build_registry", return_value=registry), mock.patch(
                "internradar.commands.scan.load_config",
                return_value={},
            ):
                result = self.runner.invoke(
                    app,
                    ["scan", "--pack", "test_pack", "--verbose", "--project-root", "."],
                )

            self.assertEqual(result.exit_code, 0)
            self.assertIn("Raw jobs collected: 3", result.stdout)
            self.assertIn("Normalized jobs: 3", result.stdout)
            self.assertIn("Duplicates merged: 1", result.stdout)
            self.assertIn("Jobs saved: 2", result.stdout)
            self.assertIn("Open jobs: 2", result.stdout)
            self.assertIn("Collector errors: 1", result.stdout)
            self.assertRegex(
                result.stdout,
                r"- (trading_systems_engineer|software_engineer_trading): 1",
            )
            self.assertIn("- infrastructure_engineer: 1", result.stdout)

            with sqlite3.connect(database_path) as connection:
                jobs = connection.execute(
                    """
                    SELECT id, company_id, role_family, status, locations_json, eligibility_json, raw_json, scores_json
                    FROM jobs ORDER BY company_id
                    """,
                ).fetchall()
                snapshots = connection.execute("SELECT COUNT(*) FROM job_snapshots").fetchone()[0]
                summary_row = connection.execute(
                    "SELECT summary_json FROM scan_runs ORDER BY id DESC LIMIT 1",
                ).fetchone()

            self.assertEqual(len(jobs), 2)
            first_job = jobs[0]
            second_job = jobs[1]
            self.assertEqual(first_job[1], "hudson-river-trading")
            self.assertIn(first_job[2], {"trading_systems_engineer", "software_engineer_trading"})
            self.assertEqual(first_job[3], "open")
            self.assertEqual(json.loads(first_job[4]), ["New York, NY"])
            self.assertIn("computer science", json.loads(first_job[5])["majors"])
            self.assertEqual(json.loads(first_job[6])["merged_records"], 2)
            self.assertGreater(json.loads(first_job[7])["opportunity_score"], 0.0)
            self.assertEqual(second_job[2], "infrastructure_engineer")
            self.assertEqual(snapshots, 2)

            summary = json.loads(summary_row[0])
            self.assertEqual(summary["raw_jobs_found"], 3)
            self.assertEqual(summary["normalized_jobs"], 3)
            self.assertEqual(summary["duplicates_merged"], 1)
            self.assertEqual(summary["jobs_saved"], 2)
            self.assertEqual(summary["status_counts"]["open"], 2)

    def test_existing_job_preserves_first_seen_and_updates_last_seen(self) -> None:
        greenhouse = MutableGreenhouseCollector()
        registry = CollectorRegistry([greenhouse, CustomPageCollectorDouble(), LeverInfrastructureCollector()])

        with self.runner.isolated_filesystem():
            self._write_test_pack()
            database_path = initialize_database()

            with mock.patch("internradar.commands.scan.build_registry", return_value=registry), mock.patch(
                "internradar.commands.scan.load_config",
                return_value={},
            ):
                first_result = self.runner.invoke(
                    app,
                    ["scan", "--pack", "test_pack", "--project-root", "."],
                )
                greenhouse.version = 2
                second_result = self.runner.invoke(
                    app,
                    ["scan", "--pack", "test_pack", "--project-root", "."],
                )

            self.assertEqual(first_result.exit_code, 0)
            self.assertEqual(second_result.exit_code, 0)
            self.assertIn("Changed jobs: 1", second_result.stdout)

            with sqlite3.connect(database_path) as connection:
                first_seen, last_seen, description = connection.execute(
                    """
                    SELECT first_seen, last_seen, description
                    FROM jobs
                    WHERE company_id = 'hudson-river-trading'
                    """,
                ).fetchone()
                latest_summary = json.loads(
                    connection.execute(
                        "SELECT summary_json FROM scan_runs ORDER BY id DESC LIMIT 1",
                    ).fetchone()[0],
                )

            self.assertIn("market data systems", description)
            self.assertEqual(latest_summary["changed_jobs"], 1)
            self.assertTrue(last_seen >= first_seen)

    def test_dry_run_does_not_write_jobs(self) -> None:
        registry = CollectorRegistry([MutableGreenhouseCollector(), CustomPageCollectorDouble(), LeverInfrastructureCollector()])

        with self.runner.isolated_filesystem():
            self._write_test_pack()
            database_path = initialize_database()

            with mock.patch("internradar.commands.scan.build_registry", return_value=registry), mock.patch(
                "internradar.commands.scan.load_config",
                return_value={},
            ):
                result = self.runner.invoke(
                    app,
                    ["scan", "--pack", "test_pack", "--dry-run", "--project-root", "."],
                )

            self.assertEqual(result.exit_code, 0)
            with sqlite3.connect(database_path) as connection:
                jobs_count = connection.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
                scan_runs_count = connection.execute("SELECT COUNT(*) FROM scan_runs").fetchone()[0]

            self.assertEqual(jobs_count, 0)
            self.assertEqual(scan_runs_count, 0)

    def test_company_filter_and_max_firms_work_with_full_pipeline(self) -> None:
        registry = CollectorRegistry([MutableGreenhouseCollector(), CustomPageCollectorDouble(), LeverInfrastructureCollector()])

        with self.runner.isolated_filesystem():
            self._write_test_pack()
            database_path = initialize_database()

            with mock.patch("internradar.commands.scan.build_registry", return_value=registry), mock.patch(
                "internradar.commands.scan.load_config",
                return_value={},
            ):
                result = self.runner.invoke(
                    app,
                    [
                        "scan",
                        "--pack",
                        "test_pack",
                        "--company",
                        "Jane",
                        "--max-firms",
                        "1",
                        "--project-root",
                        ".",
                    ],
                )

            self.assertEqual(result.exit_code, 0)
            self.assertIn("Firms checked: 1", result.stdout)
            self.assertIn("Jobs saved: 1", result.stdout)
            with sqlite3.connect(database_path) as connection:
                company_ids = {
                    row[0]
                    for row in connection.execute("SELECT company_id FROM jobs")
                }
            self.assertEqual(company_ids, {"jane-street"})

    def _write_test_pack(self) -> None:
        pack_dir = Path("packs/test_pack")
        pack_dir.mkdir(parents=True, exist_ok=True)
        (pack_dir / "firms.yaml").write_text(
            """
firms:
  - id: hudson-river-trading
    name: Hudson River Trading
    aliases:
      - HRT
    ats_type: greenhouse
    ats_slug: hrt
    careers_url: https://boards.greenhouse.io/hrt
    categories:
      - trading_systems_engineer
  - id: jane-street
    name: Jane Street
    aliases:
      - JS
    ats_type: lever
    ats_slug: jane-street
    careers_url: https://jobs.lever.co/jane-street
    categories:
      - infrastructure_engineer
  - id: broken-capital
    name: Broken Capital
    careers_url: https://broken.example.com/careers
    ats_type: custom
            """.strip(),
        )
