"""Best-effort location parsing for normalized jobs."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from internradar.parsers.text_cleaner import clean_text

REMOTE_TERMS = {
    "remote": "remote",
    "hybrid": "hybrid",
    "onsite": "onsite",
    "on-site": "onsite",
    "on site": "onsite",
}
REMOTE_PREFIX_PATTERN = re.compile(
    r"^\s*(remote|hybrid|onsite|on-site|on site)\s*[-:]\s*",
    re.IGNORECASE,
)
SPLIT_PATTERN = re.compile(r"\s*(?:/|;|\|)\s*")


@dataclass(slots=True)
class LocationParseResult:
    locations: list[str] = field(default_factory=list)
    remote_type: str | None = None


def parse_location(location_raw: str | None, description: str | None = None) -> LocationParseResult:
    """Parse a conservative set of normalized locations and remote mode."""
    cleaned_location = clean_text(location_raw)
    cleaned_description = clean_text(description)

    combined = " ".join(part for part in (cleaned_location, cleaned_description) if part).casefold()
    remote_type = _detect_remote_type(combined)

    if cleaned_location:
        locations = _normalize_locations(cleaned_location)
        if not locations and remote_type == "remote":
            locations = ["Remote"]
        return LocationParseResult(locations=locations, remote_type=remote_type)

    if remote_type == "remote":
        return LocationParseResult(locations=["Remote"], remote_type=remote_type)

    return LocationParseResult(locations=[], remote_type=remote_type)


def _detect_remote_type(text: str) -> str | None:
    if not text:
        return None

    for needle, normalized in REMOTE_TERMS.items():
        if needle in text:
            return normalized
    return None


def _normalize_locations(location_text: str) -> list[str]:
    trimmed = REMOTE_PREFIX_PATTERN.sub("", location_text).strip()
    if not trimmed:
        trimmed = location_text.strip()

    parts = SPLIT_PATTERN.split(trimmed)
    normalized: list[str] = []
    seen: set[str] = set()
    for part in parts:
        value = part.strip(" ,")
        if not value:
            continue
        key = value.casefold()
        if key in REMOTE_TERMS:
            label = "Remote" if REMOTE_TERMS[key] == "remote" else value.title()
            if label.casefold() not in seen:
                normalized.append(label)
                seen.add(label.casefold())
            continue
        if key not in seen:
            normalized.append(value)
            seen.add(key)

    return normalized


__all__ = ["LocationParseResult", "parse_location"]
