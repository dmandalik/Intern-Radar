"""Verification and deduplication helpers for Intern Radar."""

from internradar.verification.duplicate_detector import (
    DuplicateGroup,
    deduplicate_jobs,
    find_duplicates,
)
from internradar.verification.page_hash import hash_job_content, hash_text
from internradar.verification.status_checker import check_job_status
from internradar.verification.url_utils import (
    canonicalize_url,
    extract_domain,
    safe_url_hash,
    same_canonical_url,
)

__all__ = [
    "DuplicateGroup",
    "canonicalize_url",
    "check_job_status",
    "deduplicate_jobs",
    "extract_domain",
    "find_duplicates",
    "hash_job_content",
    "hash_text",
    "safe_url_hash",
    "same_canonical_url",
]
