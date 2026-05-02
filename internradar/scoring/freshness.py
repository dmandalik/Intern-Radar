"""Freshness scoring from scan timestamps and status."""

from __future__ import annotations

from datetime import UTC, datetime

from internradar.core.models import Job


def score_freshness(
    job: Job,
    *,
    now: datetime | None = None,
    apply_now_mode: bool = False,
) -> tuple[float, list[str]]:
    """Score how actionable or fresh a job appears."""
    reference_time = now or datetime.now(UTC)
    latest_seen = max(job.last_verified, job.last_seen, job.first_seen)
    age_days = max(0, (reference_time - latest_seen).days)

    if apply_now_mode and job.status.status == "closed":
        return 0.0, ["Job is marked closed, so freshness is zero in apply-now mode."]

    if age_days == 0:
        score = 100.0
    elif age_days <= 3:
        score = 90.0
    elif age_days <= 7:
        score = 75.0
    elif age_days <= 30:
        score = 55.0
    else:
        score = 35.0

    if job.status.status == "closed":
        score = min(score, 15.0)
    elif job.status.status == "stale":
        score = min(score, 25.0)
    elif job.status.status == "coming_soon":
        score = min(85.0, score + 5.0)

    explanation = [f"Job was last verified {age_days} day(s) ago."]
    if job.status.status != "unknown":
        explanation.append(f"Current status is {job.status.status}.")
    return round(score, 2), explanation


__all__ = ["score_freshness"]
