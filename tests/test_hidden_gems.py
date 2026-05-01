from __future__ import annotations

import unittest
from datetime import UTC, datetime

from internradar.core.models import ClassifiedRole, EligibilityInfo, Job, JobScores, JobStatusInfo
from internradar.scoring.opportunity_score import score_job


def make_hidden_gem_job(
    *,
    title: str,
    description: str,
    role_family: str,
    prestige_tier: str | None,
    source_type: str,
    status: str = "open",
) -> Job:
    timestamp = datetime(2026, 5, 1, 12, 0, tzinfo=UTC)
    return Job(
        id=f"{role_family}-{source_type}",
        company_id="firm",
        company_name="Example Firm",
        title=title,
        description=description,
        apply_url="https://example.com/apply",
        source_url="https://example.com/job",
        source_type=source_type,
        role=ClassifiedRole(role_family=role_family, confidence=0.9, evidence=[f"classified as {role_family}"]),
        season="Summer",
        year=2027,
        locations=["Chicago, IL"],
        remote_type="onsite",
        status=JobStatusInfo(status=status, confidence=0.9, evidence=[f"status is {status}"], checked_at=timestamp),
        eligibility=EligibilityInfo(
            degree_levels=["bachelors"],
            graduation_years=[2027],
            majors=["computer science"],
            undergrad_friendly=True,
            confidence=0.6,
            raw_evidence=["Bachelor's degree in Computer Science"],
        ),
        scores=JobScores(),
        prestige_tier=prestige_tier,
        tags=[],
        first_seen=timestamp,
        last_seen=timestamp,
        last_verified=timestamp,
        content_hash="hash",
    )


class TestHiddenGems(unittest.TestCase):
    def test_technical_fresh_credible_non_s_plus_role_scores_high_as_hidden_gem(self) -> None:
        scored = score_job(
            make_hidden_gem_job(
                title="Low Latency C++ Intern",
                description="Build low latency trading infrastructure in C++ with market data and kernel bypass.",
                role_family="low_latency_engineer",
                prestige_tier="B",
                source_type="custom_page",
            ),
            preset="hidden_gems",
        )
        self.assertGreaterEqual(scored.scores.hidden_gem_score, 75.0)

    def test_s_plus_obvious_role_has_lower_hidden_gem_than_niche_role(self) -> None:
        obvious = score_job(
            make_hidden_gem_job(
                title="Software Engineer Intern",
                description="Distributed systems and backend engineering.",
                role_family="software_engineer_trading",
                prestige_tier="S+",
                source_type="greenhouse",
            ),
            preset="hidden_gems",
        )
        niche = score_job(
            make_hidden_gem_job(
                title="Market Data Engineer Intern",
                description="Build market data feed handlers and exchange connectivity systems.",
                role_family="market_data_engineer",
                prestige_tier="B",
                source_type="custom_page",
            ),
            preset="hidden_gems",
        )
        self.assertLess(obvious.scores.hidden_gem_score, niche.scores.hidden_gem_score)
        self.assertGreater(obvious.scores.opportunity_score, 0.0)

    def test_low_quality_obscure_sales_role_does_not_score_high_hidden_gem(self) -> None:
        scored = score_job(
            make_hidden_gem_job(
                title="Sales and Trading Summer Analyst",
                description="Client services and operations support for sales teams.",
                role_family="finance_analyst",
                prestige_tier="C",
                source_type="custom_page",
            ),
            preset="hidden_gems",
        )
        self.assertLessEqual(scored.scores.hidden_gem_score, 20.0)
