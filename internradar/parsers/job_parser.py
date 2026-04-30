"""Normalize raw collector jobs into stable core job models."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from typing import Any

from internradar.core.config import AppConfig
from internradar.core.models import (
    ClassifiedRole,
    Company,
    EligibilityInfo,
    Job,
    JobScores,
    JobStatusInfo,
    RawJob,
)
from internradar.parsers.location_parser import parse_location
from internradar.parsers.season_parser import parse_season_and_year
from internradar.parsers.text_cleaner import clean_text
from internradar.verification.page_hash import hash_job_content
from internradar.verification.url_utils import canonicalize_url as verification_canonicalize_url

SAFE_ATS_ID_KEYS = ("id", "job_id", "posting_id", "requisition_id")
SLUGIFY_NON_ALNUM_PATTERN = re.compile(r"[^a-z0-9]+")


def normalize_raw_job(
    raw_job: RawJob,
    company: Company | None = None,
    existing_job: Job | None = None,
    config: AppConfig | None = None,
) -> Job:
    """Convert a raw collector job into a normalized Job model."""
    del config

    now = datetime.now(UTC)
    title = clean_text(raw_job.title) or "Untitled Job"
    description = clean_text(raw_job.description_raw) or None
    source_url = canonicalize_url(raw_job.url)
    apply_url = canonicalize_url(raw_job.apply_url or raw_job.url)
    season_result = parse_season_and_year(title, description)
    location_result = parse_location(raw_job.location_raw, description)
    company_id = _resolve_company_id(raw_job, company)
    company_name = clean_text(company.name if company is not None else raw_job.company_name) or raw_job.company_name
    prestige_tier = company.default_prestige_tier if company is not None else None

    first_seen = existing_job.first_seen if existing_job is not None else now
    job_id = (
        existing_job.id
        if existing_job is not None and existing_job.company_id == company_id and existing_job.source_type == raw_job.source_type
        else generate_stable_job_id(
            raw_job,
            company=company,
            cleaned_title=title,
            canonical_url=source_url,
            season=season_result.season,
            year=season_result.year,
            locations=location_result.locations,
        )
    )

    return Job(
        id=job_id,
        company_id=company_id,
        company_name=company_name,
        title=title,
        description=description,
        apply_url=apply_url,
        source_url=source_url,
        source_type=raw_job.source_type,
        role=ClassifiedRole(role_family="unknown", confidence=0.0),
        season=season_result.season,
        year=season_result.year,
        locations=location_result.locations,
        remote_type=location_result.remote_type,
        status=JobStatusInfo(
            status="unknown",
            confidence=0.0,
            evidence=["normalized without status verification"],
            checked_at=now,
        ),
        eligibility=EligibilityInfo(),
        scores=JobScores(),
        prestige_tier=prestige_tier,
        tags=[],
        first_seen=first_seen,
        last_seen=now,
        last_verified=now,
        content_hash=compute_content_hash(title=title, description=description, source_url=source_url),
    )


def generate_stable_job_id(
    raw_job: RawJob,
    *,
    company: Company | None = None,
    cleaned_title: str | None = None,
    canonical_url: str | None = None,
    season: str | None = None,
    year: int | None = None,
    locations: list[str] | None = None,
) -> str:
    """Generate a deterministic, URL-safe ID for a normalized job."""
    company_slug = _slugify(company.id if company is not None else raw_job.company_id or raw_job.company_name)
    source_slug = _slugify(raw_job.source_type)
    ats_id = _extract_strong_ats_id(raw_job.raw_payload)
    if ats_id is not None:
        return f"{company_slug}-{source_slug}-{_slugify(ats_id)}"

    resolved_url = canonical_url or canonicalize_url(raw_job.url)
    if resolved_url:
        url_hash = _short_hash(resolved_url)
        return f"{company_slug}-{source_slug}-{url_hash}"

    title_slug = _slugify(cleaned_title or raw_job.title)[:60] or "job"
    location_basis = "|".join(locations or [])
    suffix = _short_hash("|".join(filter(None, [title_slug, season or "", str(year or ""), location_basis])))
    return f"{company_slug}-{source_slug}-{title_slug}-{suffix}"


def canonicalize_url(url: str | None) -> str:
    """Normalize a URL for stable identity and later persistence."""
    return verification_canonicalize_url(url)


def compute_content_hash(*, title: str, description: str | None, source_url: str) -> str:
    """Compute a stable content hash for a normalized job."""
    return hash_job_content(title, description, source_url)[:16]


def _resolve_company_id(raw_job: RawJob, company: Company | None) -> str:
    if company is not None:
        return company.id
    if raw_job.company_id:
        return raw_job.company_id
    return _slugify(raw_job.company_name) or "unknown-company"


def _extract_strong_ats_id(raw_payload: dict[str, Any]) -> str | None:
    for key in SAFE_ATS_ID_KEYS:
        value = raw_payload.get(key)
        if isinstance(value, (str, int)) and str(value).strip():
            return str(value).strip()
    return None


def _slugify(value: str | None) -> str:
    if value is None:
        return "unknown"
    collapsed = SLUGIFY_NON_ALNUM_PATTERN.sub("-", value.casefold()).strip("-")
    return collapsed or "unknown"


def _short_hash(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]


__all__ = [
    "canonicalize_url",
    "compute_content_hash",
    "generate_stable_job_id",
    "normalize_raw_job",
]
