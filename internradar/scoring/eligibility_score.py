"""Eligibility-fit scoring."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from internradar.core.models import Job
from internradar.parsers.eligibility_parser import evaluate_candidate_eligibility


def score_eligibility(
    job: Job,
    *,
    config: Mapping[str, Any] | None = None,
) -> tuple[float, list[str]]:
    """Score candidate eligibility match conservatively."""
    candidate_config = _candidate_config(config)
    if candidate_config is not None:
        match = evaluate_candidate_eligibility(job.eligibility, candidate_config)
        explanation = match.explanation or ["Candidate eligibility was evaluated from explicit profile data."]
        if match.blockers:
            explanation.extend(match.blockers)
        return round(match.score * 100.0, 2), explanation[:8]

    score = 60.0
    explanation = ["No candidate profile was configured, so eligibility started from a neutral score."]
    eligibility = job.eligibility

    if eligibility.undergrad_friendly is True:
        score += 15.0
        explanation.append("Posting appears undergraduate-friendly.")
    elif eligibility.undergrad_friendly is False:
        score -= 20.0
        explanation.append("Posting does not appear undergraduate-friendly.")

    if eligibility.freshman_sophomore_friendly is True:
        score += 8.0
        explanation.append("Posting explicitly welcomes freshmen or sophomores.")

    if eligibility.sponsorship == "not_available":
        score -= 10.0
        explanation.append("Posting says sponsorship is not available.")
    elif eligibility.sponsorship in {"available", "maybe"}:
        score += 5.0
        explanation.append(f"Posting indicates sponsorship is {eligibility.sponsorship}.")

    if eligibility.requires_phd:
        score -= 25.0
        explanation.append("Posting requires a PhD.")
    elif eligibility.requires_masters:
        score -= 15.0
        explanation.append("Posting requires a master's-level candidate.")

    if eligibility.graduation_years:
        score += 5.0
        explanation.append(f"Posting lists accepted graduation years: {eligibility.graduation_years}.")

    if eligibility.majors:
        score += 5.0
        explanation.append(f"Posting lists majors or fields such as {eligibility.majors[0]}.")

    if eligibility.confidence == 0.0:
        score = min(score, 60.0)
        explanation.append("Eligibility requirements are mostly unknown.")

    score = max(0.0, min(100.0, score))
    return round(score, 2), explanation[:8]


def _candidate_config(config: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(config, Mapping):
        return None
    candidate = config.get("candidate")
    return dict(candidate) if isinstance(candidate, Mapping) else None


__all__ = ["score_eligibility"]
