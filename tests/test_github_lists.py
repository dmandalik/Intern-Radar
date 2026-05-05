from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from internradar.collectors.github_lists import (
    compare_imported_jobs_to_known_firms,
    import_github_list,
    parse_markdown_tables,
    source_visibility_counts,
)
from internradar.core.models import ClassifiedRole, Company, EligibilityInfo, Job, JobScores, JobStatusInfo
from internradar.scoring.hidden_gems import visibility_signal

MARKDOWN = """
| Company | Role | Location | Application | Date Posted | Notes |
| --- | --- | --- | --- | --- | --- |
| Hudson River Trading | Software Engineer Intern, Trading Systems | New York, NY | [Apply](https://example.com/hrt/apply) | 2026-04-10 | Build low latency systems |
| Niche Trading Co | Quant Developer Intern | Chicago, IL | https://example.com/niche/apply | 2026-04-11 | Hidden gem list row |
""".strip()


def make_known_job() -> Job:
    now = datetime(2026, 5, 4, 12, 0, tzinfo=UTC)
    return Job(
        id="hrt-job",
        company_id="hudson-river-trading",
        company_name="Hudson River Trading",
        title="Software Engineer Intern, Trading Systems",
        description="Build low latency systems.",
        apply_url="https://example.com/hrt/apply",
        source_url="https://example.com/hrt/source",
        source_type="greenhouse",
        role=ClassifiedRole(role_family="trading_systems_engineer", confidence=0.9, evidence=["classified"]),
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
        content_hash="hash-hrt",
    )


class TestGitHubLists(unittest.TestCase):
    def test_markdown_table_parser_extracts_expected_columns(self) -> None:
        rows = parse_markdown_tables(MARKDOWN)

        self.assertEqual(rows[0]["company"], "Hudson River Trading")
        self.assertEqual(rows[0]["title"], "Software Engineer Intern, Trading Systems")
        self.assertEqual(rows[0]["location"], "New York, NY")
        self.assertEqual(rows[0]["apply_url"], "https://example.com/hrt/apply")

    def test_parser_handles_missing_columns(self) -> None:
        rows = parse_markdown_tables(
            """
| Company | Role |
| --- | --- |
| Jane Street | Trading Systems Intern |
""".strip()
        )

        self.assertEqual(rows[0]["company"], "Jane Street")
        self.assertEqual(rows[0]["title"], "Trading Systems Intern")

    def test_importer_returns_raw_jobs_and_preserves_raw_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "list.md"
            path.write_text(MARKDOWN, encoding="utf-8")

            jobs = import_github_list(path)

        self.assertEqual(len(jobs), 2)
        self.assertEqual(jobs[0].source_type, "github_list")
        self.assertEqual(jobs[0].company_name, "Hudson River Trading")
        self.assertEqual(jobs[0].title, "Software Engineer Intern, Trading Systems")
        self.assertEqual(jobs[0].location_raw, "New York, NY")
        self.assertEqual(jobs[0].apply_url, "https://example.com/hrt/apply")
        self.assertIn("row", jobs[0].raw_payload)

    def test_unknown_company_comparison_identifies_missing_firms(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "list.md"
            path.write_text(MARKDOWN, encoding="utf-8")
            imported = import_github_list(path)

        firms = [
            Company(id="hudson-river-trading", name="Hudson River Trading", aliases=["HRT"]),
            Company(id="jane-street", name="Jane Street"),
        ]
        comparison = compare_imported_jobs_to_known_firms(imported, firms, known_jobs=[make_known_job()])

        self.assertIn("Niche Trading Co", comparison.unknown_companies)
        self.assertEqual(comparison.unknown_company_count, 1)
        self.assertEqual(len(comparison.missing_known_jobs), 1)
        self.assertEqual(comparison.missing_known_jobs[0].company_name, "Niche Trading Co")

    def test_visibility_helper_uses_github_list_presence(self) -> None:
        adjustment, evidence = visibility_signal(
            source_type="greenhouse",
            source_visibility_count=2,
            appears_in_github_list=True,
        )

        self.assertLess(adjustment, 0.0)
        self.assertTrue(any("GitHub" in item for item in evidence))

    def test_source_visibility_counts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "list.md"
            path.write_text(MARKDOWN, encoding="utf-8")
            imported = import_github_list(path)

        counts = source_visibility_counts(imported)

        self.assertEqual(counts["hudson river trading::software engineer intern, trading systems"], 1)
