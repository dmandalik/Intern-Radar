"""Duplicate detection and merging for normalized jobs."""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Iterable

from internradar.core.models import Job
from internradar.verification.page_hash import hash_job_content
from internradar.verification.url_utils import canonicalize_url

PREFERRED_SOURCE_PRIORITY = {
    "greenhouse": 4,
    "lever": 4,
    "custom_page": 3,
    "ats": 3,
    "github": 1,
    "list": 1,
    "search": 1,
}
STATUS_PRIORITY = {
    "closed": 7,
    "requires_login": 6,
    "coming_soon": 5,
    "open": 4,
    "likely_open": 3,
    "stale": 2,
    "unknown": 1,
}


@dataclass(slots=True)
class DuplicateGroup:
    jobs: list[Job] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)


def find_duplicates(jobs: list[Job]) -> list[DuplicateGroup]:
    """Find deterministic duplicate groups for normalized jobs."""
    parent = list(range(len(jobs)))
    reasons_by_root: dict[int, set[str]] = {}

    for left_index in range(len(jobs)):
        for right_index in range(left_index + 1, len(jobs)):
            reasons = _duplicate_reasons(jobs[left_index], jobs[right_index])
            if not reasons:
                continue
            _union(parent, left_index, right_index)
            root = _find(parent, left_index)
            reasons_by_root.setdefault(root, set()).update(reasons)

    grouped_indexes: dict[int, list[int]] = {}
    for index in range(len(jobs)):
        root = _find(parent, index)
        grouped_indexes.setdefault(root, []).append(index)

    groups: list[DuplicateGroup] = []
    for root in sorted(grouped_indexes, key=lambda group_root: grouped_indexes[group_root][0]):
        indexes = grouped_indexes[root]
        if len(indexes) < 2:
            continue
        groups.append(
            DuplicateGroup(
                jobs=[jobs[index] for index in indexes],
                reasons=sorted(reasons_by_root.get(root, set())),
            ),
        )
    return groups


def deduplicate_jobs(jobs: list[Job]) -> list[Job]:
    """Merge duplicate groups into a deterministic list of jobs."""
    groups = find_duplicates(jobs)
    consumed = {id(job) for group in groups for job in group.jobs}
    merged_jobs = [_merge_group(group) for group in groups]
    unique_jobs = [job for job in jobs if id(job) not in consumed]
    return merged_jobs + unique_jobs


def _duplicate_reasons(left: Job, right: Job) -> list[str]:
    if left.company_id != right.company_id:
        return []

    reasons: list[str] = []
    if _canonical_equals(left.apply_url, right.apply_url):
        reasons.append("same canonical apply URL")
    if _canonical_equals(left.source_url, right.source_url):
        reasons.append("same canonical source URL")

    left_ats_key = _extract_ats_job_key(left)
    right_ats_key = _extract_ats_job_key(right)
    if left_ats_key and left_ats_key == right_ats_key:
        reasons.append("same ATS job ID")

    title_similarity = _title_similarity(left.title, right.title)
    same_season_year = left.season == right.season and left.year == right.year and left.year is not None
    if title_similarity > 92:
        reasons.append("same company with highly similar title")
    elif title_similarity > 85 and same_season_year:
        reasons.append("same company, similar title, and same season/year")

    same_title = left.title.casefold() == right.title.casefold()
    overlapping_locations = set(location.casefold() for location in left.locations) & set(
        location.casefold() for location in right.locations
    )
    if same_title and overlapping_locations:
        reasons.append("same company, same title, and overlapping location")

    if not reasons:
        return []

    if title_similarity > 85 and left.year != right.year and not {
        "same canonical apply URL",
        "same canonical source URL",
        "same ATS job ID",
    } & set(reasons):
        return []

    return reasons


def _merge_group(group: DuplicateGroup) -> Job:
    jobs = group.jobs
    primary = max(
        jobs,
        key=lambda job: (
            PREFERRED_SOURCE_PRIORITY.get(job.source_type, 2),
            len(job.description or ""),
            job.status.confidence,
            job.role.confidence,
        ),
    )
    richest_description = max(jobs, key=lambda job: len(job.description or "")).description
    merged_locations = _dedupe_preserve_order(location for job in jobs for location in job.locations)
    merged_tags = _dedupe_preserve_order(tag for job in jobs for tag in job.tags)
    earliest_first_seen = min(job.first_seen for job in jobs)
    latest_last_seen = max(job.last_seen for job in jobs)
    latest_last_verified = max(job.last_verified for job in jobs)
    best_status = max(
        (job.status for job in jobs),
        key=lambda status: (status.confidence, STATUS_PRIORITY.get(status.status, 0)),
    )
    best_role = max((job.role for job in jobs), key=lambda role: role.confidence)
    best_eligibility = max((job.eligibility for job in jobs), key=lambda eligibility: eligibility.confidence)

    apply_url = next((job.apply_url for job in jobs if job.apply_url), primary.apply_url)
    source_url = next((job.source_url for job in jobs if job.source_url), primary.source_url)
    description = richest_description or primary.description

    merged = primary.model_copy(
        update={
            "description": description,
            "apply_url": apply_url,
            "source_url": source_url,
            "locations": merged_locations,
            "tags": merged_tags,
            "first_seen": earliest_first_seen,
            "last_seen": latest_last_seen,
            "last_verified": latest_last_verified,
            "status": best_status,
            "role": best_role,
            "eligibility": best_eligibility,
            "content_hash": hash_job_content(primary.title, description, source_url),
        },
    )
    return merged


def _canonical_equals(left: str | None, right: str | None) -> bool:
    normalized_left = canonicalize_url(left)
    normalized_right = canonicalize_url(right)
    return bool(normalized_left and normalized_right and normalized_left == normalized_right)


def _extract_ats_job_key(job: Job) -> str | None:
    for url in (job.source_url, job.apply_url):
        normalized = canonicalize_url(url)
        if "greenhouse" in normalized:
            match = _search_pattern(normalized, r"/jobs/(\d+)")
            if match:
                return f"greenhouse:{match}"
        if "lever.co" in normalized:
            match = _search_pattern(normalized, r"/([^/?#]+)/?$")
            if match:
                return f"lever:{match}"
    return None


def _search_pattern(text: str, pattern: str) -> str | None:
    match = __import__("re").search(pattern, text)
    if match:
        return match.group(1)
    return None


def _title_similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, left.casefold(), right.casefold()).ratio() * 100


def _dedupe_preserve_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(value)
    return ordered


def _find(parent: list[int], index: int) -> int:
    while parent[index] != index:
        parent[index] = parent[parent[index]]
        index = parent[index]
    return index


def _union(parent: list[int], left: int, right: int) -> None:
    left_root = _find(parent, left)
    right_root = _find(parent, right)
    if left_root == right_root:
        return
    if left_root < right_root:
        parent[right_root] = left_root
    else:
        parent[left_root] = right_root


__all__ = ["DuplicateGroup", "deduplicate_jobs", "find_duplicates"]
