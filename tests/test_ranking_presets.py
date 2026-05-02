from __future__ import annotations

import json
import sqlite3
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest import mock

from typer.testing import CliRunner

from internradar.cli import app
from internradar.collectors.registry import CollectorRegistry
from internradar.core.database import initialize_database
from internradar.core.models import ClassifiedRole, Company, EligibilityInfo, Job, JobScores, JobStatusInfo, RawJob
from internradar.scoring.opportunity_score import score_job
from internradar.scoring.ranking_presets import resolve_ranking_preset


class FakeScoringCollector:
    source_type = "greenhouse"

    def can_collect(self, company: Company) -> bool:
        return True

    def collect(self, company: Company, config: dict[str, object]) -> list[RawJob]:
        del config
        return [
            RawJob(
                source_type="greenhouse",
                source_name="Fake Greenhouse",
                company_id=company.id,
                company_name=company.name,
                title="Low Latency C++ Intern",
                url="https://boards.greenhouse.io/example/jobs/123",
                apply_url="https://boards.greenhouse.io/example/jobs/123/apply",
                location_raw="Chicago, IL",
                description_raw=(
                    "<p>Apply now to build low latency trading infrastructure in C++ and Python.</p>"
                    "<p>Currently pursuing a Bachelor's degree in Computer Science.</p>"
                ),
                department="Engineering",
                raw_payload={"id": 123},
            ),
        ]


def make_job(*, prestige_tier: str | None, role_family: str) -> Job:
    timestamp = datetime(2026, 5, 1, 12, 0, tzinfo=UTC)
    return Job(
        id="job-123",
        company_id="example-firm",
        company_name="Example Firm",
        title="Software Engineer Intern, Trading Systems",
        description="Build low latency market data systems in C++ and Python.",
        apply_url="https://example.com/apply",
        source_url="https://example.com/job",
        source_type="greenhouse",
        role=ClassifiedRole(
            role_family=role_family,
            confidence=0.9,
            evidence=[f"classified as {role_family}"],
        ),
        season="Summer",
        year=2027,
        locations=["Chicago, IL"],
        remote_type="onsite",
        status=JobStatusInfo(status="open", confidence=0.9, evidence=["open"], checked_at=timestamp),
        eligibility=EligibilityInfo(
            degree_levels=["bachelors"],
            graduation_years=[2027],
            majors=["computer science"],
            undergrad_friendly=True,
            confidence=0.5,
            raw_evidence=["Bachelor's degree in Computer Science"],
        ),
        scores=JobScores(),
        prestige_tier=prestige_tier,
        tags=[],
        first_seen=timestamp - timedelta(days=1),
        last_seen=timestamp,
        last_verified=timestamp,
        content_hash="hash",
    )


class TestRankingPresets(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = CliRunner()

    def test_resolve_builtin_preset(self) -> None:
        name, weights = resolve_ranking_preset("prestige_first")
        self.assertEqual(name, "prestige_first")
        self.assertAlmostEqual(weights["prestige"], 0.40)

    def test_resolve_custom_preset_from_config(self) -> None:
        name, weights = resolve_ranking_preset(
            "custom",
            config={"scoring": {"custom_preset": {"role_fit": 3, "hidden_gem": 1}}},
        )
        self.assertEqual(name, "custom")
        self.assertAlmostEqual(weights["role_fit"], 0.75)
        self.assertAlmostEqual(weights["hidden_gem"], 0.25)

    def test_opportunity_score_uses_selected_preset(self) -> None:
        job = make_job(prestige_tier="S+", role_family="software_engineer_trading")
        prestige_first = score_job(job, preset="prestige_first")
        hidden_gems = score_job(job, preset="hidden_gems")
        self.assertNotEqual(prestige_first.scores.opportunity_score, hidden_gems.scores.opportunity_score)

    def test_scan_pipeline_persists_scores_when_scoring_is_integrated(self) -> None:
        registry = CollectorRegistry([FakeScoringCollector()])

        with self.runner.isolated_filesystem():
            self._write_test_pack()
            database_path = initialize_database()

            with mock.patch("internradar.commands.scan.build_registry", return_value=registry), mock.patch(
                "internradar.commands.scan.load_config",
                return_value={"scoring": {"preset": "hidden_gems"}},
            ):
                result = self.runner.invoke(
                    app,
                    ["scan", "--pack", "test_pack", "--project-root", "."],
                )

            self.assertEqual(result.exit_code, 0)
            with sqlite3.connect(database_path) as connection:
                scores_json = connection.execute("SELECT scores_json FROM jobs LIMIT 1").fetchone()[0]

            scores = json.loads(scores_json)
            self.assertGreater(scores["opportunity_score"], 0.0)
            self.assertGreater(scores["technical_depth_score"], 0.0)
            self.assertTrue(scores["explanation"])

    def _write_test_pack(self) -> None:
        pack_dir = Path("packs/test_pack")
        pack_dir.mkdir(parents=True, exist_ok=True)
        (pack_dir / "firms.yaml").write_text(
            """
firms:
  - id: example-firm
    name: Example Firm
    ats_type: greenhouse
    ats_slug: example
    careers_url: https://boards.greenhouse.io/example
    categories:
      - low_latency_engineer
    default_prestige_tier: tier_4
            """.strip(),
        )
