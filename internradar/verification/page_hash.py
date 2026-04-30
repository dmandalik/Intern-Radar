"""Content hashing helpers for verification and deduplication."""

from __future__ import annotations

import hashlib
import html
import re
from internradar.verification.url_utils import canonicalize_url

WHITESPACE_PATTERN = re.compile(r"\s+")


def hash_text(text: str | None) -> str:
    """Hash normalized text deterministically."""
    normalized = _normalize_text(text)
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()


def hash_job_content(title: str | None, description: str | None, url: str | None) -> str:
    """Hash the main normalized job content."""
    payload = "\n".join(
        [
            _normalize_text(title),
            _normalize_text(description),
            canonicalize_url(url),
        ],
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def _normalize_text(text: str | None) -> str:
    if text is None:
        return ""
    cleaned = html.unescape(str(text)).replace("\xa0", " ").strip()
    return WHITESPACE_PATTERN.sub(" ", cleaned)


__all__ = ["hash_job_content", "hash_text"]
