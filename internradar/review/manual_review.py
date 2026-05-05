"""Manual review queue and terminal-friendly review helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

HIGH_HIDDEN_GEM_THRESHOLD = 80.0
HIGH_OPPORTUNITY_THRESHOLD = 85.0
LOW_ROLE_CONFIDENCE_THRESHOLD = 0.55
LOW_ELIGIBILITY_CONFIDENCE_THRESHOLD = 0.35


@dataclass(slots=True)
class ReviewItem:
    job_id: str
    company: str
    title: str
    reasons: list[str] = field(default_factory=list)
    current_fields: dict[str, Any] = field(default_factory=dict)
    evidence_snippets: list[str] = field(default_factory=list)
    apply_url: str | None = None
    source_url: str | None = None


def build_review_queue(
    jobs: list[dict[str, Any]],
    *,
    status: str | None = None,
    hidden_gems_only: bool = False,
    low_confidence_only: bool = False,
    include_all: bool = False,
    limit: int | None = None,
) -> list[ReviewItem]:
    """Build a review queue from serialized dashboard jobs."""
    items: list[ReviewItem] = []
    normalized_status = status.casefold() if isinstance(status, str) and status.strip() else None
    for job in jobs:
        if job.get("reviewed"):
            continue
        if normalized_status and str(job.get("status", "")).casefold() != normalized_status:
            continue

        reasons = _review_reasons(job)
        if hidden_gems_only and float(job["scores"]["hidden_gem_score"]) < HIGH_HIDDEN_GEM_THRESHOLD:
            continue
        if low_confidence_only and not _has_low_confidence_reason(reasons):
            continue
        if not include_all and not reasons:
            continue

        item = ReviewItem(
            job_id=job["id"],
            company=job["company_name"],
            title=job["title"],
            reasons=reasons or ["manual review requested"],
            current_fields={
                "status": job["status"],
                "role_family": job["role_family"],
                "role_confidence": job["role_confidence"],
                "eligibility_confidence": float(job["eligibility"]["confidence"]),
                "season": job["season"],
                "year": job["year"],
                "application_status": job.get("application_status", ""),
                "opportunity_score": float(job["scores"]["opportunity_score"]),
                "hidden_gem_score": float(job["scores"]["hidden_gem_score"]),
            },
            evidence_snippets=_evidence_snippets(job),
            apply_url=job.get("apply_url"),
            source_url=job.get("source_url"),
        )
        items.append(item)

    items.sort(
        key=lambda item: (
            -len(item.reasons),
            -float(item.current_fields.get("hidden_gem_score", 0.0)),
            -float(item.current_fields.get("opportunity_score", 0.0)),
            item.company.casefold(),
            item.title.casefold(),
        ),
    )
    if limit is not None:
        return items[:limit]
    return items


def _review_reasons(job: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    status = str(job.get("status", ""))
    role_confidence = float(job.get("role_confidence", 0.0))
    eligibility_confidence = float(job.get("eligibility", {}).get("confidence", 0.0))
    opportunity_score = float(job.get("scores", {}).get("opportunity_score", 0.0))
    hidden_gem_score = float(job.get("scores", {}).get("hidden_gem_score", 0.0))

    if status in {"unknown", "requires_login"}:
        reasons.append("unknown status")
    if role_confidence < LOW_ROLE_CONFIDENCE_THRESHOLD:
        reasons.append("low-confidence role classification")
    if eligibility_confidence < LOW_ELIGIBILITY_CONFIDENCE_THRESHOLD:
        reasons.append("low-confidence eligibility")
    if not job.get("description"):
        reasons.append("missing description")
    if job.get("season") is None or job.get("year") is None:
        reasons.append("missing season/year")
    if hidden_gem_score >= HIGH_HIDDEN_GEM_THRESHOLD:
        reasons.append("new high hidden-gem signal")
    if opportunity_score >= HIGH_OPPORTUNITY_THRESHOLD and (
        role_confidence < LOW_ROLE_CONFIDENCE_THRESHOLD
        or eligibility_confidence < LOW_ELIGIBILITY_CONFIDENCE_THRESHOLD
        or status in {"unknown", "requires_login"}
    ):
        reasons.append("high opportunity score but low confidence")
    return reasons


def _has_low_confidence_reason(reasons: list[str]) -> bool:
    return any("low-confidence" in reason or "unknown status" == reason for reason in reasons)


def _evidence_snippets(job: dict[str, Any]) -> list[str]:
    seen: set[str] = set()
    snippets: list[str] = []
    for group in (
        job.get("role_evidence", []),
        job.get("status_evidence", []),
        job.get("eligibility", {}).get("raw_evidence", []),
        job.get("score_explanation", []),
    ):
        for entry in group:
            text = str(entry).strip()
            if not text or text in seen:
                continue
            snippets.append(text)
            seen.add(text)
            if len(snippets) >= 6:
                return snippets
    return snippets
