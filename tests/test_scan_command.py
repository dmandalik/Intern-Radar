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


class FakeGreenhouseCollector:
    source_type = "greenhouse"

    def __init__(self) -> None:
        self.collect_calls = 0

    def can_collect(self, company: Company) -> bool:
        return (company.ats_type or "").casefold() == "greenhouse"

    def collect(self, company: Company, config: dict[str, object]) -> list[RawJob]:
        del config
        self.collect_calls += 1
        return [
            RawJob(
                source_type=self.source_type,
                source_name="Fake Greenhouse",
                company_id=company.id,
                company_name=company.name,
                title="Trading Intern I",
                url=f"https://example.com/{company.id}/1",
            ),
            RawJob(
                source_type=self.source_type,
                source_name="Fake Greenhouse",
                company_id=company.id,
                company_name=company.name,
                title="Trading Intern II",
                url=f"https://example.com/{company.id}/2",
            ),
        ]


class FakeLeverCollector:
    source_type = "lever"

    def __init__(self) -> None:
        self.collect_calls = 0

    def can_collect(self, company: Company) -> bool:
        return (company.ats_type or "").casefold() == "lever"

    def collect(self, company: Company, config: dict[str, object]) -> list[RawJob]:
        del config
        self.collect_calls += 1
        return [
            RawJob(
                source_type=self.source_type,
                source_name="Fake Lever",
                company_id=company.id,
                company_name=company.name,
                title="Platform Intern",
                url=f"https://example.com/{company.id}/job",
            ),
        ]


class FailingCollector:
    source_type = "custom_page"

    def __init__(self) -> None:
        self.collect_calls = 0

    def can_collect(self, company: Company) -> bool:
        return bool(company.careers_url) and (company.ats_type or "").casefold() in {
            "",
            "custom",
            "unknown",
        }

    def collect(self, company: Company, config: dict[str, object]) -> list[RawJob]:
        del company, config
        self.collect_calls += 1
        raise RuntimeError("request timed out")


