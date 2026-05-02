from __future__ import annotations

import csv
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from internradar.core.models import ClassifiedRole, EligibilityInfo, Job, JobScores, JobStatusInfo
from internradar.export import ExportJobView
from internradar.export.csv_exporter import export_csv
from internradar.export.excel_exporter import export_xlsx
from internradar.export.html_exporter import export_html
from internradar.export.json_exporter import export_json
from internradar.export.markdown_exporter import export_markdown


def make_record() -> ExportJobView:
    from datetime import UTC, datetime

    now = datetime(2026, 5, 2, 12, 0, tzinfo=UTC)
    job = Job(
        id="job-1",
        company_id="hudson-river-trading",
        company_name="Hudson River Trading",
        title="Low Latency C++ Intern",
        description="Build low latency market data systems in C++.",
        apply_url="https://example.com/apply",
        source_url="https://example.com/source",
        source_type="custom_page",
        role=ClassifiedRole(role_family="low_latency_engineer", confidence=0.9, evidence=["classified"]),
        season="Summer",
        year=2027,
        locations=["Chicago, IL"],
        remote_type="onsite",
        status=JobStatusInfo(status="open", confidence=0.9, evidence=["apply now"], checked_at=now),
        eligibility=EligibilityInfo(
            degree_levels=["bachelors"],
            graduation_years=[2027],
            majors=["computer science"],
            confidence=0.4,
            raw_evidence=["Bachelor's degree in Computer Science"],
        ),
        scores=JobScores(
            prestige_score=70,
            role_fit_score=96,
            technical_depth_score=92,
            hidden_gem_score=84,
            freshness_score=100,
            eligibility_score=88,
            opportunity_score=91,
            explanation=["Opportunity score used the hidden_gems preset."],
        ),
        prestige_tier="B",
        tags=[],
        first_seen=now,
        last_seen=now,
        last_verified=now,
        content_hash="hash",
    )
    return ExportJobView(rank=1, job=job, application_status="saved", notes="Strong fit", saved=True, applied=False)


class TestExporters(unittest.TestCase):
    def test_csv_export_creates_file_and_headers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = export_csv([make_record()], Path(temp_dir) / "jobs.csv")
            self.assertTrue(path.exists())
            with path.open("r", encoding="utf-8") as handle:
                reader = csv.reader(handle)
                headers = next(reader)
            self.assertIn("Company", headers)
            self.assertIn("Opportunity Score", headers)

    def test_json_export_creates_valid_json_with_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = export_json(
                [make_record()],
                Path(temp_dir) / "jobs.json",
                metadata={"generated_at": "2026-05-02T12:00:00+00:00", "filters": {}, "pack": "quant_engineering"},
            )
            payload = json.loads(path.read_text())
            self.assertEqual(payload["count"], 1)
            self.assertEqual(payload["pack"], "quant_engineering")
            self.assertIn("jobs", payload)

    def test_excel_export_creates_workbook_with_required_sheets_and_hyperlinks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = export_xlsx(
                [make_record()],
                Path(temp_dir) / "jobs.xlsx",
                metadata={"generated_at": "2026-05-02T12:00:00+00:00", "summary": {}},
            )
            self.assertTrue(path.exists())
            with zipfile.ZipFile(path) as archive:
                workbook_xml = archive.read("xl/workbook.xml").decode("utf-8")
                open_jobs_xml = archive.read("xl/worksheets/sheet2.xml").decode("utf-8")
                rels = archive.read("xl/worksheets/_rels/sheet2.xml.rels").decode("utf-8")
            self.assertIn("Open Jobs", workbook_xml)
            self.assertIn("All Jobs", workbook_xml)
            self.assertIn("Apply URL", open_jobs_xml)
            self.assertIn("hyperlink", rels)

    def test_html_export_is_polished_and_self_contained(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = export_html(
                [make_record()],
                Path(temp_dir) / "jobs.html",
                metadata={
                    "generated_at": "2026-05-02T12:00:00+00:00",
                    "pack": "quant_engineering",
                    "summary": {"open": 1, "likely_open": 0, "hidden_gems": 1, "coming_soon": 0, "saved": 1, "applied": 0, "review_needed": 0},
                },
            )
            html = path.read_text(encoding="utf-8")
            self.assertIn("Intern Radar Report", html)
            self.assertIn("Low Latency C++ Intern", html)
            self.assertIn("https://example.com/apply", html)
            self.assertIn("Hidden Gems", html)
            self.assertIn("<style>", html)
            self.assertNotIn("<link rel=", html)
            self.assertNotIn("<script src=", html)

    def test_markdown_export_creates_expected_tables(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = export_markdown(
                [make_record()],
                Path(temp_dir) / "jobs.md",
                metadata={
                    "generated_at": "2026-05-02T12:00:00+00:00",
                    "pack": "quant_engineering",
                    "summary": {"open": 1, "likely_open": 0, "hidden_gems": 1, "coming_soon": 0, "saved": 1, "applied": 0},
                },
            )
            markdown = path.read_text(encoding="utf-8")
            self.assertIn("# Intern Radar Report", markdown)
            self.assertIn("| Rank | Company | Title | Status | Opportunity | Apply |", markdown)
            self.assertIn("[Apply](https://example.com/apply)", markdown)

    def test_empty_job_list_is_handled_gracefully(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = export_csv([], Path(temp_dir) / "empty.csv")
            json_path = export_json([], Path(temp_dir) / "empty.json", metadata={"generated_at": "", "filters": {}, "summary": {}})
            self.assertTrue(csv_path.exists())
            self.assertTrue(json_path.exists())
