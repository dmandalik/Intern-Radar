from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from internradar.core.models import ClassifiedRole, Company, EligibilityInfo, Job, JobScores, JobStatusInfo
from internradar.scoring.eligibility_score import score_eligibility
from internradar.scoring.freshness import score_freshness
from internradar.scoring.opportunity_score import score_job
from internradar.scoring.prestige import score_prestige
from internradar.scoring.role_fit import score_role_fit
from internradar.scoring.technical_depth import score_technical_depth


FIXED_NOW = datetime(2026, 5, 1, 12, 0, tzinfo=UTC)


def make_job(
    *,
    title: str = "Software Engineer Intern, Trading Systems",
    description: str = "Build low latency market data systems in C++ and Python.",
    role_family: str = "trading_systems_engineer",
    role_confidence: float = 0.9,
    status: str = "open",
    prestige_tier: str | None = "S",
    source_type: str = "greenhouse",
    eligibility: EligibilityInfo | None = None,
    last_verified: datetime | None = None,
) -> Job:
    timestamp = last_verified or FIXED_NOW
    return Job(
        id="job-123",
        company_id="hudson-river-trading",
        company_name="Hudson River Trading",
        title=title,
        description=description,
        apply_url="https://example.com/apply",
        source_url="https://example.com/job",
        source_type=source_type,
        role=ClassifiedRole(
            role_family=role_family,
            confidence=role_confidence,
            evidence=[f"classified as {role_family}"],
        ),
        season="Summer",
        year=2027,
        locations=["New York, NY"],
        remote_type="onsite",
        status=JobStatusInfo(
            status=status,
            confidence=0.9,
            evidence=[f"status is {status}"],
            checked_at=timestamp,
        ),
        eligibility=eligibility
        or EligibilityInfo(
            degree_levels=["bachelors"],
            graduation_years=[2027, 2028],
            majors=["computer science"],
            undergrad_friendly=True,
            confidence=0.5,
            raw_evidence=["Currently pursuing a Bachelor's degree in Computer Science"],
        ),
        scores=JobScores(),
        prestige_tier=prestige_tier,
        tags=["internship"],
        first_seen=timestamp - timedelta(days=1),
        last_seen=timestamp,
        last_verified=timestamp,
        content_hash="abc123",
    )


class TestScoring(unittest.TestCase):
    def test_prestige_tier_mapping_s_plus_is_100(self) -> None:
        score, explanation, tier = score_prestige(make_job(prestige_tier="S+"))
        self.assertEqual(score, 100.0)
        self.assertEqual(tier, "S+")
        self.assertTrue(explanation)

    def test_unknown_prestige_is_neutral(self) -> None:
        score, _, tier = score_prestige(make_job(prestige_tier=None))
        self.assertEqual(score, 50.0)
        self.assertEqual(tier, "Unknown")

    def test_user_override_beats_company_default(self) -> None:
        company = Company(id="hudson-river-trading", name="Hudson River Trading", default_prestige_tier="S+")
        score, explanation, tier = score_prestige(
            make_job(prestige_tier=None),
            company=company,
            config={"scoring": {"prestige_overrides": {"Hudson River Trading": "B"}}},
        )
        self.assertEqual(score, 70.0)
        self.assertEqual(tier, "B")
        self.assertIn("user override", explanation[0])

    def test_target_role_gets_high_role_fit(self) -> None:
        score, explanation = score_role_fit(make_job(role_family="low_latency_engineer"))
        self.assertGreaterEqual(score, 90.0)
        self.assertTrue(explanation)

    def test_deprioritized_role_gets_low_role_fit(self) -> None:
        score, _ = score_role_fit(make_job(role_family="finance_analyst"))
        self.assertLessEqual(score, 50.0)

    def test_technical_role_gets_high_technical_depth(self) -> None:
        score, explanation = score_technical_depth(
            make_job(
                description="C++ low latency market data systems with exchange connectivity and multithreading.",
                role_family="low_latency_engineer",
            ),
        )
        self.assertGreaterEqual(score, 85.0)
        self.assertTrue(explanation)

    def test_sales_role_gets_low_technical_depth(self) -> None:
        score, _ = score_technical_depth(
            make_job(
                title="Sales and Trading Summer Analyst",
                description="Client services, operations, and marketing support for sales teams.",
                role_family="finance_analyst",
            ),
        )
        self.assertLessEqual(score, 25.0)

    def test_fresh_job_gets_high_freshness(self) -> None:
        score, _ = score_freshness(make_job(last_verified=FIXED_NOW), now=FIXED_NOW)
        self.assertEqual(score, 100.0)

    def test_old_job_gets_lower_freshness(self) -> None:
        score, _ = score_freshness(
            make_job(last_verified=FIXED_NOW - timedelta(days=45)),
            now=FIXED_NOW,
        )
        self.assertEqual(score, 35.0)

    def test_closed_job_gets_low_apply_now_opportunity(self) -> None:
        scored = score_job(
            make_job(status="closed"),
            preset="apply_now",
        )
        self.assertLess(scored.scores.opportunity_score, 50.0)

    def test_eligibility_match_gets_high_score(self) -> None:
        job = make_job()
        score, explanation = score_eligibility(
            job,
            config={
                "candidate": {
                    "degree_level": "bachelors",
                    "graduation_year": 2027,
                    "major": "computer science",
                    "needs_sponsorship": False,
                    "citizenship": "us",
                },
            },
        )
        self.assertGreaterEqual(score, 80.0)
        self.assertTrue(explanation)

    def test_sponsorship_conflict_gets_very_low_score(self) -> None:
        job = make_job(
            eligibility=EligibilityInfo(
                degree_levels=["bachelors"],
                sponsorship="not_available",
                confidence=0.4,
                raw_evidence=["We do not sponsor visas for this position."],
            ),
        )
        score, _ = score_eligibility(
            job,
            config={"candidate": {"degree_level": "bachelors", "needs_sponsorship": True}},
        )
        self.assertLessEqual(score, 5.0)

    def test_phd_only_undergrad_conflict_gets_low_score(self) -> None:
        job = make_job(
            eligibility=EligibilityInfo(
                degree_levels=["phd"],
                requires_phd=True,
                undergrad_friendly=False,
                confidence=0.5,
                raw_evidence=["PhD required"],
            ),
        )
        score, _ = score_eligibility(
            job,
            config={"candidate": {"degree_level": "bachelors"}},
        )
        self.assertLessEqual(score, 10.0)

    def test_scoring_explanations_are_nonempty(self) -> None:
        scored = score_job(make_job())
        self.assertTrue(scored.scores.explanation)

    def test_scoring_is_deterministic(self) -> None:
        first = score_job(make_job(), preset="cs_algo_engineering")
        second = score_job(make_job(), preset="cs_algo_engineering")
        self.assertEqual(first.scores.model_dump(mode="json"), second.scores.model_dump(mode="json"))
