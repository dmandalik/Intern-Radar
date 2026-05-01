"""Hidden-gem scoring."""

from __future__ import annotations

from internradar.core.models import Job

DEPRIORITIZED_ROLE_FAMILIES = {"finance_analyst", "trading_operations", "other", "unknown"}


def score_hidden_gem(
    job: Job,
    *,
    prestige_score: float,
    role_fit_score: float,
    technical_depth_score: float,
    freshness_score: float,
    eligibility_score: float,
) -> tuple[float, list[str]]:
    """Score whether a role looks like a credible hidden gem."""
    low_visibility_score, low_visibility_evidence = _low_visibility(job, prestige_score)
    technical_relevance_score = round((technical_depth_score * 0.6) + (role_fit_score * 0.4), 2)
    firm_quality_score = _firm_quality(prestige_score)

    raw_score = (
        (0.25 * low_visibility_score)
        + (0.25 * technical_relevance_score)
        + (0.20 * eligibility_score)
        + (0.15 * freshness_score)
        + (0.15 * firm_quality_score)
    )

    evidence = list(low_visibility_evidence)
    evidence.append(f"Technical relevance blended role fit ({role_fit_score:.0f}) and depth ({technical_depth_score:.0f}).")
    evidence.append(f"Eligibility contributed {eligibility_score:.0f}.")
    evidence.append(f"Freshness contributed {freshness_score:.0f}.")

    if job.role.role_family in DEPRIORITIZED_ROLE_FAMILIES or technical_depth_score < 40.0:
        raw_score = min(raw_score, 20.0)
        evidence.append("Role is not technical enough to be a strong hidden gem.")
    elif role_fit_score < 50.0 or technical_depth_score < 50.0:
        raw_score = min(raw_score, 35.0)
        evidence.append("Role relevance is too weak for a top hidden-gem ranking.")

    if job.status.status == "closed":
        raw_score = min(raw_score, 10.0)
        evidence.append("Closed jobs are not strong hidden gems for current applications.")
    elif job.status.status in {"requires_login", "unknown"}:
        raw_score = min(raw_score, 30.0)
        evidence.append(f"Status {job.status.status} limits hidden-gem confidence.")

    return round(max(0.0, min(100.0, raw_score)), 2), evidence[:8]


def _low_visibility(job: Job, prestige_score: float) -> tuple[float, list[str]]:
    if prestige_score >= 95.0:
        score = 20.0
        evidence = ["S+ prestige makes the role highly visible rather than hidden."]
    elif prestige_score >= 90.0:
        score = 35.0
        evidence = ["Top-tier prestige makes the role somewhat obvious."]
    elif prestige_score >= 80.0:
        score = 70.0
        evidence = ["A-tier prestige keeps the firm credible while still less saturated than S+ names."]
    elif prestige_score >= 70.0:
        score = 82.0
        evidence = ["B-tier prestige suggests a credible but less obvious firm."]
    elif prestige_score >= 60.0:
        score = 88.0
        evidence = ["C-tier prestige increases hidden-gem visibility potential."]
    else:
        score = 75.0
        evidence = ["Unknown prestige keeps visibility moderate until more evidence is available."]

    if job.source_type == "custom_page":
        score = min(100.0, score + 10.0)
        evidence.append("Custom career page sourcing suggests lower visibility.")
    elif job.source_type not in {"greenhouse", "lever"}:
        score = min(100.0, score + 5.0)
        evidence.append(f"Source type '{job.source_type}' is less obvious than major ATS feeds.")

    return score, evidence


def _firm_quality(prestige_score: float) -> float:
    if prestige_score >= 95.0:
        return 85.0
    if prestige_score >= 90.0:
        return 80.0
    if prestige_score >= 80.0:
        return 75.0
    if prestige_score >= 70.0:
        return 70.0
    if prestige_score >= 60.0:
        return 62.0
    return 55.0


__all__ = ["score_hidden_gem"]
