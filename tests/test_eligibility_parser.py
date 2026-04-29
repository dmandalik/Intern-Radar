from __future__ import annotations

import unittest
from datetime import UTC, datetime

from internradar.core.models import (
    ClassifiedRole,
    EligibilityInfo,
    Job,
    JobScores,
    JobStatusInfo,
)
from internradar.parsers.eligibility_parser import (
    CandidateEligibilityMatch,
    apply_job_eligibility,
    evaluate_candidate_eligibility,
    parse_eligibility,
)


class TestEligibilityParser(unittest.TestCase):
    def test_bachelors_and_undergraduate_detection(self) -> None:
        info = parse_eligibility(
            "Software Engineer Intern",
            "Currently pursuing a Bachelor's degree in Computer Science or related Engineering field.",
        )

        self.assertIn("bachelors", info.degree_levels)
        self.assertTrue(info.undergrad_friendly)

    def test_masters_detection(self) -> None:
        info = parse_eligibility(
            "Research Intern",
            "Candidates should be pursuing a Master's degree in Statistics or Machine Learning.",
        )

        self.assertIn("masters", info.degree_levels)

    def test_phd_detection(self) -> None:
        info = parse_eligibility(
            "Research Scientist Intern",
            "Applicants must be pursuing a Ph.D. in Physics or Mathematics.",
        )

        self.assertIn("phd", info.degree_levels)
        self.assertTrue(info.requires_phd)

    def test_phd_required_makes_undergrad_friendly_false(self) -> None:
        info = parse_eligibility(
            "Research Scientist Intern",
            "PhD required for this role.",
        )

        self.assertFalse(info.undergrad_friendly)

    def test_graduation_year_detection(self) -> None:
        info = parse_eligibility(
            "Software Engineer Intern",
            "Students graduating in 2027 are encouraged to apply.",
        )

        self.assertEqual(info.graduation_years, [2027])

    def test_graduation_range_detection(self) -> None:
        info = parse_eligibility(
            "Software Engineer Intern",
            "Expected graduation date between December 2026 and June 2028.",
        )

        self.assertEqual(info.graduation_years, [2026, 2027, 2028])

    def test_class_of_detection(self) -> None:
        info = parse_eligibility(
            "Trading Intern",
            "Open to students in the class of 2028.",
        )

        self.assertEqual(info.graduation_years, [2028])

    def test_freshman_sophomore_friendly_detection(self) -> None:
        info = parse_eligibility(
            "Early Careers Program",
            "Open to first-years and sophomores studying STEM fields.",
        )

        self.assertTrue(info.freshman_sophomore_friendly)
        self.assertIn("freshman", info.class_years)
        self.assertIn("sophomore", info.class_years)

    def test_penultimate_junior_senior_detection(self) -> None:
        info = parse_eligibility(
            "Intern",
            "This opportunity is for junior, senior, or penultimate year students only.",
        )

        self.assertIn("junior", info.class_years)
        self.assertIn("senior", info.class_years)
        self.assertIn("penultimate year", info.class_years)
        self.assertFalse(info.freshman_sophomore_friendly)

    def test_major_extraction(self) -> None:
        info = parse_eligibility(
            "Engineer Intern",
            "Pursuing Computer Science, Electrical Engineering, or related Engineering majors.",
        )

        self.assertIn("computer science", info.majors)
        self.assertIn("electrical engineering", info.majors)
        self.assertIn("engineering", info.majors)

    def test_no_sponsorship_detection(self) -> None:
        info = parse_eligibility(
            "Engineer Intern",
            "Candidates must be legally authorized to work without sponsorship now or in the future.",
        )

        self.assertEqual(info.sponsorship, "not_available")

    def test_sponsorship_available_detection(self) -> None:
        info = parse_eligibility(
            "Engineer Intern",
            "Visa sponsorship may be available for qualified candidates.",
        )

        self.assertEqual(info.sponsorship, "maybe")

    def test_unknown_sponsorship_when_not_stated(self) -> None:
        info = parse_eligibility(
            "Engineer Intern",
            "Build backend systems for trading infrastructure.",
        )

        self.assertEqual(info.sponsorship, "unknown")

    def test_us_citizenship_detection(self) -> None:
        info = parse_eligibility(
            "Hardware Intern",
            "U.S. citizenship required for this position.",
        )

        self.assertEqual(info.citizenship_requirement, "us_citizen_required")

    def test_security_clearance_detection(self) -> None:
        info = parse_eligibility(
            "Systems Intern",
            "Security clearance required before start date.",
        )

        self.assertEqual(info.citizenship_requirement, "security_clearance_required")

    def test_gpa_parsing(self) -> None:
        info = parse_eligibility(
            "Software Intern",
            "Minimum cumulative GPA 3.5 and strong CS fundamentals required.",
        )

        self.assertEqual(info.minimum_gpa, 3.5)

    def test_evidence_snippets_are_included(self) -> None:
        info = parse_eligibility(
            "Software Engineer Intern",
            "Currently pursuing a Bachelor's degree in Computer Science. Expected graduation date between December 2027 and June 2028.",
        )

        self.assertTrue(info.raw_evidence)
        self.assertTrue(any("Bachelor" in snippet or "bachelor" in snippet for snippet in info.raw_evidence))

    def test_confidence_increases_with_multiple_signals(self) -> None:
        info = parse_eligibility(
            "Software Engineer Intern",
            (
                "Currently pursuing a Bachelor's degree in Computer Science. "
                "Students graduating in 2027 or 2028 are eligible. "
                "Minimum GPA of 3.5. We do not sponsor visas. "
                "U.S. citizenship required."
            ),
        )

        self.assertGreaterEqual(info.confidence, 0.7)

    def test_irrelevant_years_are_not_treated_as_graduation_years(self) -> None:
        info = parse_eligibility(
            "Software Intern",
            "Our company was founded in 2001 and expanded in 2026.",
        )

        self.assertEqual(info.graduation_years, [])

    def test_candidate_match_detects_clear_eligibility_match(self) -> None:
        info = parse_eligibility(
            "Software Engineer Intern",
            "Bachelor's degree in Computer Science. Students graduating in 2027 or 2028 are eligible.",
        )

        match = evaluate_candidate_eligibility(
            info,
            {
                "degree_level": "bachelors",
                "graduation_year": 2027,
                "major": "computer science",
                "needs_sponsorship": False,
                "citizenship": "us",
            },
        )

        self.assertIsInstance(match, CandidateEligibilityMatch)
        self.assertGreater(match.score, 0.6)
        self.assertFalse(match.blockers)

    def test_candidate_match_detects_sponsorship_conflict(self) -> None:
        info = parse_eligibility(
            "Software Engineer Intern",
            "We do not sponsor visas for this position.",
        )

        match = evaluate_candidate_eligibility(
            info,
            {
                "degree_level": "bachelors",
                "graduation_year": 2027,
                "major": "computer science",
                "needs_sponsorship": True,
                "citizenship": "canada",
            },
        )

        self.assertLessEqual(match.score, 0.05)
        self.assertTrue(match.blockers)

    def test_candidate_match_detects_undergrad_vs_phd_only_conflict(self) -> None:
        info = parse_eligibility(
            "Research Intern",
            "PhD required in Statistics or Mathematics.",
        )

        match = evaluate_candidate_eligibility(
            info,
            {
                "degree_level": "bachelors",
                "graduation_year": 2027,
                "major": "statistics",
                "needs_sponsorship": False,
                "citizenship": "us",
            },
        )

        self.assertLessEqual(match.score, 0.05)
        self.assertTrue(match.blockers)

    def test_parser_handles_empty_or_none_description_safely(self) -> None:
        info = parse_eligibility("Software Engineer Intern", None)

        self.assertEqual(info.degree_levels, [])
        self.assertEqual(info.graduation_years, [])
        self.assertEqual(info.majors, [])
        self.assertEqual(info.sponsorship, "unknown")
        self.assertEqual(info.confidence, 0.0)

    def test_apply_job_eligibility_updates_job(self) -> None:
        now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        job = Job(
            id="job-1",
            company_id="company-1",
            company_name="Example",
            title="Software Engineer Intern",
            description="Bachelor's degree in Computer Science. Students graduating in 2027 are eligible.",
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

        updated = apply_job_eligibility(job)

        self.assertIn("bachelors", updated.eligibility.degree_levels)
        self.assertEqual(updated.id, job.id)
