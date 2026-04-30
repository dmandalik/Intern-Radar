"""Pure status inference for normalized or raw jobs."""

from __future__ import annotations

from datetime import UTC, datetime
import html
import re
from typing import Any

from internradar.core.models import JobStatusInfo

WHITESPACE_PATTERN = re.compile(r"\s+")

ACTIVE_ATS_SOURCES = {"greenhouse", "lever"}
OPEN_SIGNALS = (
    "apply now",
    "apply for this job",
    "submit application",
    "application form",
    "application",
)
CLOSED_SIGNALS = (
    "no longer accepting applications",
    "this job is closed",
    "position has been filled",
    "applications are closed",
    "job not found",
    "404",
    "no longer available",
    "this posting has expired",
)
COMING_SOON_SIGNALS = (
    "check back next year",
    "check back soon",
    "applications will open",
    "join our talent community",
    "summer 2027 applications",
    "applications for summer 2026 are closed",
    "not currently accepting applications",
)
LOGIN_SIGNALS = (
    "login to apply",
    "sign in to continue",
    "create an account to view",
    "log in to view",
    "authentication required",
)


def check_job_status(
    job_or_raw_job: Any,
    *,
    page_text: str | None = None,
    http_status: int | None = None,
    source_type: str | None = None,
    listed_in_current_source: bool = True,
) -> JobStatusInfo:
    """Infer a job status conservatively from page text and source metadata."""
    checked_at = datetime.now(UTC)
    inferred_source = (source_type or getattr(job_or_raw_job, "source_type", "") or "").casefold()

    text_candidates = [
        page_text,
        getattr(job_or_raw_job, "description", None),
        getattr(job_or_raw_job, "description_raw", None),
    ]
    normalized_text = clean_text_lower(" ".join(part for part in text_candidates if part))
    evidence: list[str] = []

    if http_status == 404:
        evidence.append("HTTP status 404 indicates the posting is no longer available.")
        return JobStatusInfo(status="closed", confidence=0.98, evidence=evidence, checked_at=checked_at)

    closed_signal = _first_signal(normalized_text, CLOSED_SIGNALS)
    if closed_signal:
        evidence.append(f'page matched closed signal "{closed_signal}"')
        return JobStatusInfo(status="closed", confidence=0.95, evidence=evidence, checked_at=checked_at)

    coming_soon_signal = _first_signal(normalized_text, COMING_SOON_SIGNALS)
    if coming_soon_signal:
        evidence.append(f'page matched coming-soon signal "{coming_soon_signal}"')
        return JobStatusInfo(status="coming_soon", confidence=0.82, evidence=evidence, checked_at=checked_at)

    login_signal = _first_signal(normalized_text, LOGIN_SIGNALS)
    if login_signal:
        evidence.append(f'page matched login-required signal "{login_signal}"')
        return JobStatusInfo(status="requires_login", confidence=0.9, evidence=evidence, checked_at=checked_at)

    open_signal = _first_signal(normalized_text, OPEN_SIGNALS)
    if listed_in_current_source and inferred_source in ACTIVE_ATS_SOURCES:
        evidence.append(f"job is listed in the current {inferred_source} source feed")
        if open_signal:
            evidence.append(f'page matched open signal "{open_signal}"')
            return JobStatusInfo(status="open", confidence=0.9, evidence=evidence, checked_at=checked_at)
        return JobStatusInfo(status="likely_open", confidence=0.7, evidence=evidence, checked_at=checked_at)

    if open_signal:
        evidence.append(f'page matched open signal "{open_signal}"')
        return JobStatusInfo(status="likely_open", confidence=0.68, evidence=evidence, checked_at=checked_at)

    posted_at = getattr(job_or_raw_job, "posted_at", None)
    if posted_at is not None and not listed_in_current_source:
        age_days = (checked_at - posted_at).days
        if age_days >= 180:
            evidence.append(f"posting is {age_days} days old and is no longer listed in the current source")
            return JobStatusInfo(status="stale", confidence=0.65, evidence=evidence, checked_at=checked_at)

    evidence.append("no explicit open, closed, login, or coming-soon signals were found")
    return JobStatusInfo(status="unknown", confidence=0.2, evidence=evidence, checked_at=checked_at)


def _first_signal(text: str, signals: tuple[str, ...]) -> str | None:
    for signal in signals:
        if signal in text:
            return _normalize_text(signal)
    return None


def _normalize_text(text: str | None) -> str:
    if text is None:
        return ""
    cleaned = html.unescape(str(text)).replace("\xa0", " ").strip()
    return WHITESPACE_PATTERN.sub(" ", cleaned)


def clean_text_lower(text: str | None) -> str:
    return _normalize_text(text).casefold()


__all__ = ["check_job_status"]
