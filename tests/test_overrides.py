from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from typer.testing import CliRunner

from internradar.cli import app
from internradar.collectors.registry import CollectorRegistry
from internradar.core.database import initialize_database, load_jobs_by_ids, load_user_actions
from internradar.core.models import Company, Job, RawJob
from internradar.review.overrides import OverrideError, ReviewOverrides, apply_overrides, load_overrides


def make_company() -> Company:
    return Company(
        id="gts",
        name="GTS",
        aliases=["Global Trading Systems"],
        ats_type="greenhouse",
        default_prestige_tier="B",
    )


def make_job() -> Job:
    from datetime import UTC, datetime

    now = datetime(2026, 5, 4, 12, 0, tzinfo=UTC)
    from internradar.core.models import ClassifiedRole, EligibilityInfo, JobScores, JobStatusInfo

    return Job(
        id="gts-quantitative-trading-intern-summer-2027",
        company_id="gts",
        company_name="GTS",
        title="Quantitative Trading Intern",
        description="Campus ambassador style program with unpaid introductory work.",
        apply_url="https://example.com/apply",
        source_url="https://example.com/source",
        source_type="greenhouse",
        role=ClassifiedRole(role_family="quant_trading", confidence=0.7, evidence=["classified"]),
        season="Summer",
        year=2027,
        locations=["New York, NY"],
        remote_type="onsite",
        status=JobStatusInfo(status="likely_open", confidence=0.6, evidence=["listed"], checked_at=now),
        eligibility=EligibilityInfo(confidence=0.2),
        scores=JobScores(),
        prestige_tier="B",
        tags=[],
        first_seen=now,
        last_seen=now,
        last_verified=now,
        content_hash="hash-gts",
    )


class FakeCollector:
    source_type = "greenhouse"

    def can_collect(self, company: Company) -> bool:
        return company.id == "gts"

    def collect(self, company: Company, config: dict[str, object]) -> list[RawJob]:
        del config
        return [
            RawJob(
                source_type="greenhouse",
                source_name="Fake Greenhouse",
                company_id=company.id,
                company_name=company.name,
                title="Quantitative Trading Intern",
                url="https://boards.greenhouse.io/gts/jobs/123",
                apply_url="https://boards.greenhouse.io/gts/jobs/123/apply",
                location_raw="New York, NY",
                description_raw=(
                    "<p>Apply now.</p>"
                    "<p>Summer 2027 internship in New York.</p>"
                ),
                department="Trading",
                raw_payload={"id": 123},
            ),
        ]


class TestOverrides(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = CliRunner()

    def test_load_overrides_from_local_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cwd = Path(temp_dir)
            app_dir = cwd / ".internradar"
            app_dir.mkdir()
            (app_dir / "overrides.yaml").write_text(
                """
company_overrides:
  GTS:
    prestige_tier: S
job_overrides:
  gts-quantitative-trading-intern-summer-2027:
    status: open
ignored_keywords:
  - unpaid
""".strip(),
                encoding="utf-8",
            )

            overrides = load_overrides(cwd=cwd)

            self.assertEqual(overrides.company_overrides["GTS"]["prestige_tier"], "S")
            self.assertEqual(overrides.job_overrides["gts-quantitative-trading-intern-summer-2027"]["status"], "open")
            self.assertEqual(overrides.ignored_keywords, ["unpaid"])

    def test_invalid_overrides_yaml_is_helpful(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cwd = Path(temp_dir)
            app_dir = cwd / ".internradar"
            app_dir.mkdir()
            (app_dir / "overrides.yaml").write_text("company_overrides: [broken", encoding="utf-8")

            with self.assertRaises(OverrideError):
                load_overrides(cwd=cwd)

    def test_company_prestige_override_applies(self) -> None:
        overrides = ReviewOverrides(company_overrides={"GTS": {"prestige_tier": "S"}})

        applied = apply_overrides(make_job(), company=make_company(), overrides=overrides)

        self.assertEqual(applied.company.default_prestige_tier, "S")
        self.assertEqual(applied.job.prestige_tier, "S")

    def test_job_role_and_status_override_apply(self) -> None:
        overrides = ReviewOverrides(
            job_overrides={
                "gts-quantitative-trading-intern-summer-2027": {
                    "role_family": "algorithmic_trading_engineer",
                    "status": "open",
                },
            },
        )

        applied = apply_overrides(make_job(), company=make_company(), overrides=overrides)

        self.assertEqual(applied.job.role.role_family, "algorithmic_trading_engineer")
        self.assertEqual(applied.job.status.status, "open")
        self.assertEqual(applied.job.role.confidence, 1.0)
        self.assertEqual(applied.job.status.confidence, 1.0)

    def test_ignored_company_marks_job_ignored(self) -> None:
        overrides = ReviewOverrides(ignored_companies=["GTS"])

        applied = apply_overrides(make_job(), company=make_company(), overrides=overrides)

        self.assertEqual(applied.application_status, "ignored")
        self.assertTrue(any("ignored company" in reason for reason in applied.ignore_reasons))

    def test_ignored_keyword_marks_job_ignored(self) -> None:
        overrides = ReviewOverrides(ignored_keywords=["unpaid", "campus ambassador"])

        applied = apply_overrides(make_job(), company=make_company(), overrides=overrides)

        self.assertEqual(applied.application_status, "ignored")
        self.assertTrue(any("campus ambassador" in reason for reason in applied.ignore_reasons))

    def test_scan_integration_applies_overrides(self) -> None:
        registry = CollectorRegistry([FakeCollector()])

        with self.runner.isolated_filesystem():
            Path("packs/test_pack").mkdir(parents=True)
            Path("packs/test_pack/firms.yaml").write_text(
                """
firms:
  - id: gts
    name: GTS
    aliases:
      - Global Trading Systems
    ats_type: greenhouse
    ats_slug: gts
""".strip(),
                encoding="utf-8",
            )
            initialize_database()
            Path(".internradar").mkdir(exist_ok=True)
            Path(".internradar/overrides.yaml").write_text(
                """
company_overrides:
  GTS:
    prestige_tier: S
job_overrides:
  gts-greenhouse-123:
    role_family: algorithmic_trading_engineer
    status: open
    application_status: applied
    notes: Applied with systems-focused resume.
""".strip(),
                encoding="utf-8",
            )

            with mock.patch("internradar.commands.scan.build_registry", return_value=registry), mock.patch(
                "internradar.commands.scan.load_config",
                return_value={},
            ):
                result = self.runner.invoke(app, ["scan", "--pack", "test_pack", "--project-root", "."])

            self.assertEqual(result.exit_code, 0)
            saved = load_jobs_by_ids(["gts-greenhouse-123"])
            state = load_user_actions()["gts-greenhouse-123"]

        job = saved["gts-greenhouse-123"]
        self.assertEqual(job.role.role_family, "algorithmic_trading_engineer")
        self.assertEqual(job.status.status, "open")
        self.assertEqual(job.prestige_tier, "S")
        self.assertEqual(state["application_status"], "applied")
        self.assertEqual(state["notes"], "Applied with systems-focused resume.")