class TestScanCommand(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = CliRunner()

    def test_scan_dry_run_lists_collectors_without_collecting(self) -> None:
        greenhouse = FakeGreenhouseCollector()
        lever = FakeLeverCollector()
        failing = FailingCollector()
        registry = CollectorRegistry([greenhouse, lever, failing])

        with self.runner.isolated_filesystem():
            self._write_test_pack()

            with mock.patch("internradar.commands.scan.build_registry", return_value=registry), mock.patch(
                "internradar.commands.scan.load_config",
                return_value={},
            ):
                result = self.runner.invoke(
                    app,
                    ["scan", "--pack", "test_pack", "--dry-run", "--project-root", "."],
                )

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Dry run: Intern Radar scan", result.stdout)
        self.assertIn("Firms loaded: 4", result.stdout)
        self.assertIn("Firms selected: 4", result.stdout)
        self.assertIn("Collectors available: custom_page, greenhouse, lever", result.stdout)
        self.assertIn("- Hudson River Trading: greenhouse", result.stdout)
        self.assertIn("- Jane Street: lever", result.stdout)
        self.assertIn("- Hidden Gem Capital: custom_page", result.stdout)
        self.assertIn("- No Collector LLC: no matching collectors", result.stdout)
        self.assertEqual(greenhouse.collect_calls, 0)
        self.assertEqual(lever.collect_calls, 0)
        self.assertEqual(failing.collect_calls, 0)

    def test_scan_max_firms_limits_selected_companies(self) -> None:
        registry = CollectorRegistry([FakeGreenhouseCollector(), FakeLeverCollector(), FailingCollector()])

        with self.runner.isolated_filesystem():
            self._write_test_pack()
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
                        "--dry-run",
                        "--max-firms",
                        "2",
                        "--project-root",
                        ".",
                    ],
                )

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Firms selected: 2", result.stdout)
        self.assertIn("- Hudson River Trading: greenhouse", result.stdout)
        self.assertIn("- Jane Street: lever", result.stdout)
        self.assertNotIn("- Hidden Gem Capital: custom_page", result.stdout)

    def test_scan_company_filter_matches_exact_name(self) -> None:
        registry = CollectorRegistry([FakeGreenhouseCollector(), FakeLeverCollector(), FailingCollector()])

        with self.runner.isolated_filesystem():
            self._write_test_pack()
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
                        "--dry-run",
                        "--company",
                        "Hudson River Trading",
                        "--project-root",
                        ".",
                    ],
                )

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Firms selected: 1", result.stdout)
        self.assertIn("- Hudson River Trading: greenhouse", result.stdout)
        self.assertNotIn("- Jane Street: lever", result.stdout)

    def test_scan_company_filter_matches_alias(self) -> None:
        registry = CollectorRegistry([FakeGreenhouseCollector(), FakeLeverCollector(), FailingCollector()])

        with self.runner.isolated_filesystem():
            self._write_test_pack()
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
                        "--dry-run",
                        "--company",
                        "HRT",
                        "--project-root",
                        ".",
                    ],
                )

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Firms selected: 1", result.stdout)
        self.assertIn("- Hudson River Trading: greenhouse", result.stdout)

    def test_scan_company_filter_matches_partial_name(self) -> None:
        registry = CollectorRegistry([FakeGreenhouseCollector(), FakeLeverCollector(), FailingCollector()])

        with self.runner.isolated_filesystem():
            self._write_test_pack()
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
                        "--dry-run",
                        "--company",
                        "Jane",
                        "--project-root",
                        ".",
                    ],
                )

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Firms selected: 1", result.stdout)
        self.assertIn("- Jane Street: lever", result.stdout)

    def test_scan_invalid_company_filter_returns_helpful_error(self) -> None:
        registry = CollectorRegistry([FakeGreenhouseCollector(), FakeLeverCollector(), FailingCollector()])

        with self.runner.isolated_filesystem():
            self._write_test_pack()
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
                        "--dry-run",
                        "--company",
                        "Does Not Exist",
                        "--project-root",
                        ".",
                    ],
                )

        self.assertEqual(result.exit_code, 1)
        self.assertIn("No firms matched company filter 'Does Not Exist'.", result.stdout)

    def test_scan_invalid_pack_returns_helpful_error(self) -> None:
        registry = CollectorRegistry([FakeGreenhouseCollector(), FakeLeverCollector(), FailingCollector()])

        with self.runner.isolated_filesystem():
            with mock.patch("internradar.commands.scan.build_registry", return_value=registry), mock.patch(
                "internradar.commands.scan.load_config",
                return_value={},
            ):
                result = self.runner.invoke(
                    app,
                    ["scan", "--pack", "missing_pack", "--dry-run", "--project-root", "."],
                )

        self.assertEqual(result.exit_code, 1)
        self.assertIn("Pack 'missing_pack' was not found", result.stdout)

    def test_scan_real_run_counts_jobs_errors_and_persists_summary(self) -> None:
        greenhouse = FakeGreenhouseCollector()
        lever = FakeLeverCollector()
        failing = FailingCollector()
        registry = CollectorRegistry([greenhouse, lever, failing])

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

            self.assertTrue(database_path.exists())
            with sqlite3.connect(database_path) as connection:
                row = connection.execute(
                    "SELECT status, trigger, notes FROM scan_runs ORDER BY id DESC LIMIT 1",
                ).fetchone()

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Scan complete.", result.stdout)
        self.assertIn("Firms checked: 4", result.stdout)
        self.assertIn("Sources attempted: 3", result.stdout)
        self.assertIn("Raw jobs collected: 3", result.stdout)
        self.assertIn("Normalized jobs: 3", result.stdout)
        self.assertIn("Duplicates merged: 1", result.stdout)
        self.assertIn("Jobs saved: 2", result.stdout)
        self.assertIn("Collector errors: 1", result.stdout)
        self.assertIn("- greenhouse: 2", result.stdout)
        self.assertIn("- lever: 1", result.stdout)
        self.assertIn("Hidden Gem Capital / custom_page: request timed out", result.stdout)
        self.assertIn("Persistence: saved jobs and scan history to", result.stdout)
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "completed_with_errors")
        self.assertEqual(row[1], "scan:test_pack")
        notes = json.loads(row[2])
        self.assertEqual(notes["pack"], "test_pack")
        self.assertEqual(notes["firms_selected"], 4)
        self.assertEqual(notes["raw_jobs_found"], 3)
        self.assertEqual(notes["normalized_jobs"], 3)
        self.assertEqual(notes["duplicates_merged"], 1)
        self.assertEqual(notes["jobs_saved"], 2)
        self.assertEqual(notes["collector_errors"], 1)

    def test_scan_source_filter_restricts_collectors(self) -> None:
        registry = CollectorRegistry([FakeGreenhouseCollector(), FakeLeverCollector(), FailingCollector()])

        with self.runner.isolated_filesystem():
            self._write_test_pack()
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
                        "--dry-run",
                        "--source",
                        "lever",
                        "--project-root",
                        ".",
                    ],
                )

        self.assertEqual(result.exit_code, 0)
        self.assertIn("- Hudson River Trading: no matching collectors", result.stdout)
        self.assertIn("- Jane Street: lever", result.stdout)
        self.assertIn("- Hidden Gem Capital: no matching collectors", result.stdout)

    def test_scan_invalid_source_returns_helpful_error(self) -> None:
        registry = CollectorRegistry([FakeGreenhouseCollector(), FakeLeverCollector(), FailingCollector()])

        with self.runner.isolated_filesystem():
            self._write_test_pack()
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
                        "--dry-run",
                        "--source",
                        "not-a-source",
                        "--project-root",
                        ".",
                    ],
                )

        self.assertEqual(result.exit_code, 1)
        self.assertIn("Unknown collector source 'not-a-source'.", result.stdout)

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
  - id: jane-street
    name: Jane Street
    aliases:
      - JS
    ats_type: lever
    ats_slug: jane-street
    careers_url: https://jobs.lever.co/jane-street
  - id: hidden-gem-capital
    name: Hidden Gem Capital
    aliases:
      - HGC
    careers_url: https://hidden.example.com/careers
  - id: no-collector-llc
    name: No Collector LLC
            """.strip(),
        )
