"""Text cleaning helpers for raw collector content."""

from __future__ import annotations

import html
import re

from bs4 import BeautifulSoup

WHITESPACE_PATTERN = re.compile(r"\s+")


def clean_text(value: str | None) -> str:
    """Strip markup and normalize whitespace while preserving useful punctuation."""
    if value is None:
        return ""

    raw = html.unescape(str(value)).replace("\xa0", " ").strip()
    if not raw:
        return ""

    if "<" not in raw and ">" not in raw and "&" not in raw:
        return WHITESPACE_PATTERN.sub(" ", raw).strip()

    soup = BeautifulSoup(raw, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = soup.get_text(" ", strip=True) if soup.find() else raw
    cleaned = html.unescape(text).replace("\xa0", " ")
    return WHITESPACE_PATTERN.sub(" ", cleaned).strip()


def clean_text_lower(value: str | None) -> str:
    """Lowercased cleaned text for keyword matching."""
    return clean_text(value).casefold()


__all__ = ["clean_text", "clean_text_lower"]
