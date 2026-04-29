from __future__ import annotations

import unittest
from datetime import UTC, datetime
from pathlib import Path

from internradar.core.models import (
    ClassifiedRole,
    EligibilityInfo,
    Job,
    JobScores,
    JobStatusInfo,
)
from internradar.core.pack_loader import load_pack_role_keywords
from internradar.parsers.role_classifier import classify_job_role, classify_role


class TestRoleClassifier(unittest.TestCase):
    def setUp(self) -> None:
        self.pack_dir = Path("tests/fixtures")
        self.quant_keywords = load_pack_role_keywords("quant_engineering")

    def test_trading_systems_role_is_classified_with_strong_evidence(self) -> None:
        role = classify_role(
            "Software Engineer Intern, Trading Systems",
            "Build market data and order book services in C++.",
            role_keywords=self.quant_keywords,
        )

        self.assertIn(role.role_family, {"trading_systems_engineer", "software_engineer_trading"})
        self.assertGreaterEqual(role.confidence, 0.6)
        self.assertTrue(role.evidence)

    def test_low_latency_role_is_classified(self) -> None:
        role = classify_role(
            "Low Latency C++ Intern",
            "Optimize performance critical systems and kernel bypass networking.",
            role_keywords=self.quant_keywords,
        )

        self.assertEqual(role.role_family, "low_latency_engineer")

    def test_fpga_role_is_classified(self) -> None:
        role = classify_role(
            "FPGA Engineer Intern",
            "Work with Verilog and low latency hardware acceleration.",
            role_keywords=self.quant_keywords,
        )

        self.assertEqual(role.role_family, "fpga_engineer")

    def test_quant_research_role_is_classified(self) -> None:
        role = classify_role(
            "Quantitative Research Intern",
            "Use statistics and optimization for alpha research.",
            role_keywords=self.quant_keywords,
        )

        self.assertEqual(role.role_family, "quant_research")

    def test_quant_trading_role_is_classified(self) -> None:
        role = classify_role(
            "Quantitative Trading Intern",
            "Support market making and options trading decisions.",
            role_keywords=self.quant_keywords,
        )

        self.assertEqual(role.role_family, "quant_trading")

    def test_market_data_role_is_classified(self) -> None:
        role = classify_role(
            "Market Data Engineer Intern",
            "Build real-time data feed handlers and streaming systems.",
            role_keywords=self.quant_keywords,
        )

        self.assertEqual(role.role_family, "market_data_engineer")

    def test_infrastructure_role_is_classified(self) -> None:
        role = classify_role(
            "Infrastructure Engineer Intern",
            "Own distributed systems, Linux services, and cloud observability.",
            role_keywords=self.quant_keywords,
        )

        self.assertEqual(role.role_family, "infrastructure_engineer")

    def test_sales_and_trading_analyst_is_not_misclassified_as_engineering(self) -> None:
        role = classify_role(
            "Sales and Trading Summer Analyst",
            "Support the trading desk and client coverage teams.",
            role_keywords=self.quant_keywords,
        )

        self.assertIn(role.role_family, {"finance_analyst", "trading_operations", "other"})
        self.assertNotIn(role.role_family, {"software_engineer_trading", "trading_systems_engineer"})

    def test_unknown_generic_role_returns_low_confidence(self) -> None:
        role = classify_role(
            "Campus Ambassador",
            "Promote events and brand awareness on campus.",
            role_keywords=self.quant_keywords,
        )

        self.assertIn(role.role_family, {"unknown", "other"})
        self.assertLessEqual(role.confidence, 0.2)

    def test_evidence_is_nonempty_for_confident_classification(self) -> None:
        role = classify_role(
            "Quantitative Trading Intern",
            "Market making and risk taking on options books.",
            role_keywords=self.quant_keywords,
        )

        self.assertGreater(role.confidence, 0.5)
        self.assertTrue(role.evidence)

    def test_negative_keywords_reduce_engineering_score(self) -> None:
        role = classify_role(
            "Software Engineer Intern",
            "This is a sales-focused client services internship with marketing rotation.",
            role_keywords=self.quant_keywords,
        )

        self.assertNotEqual(role.role_family, "software_engineer_trading")

    def test_pack_role_keywords_can_be_loaded_and_used(self) -> None:
        role_keywords = load_pack_role_keywords("quant_engineering")
        role = classify_role(
            "Software Engineer Intern, Trading Systems",
            "Build trading systems.",
            role_keywords=role_keywords,
        )

        self.assertIsInstance(role, ClassifiedRole)
        self.assertNotEqual(role.role_family, "unknown")

    def test_fixture_role_keywords_can_be_loaded_by_pack_loader(self) -> None:
        role_keywords = load_pack_role_keywords("fixtures", root=Path("tests"))
        role = classify_role(
            "Trading Systems Intern",
            "Build trading systems and market data services.",
            role_keywords=role_keywords,
        )

        self.assertEqual(role.role_family, "trading_systems_engineer")

    def test_classifier_is_deterministic(self) -> None:
        first = classify_role(
            "Low Latency C++ Intern",
            "Optimize performance critical systems and kernel bypass networking.",
            role_keywords=self.quant_keywords,
        )
        second = classify_role(
            "Low Latency C++ Intern",
            "Optimize performance critical systems and kernel bypass networking.",
            role_keywords=self.quant_keywords,
        )

        self.assertEqual(first.model_dump(), second.model_dump())

    def test_existing_job_can_be_updated_with_classified_role(self) -> None:
        now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        job = Job(
            id="job-1",
            company_id="company-1",
            company_name="Example",
            title="Market Data Engineer Intern",
            description="Build exchange data feed handlers and streaming systems.",
            apply_url="https://example.com/apply",
            source_url="https://example.com/jobs/1",
            source_type="lever",
            role=ClassifiedRole(role_family="unknown", confidence=0.0),
            season=None,
            year=None,
            locations=[],
            remote_type=None,
            status=JobStatusInfo(status="unknown", confidence=0.0, checked_at=now),
            eligibility=EligibilityInfo(),
            scores=JobScores(),
            first_seen=now,
            last_seen=now,
            last_verified=now,
        )

        updated = classify_job_role(job, role_keywords=self.quant_keywords)

        self.assertEqual(updated.role.role_family, "market_data_engineer")
        self.assertEqual(updated.id, job.id)
