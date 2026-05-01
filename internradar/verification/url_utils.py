"""Shared URL normalization helpers."""

from __future__ import annotations

import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_QUERY_KEYS = {
    "fbclid",
    "gclid",
    "gh_src",
    "utm_campaign",
    "utm_content",
    "utm_medium",
    "utm_source",
    "utm_term",
}


def canonicalize_url(url: str | None) -> str:
    """Normalize a URL for stable comparison and hashing."""
    if url is None:
        return ""

    raw = str(url).strip()
    if not raw:
        return ""

    parts = urlsplit(raw)
    if not parts.scheme and not parts.netloc:
        return raw

    scheme = parts.scheme.casefold() or "https"
    netloc = _normalize_netloc(parts.netloc, scheme)
    path = re.sub(r"/{2,}", "/", parts.path or "/")
    if path != "/" and path.endswith("/"):
        path = path[:-1]

    query_pairs = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key.casefold() not in TRACKING_QUERY_KEYS
    ]
    query = urlencode(sorted(query_pairs))
    return urlunsplit((scheme, netloc, path, query, ""))


def same_canonical_url(url1: str | None, url2: str | None) -> bool:
    """Return True when two URLs normalize to the same canonical form."""
    left = canonicalize_url(url1)
    right = canonicalize_url(url2)
    return bool(left and right and left == right)


def extract_domain(url: str | None) -> str:
    """Extract a lowercased domain from a URL safely."""
    if url is None:
        return ""

    raw = str(url).strip()
    if not raw:
        return ""

    parts = urlsplit(raw)
    return _normalize_netloc(parts.netloc, parts.scheme.casefold() or "https")


def safe_url_hash(url: str | None) -> str:
    """Hash a canonical URL safely and deterministically."""
    canonical = canonicalize_url(url)
    if not canonical:
        return ""
    return hashlib.sha1(canonical.encode("utf-8")).hexdigest()[:16]


def _normalize_netloc(netloc: str, scheme: str) -> str:
    lowered = netloc.casefold().strip()
    if scheme == "http" and lowered.endswith(":80"):
        lowered = lowered[:-3]
    if scheme == "https" and lowered.endswith(":443"):
        lowered = lowered[:-4]
    return lowered.removeprefix("www.")


__all__ = ["canonicalize_url", "extract_domain", "safe_url_hash", "same_canonical_url"]
