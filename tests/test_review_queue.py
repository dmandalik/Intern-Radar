from __future__ import annotations

import unittest

from internradar.review.manual_review import build_review_queue


def make_serialized_job(
    *,
    job_id: str,
    status: str = "open",
    role_confidence: float = 0.9,
    eligibility_confidence: float = 0.5,
    season: str | None = "Summer",
    year: int | None = 2027,
    hidden_gem_score: float = 20.0,
    opportunity_score: float = 50.0,
    reviewed: bool = False,
    description: str | None = "Build systems in C++.",
) -> dict[str, object]:
    return {
        "id": job_id,
        "company_name": "Example Firm",
        "title": f"Role {job_id}",
        "status": status,
        "role_family": "software_engineer_trading",
        "role_confidence": role_confidence,
        "role_evidence": ["title matched strong keyword"],
        "eligibility": {"confidence": eligibility_confidence, "raw_evidence": ["Bachelor's degree"]},
        "season": season,
        "year": year,
        "description": description,
        "scores": {"hidden_gem_score": hidden_gem_score, "opportunity_score": opportunity_score},
        "status_evidence": ["job is listed in current source feed"],
        "score_explanation": ["Strong technical fit"],
        "apply_url": "https://example.com/apply",
        "source_url": "https://example.com/source",
        "application_status": "",
        "reviewed": reviewed,
    }


class TestReviewQueue(unittest.TestCase):
    def test_review_queue_includes_unknown_status_job(self) -> None:
        queue = build_review_queue([make_serialized_job(job_id="job-1", status="unknown")])

        self.assertEqual(queue[0].job_id, "job-1")
        self.assertIn("unknown status", queue[0].reasons)

    def test_review_queue_includes_low_confidence_role_job(self) -> None:
        queue = build_review_queue([make_serialized_job(job_id="job-1", role_confidence=0.2)])

        self.assertIn("low-confidence role classification", queue[0].reasons)

    def test_review_queue_includes_missing_season_year_job(self) -> None:
        queue = build_review_queue([make_serialized_job(job_id="job-1", season=None, year=None)])

        self.assertIn("missing season/year", queue[0].reasons)

    def test_review_queue_excludes_reviewed_job(self) -> None:
        queue = build_review_queue([make_serialized_job(job_id="job-1", status="unknown", reviewed=True)])

        self.assertEqual(queue, [])

    def test_hidden_gem_filter_only_keeps_high_signal_jobs(self) -> None:
        queue = build_review_queue(
            [
                make_serialized_job(job_id="job-1", hidden_gem_score=90),
                make_serialized_job(job_id="job-2", hidden_gem_score=40),
            ],
            hidden_gems_only=True,
            include_all=True,
        )

        self.assertEqual([item.job_id for item in queue], ["job-1"])
