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
    source_visibility_count: int = 1,
    appears_in_github_list: bool = False,
) -> tuple[float, list[str]]:
    """Score whether a role looks like a credible hidden gem."""
    low_visibility_score, low_visibility_evidence = _low_visibility(
        job,
        prestige_score,
        source_visibility_count=source_visibility_count,
        appears_in_github_list=appears_in_github_list,
    )
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


def visibility_signal(
    *,
    source_type: str,
    source_visibility_count: int = 1,
    appears_in_github_list: bool = False,
) -> tuple[float, list[str]]:
    """Return a visibility adjustment based on source breadth and public-list presence."""
    adjustment = 0.0
    evidence: list[str] = []

    if source_type == "custom_page":
        adjustment += 10.0
        evidence.append("Custom career page sourcing suggests lower visibility.")
    elif source_type == "github_list" or appears_in_github_list:
        adjustment -= 12.0
        evidence.append("Public GitHub internship list presence makes the role more visible.")
    elif source_type not in {"greenhouse", "lever"}:
        adjustment += 5.0
        evidence.append(f"Source type '{source_type}' is less obvious than major ATS feeds.")

    if source_visibility_count > 1:
        penalty = min(15.0, float(source_visibility_count - 1) * 4.0)
        adjustment -= penalty
        evidence.append(f"Appearing in {source_visibility_count} discovery sources makes the role easier to find.")

    return adjustment, evidence


def _low_visibility(
    job: Job,
    prestige_score: float,
    *,
    source_visibility_count: int,
    appears_in_github_list: bool,
) -> tuple[float, list[str]]:
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

    adjustment, visibility_evidence = visibility_signal(
        source_type=job.source_type,
        source_visibility_count=source_visibility_count,
        appears_in_github_list=appears_in_github_list,
    )
    score = max(0.0, min(100.0, score + adjustment))
    evidence.extend(visibility_evidence)

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


__all__ = ["score_hidden_gem", "visibility_signal"]
