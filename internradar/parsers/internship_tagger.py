"""Robust internship detection.

Identifies internship-class roles across spelling variants and several
languages so that the scanner can capture *every* role yet reliably flag which
ones are internships. Full-time "graduate program" / "new grad" roles are
intentionally NOT treated as internships; only intern / co-op / placement /
summer-analyst style early-career programs are.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from internradar.parsers.text_cleaner import clean_text

INTERNSHIP_TAG = "internship"

# Unambiguous, non-English internship nouns shared by title and description
# matching. ``stage`` (French) is intentionally excluded here because it
# collides with the common English word "stage"; only ``stagiaire`` is used.
_MULTILINGUAL_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # German
    ("internship", re.compile(r"\b(?:praktikum|praktikant(?:in|en)?)\b", re.IGNORECASE)),
    ("internship", re.compile(r"\bwerkstudent(?:in)?\b", re.IGNORECASE)),
    # French (stagiaire only; bare "stage" is too ambiguous in English text)
    ("internship", re.compile(r"\bstagiaire\b", re.IGNORECASE)),
    # Spanish
    ("internship", re.compile(r"\b(?:becari[oa]|pr[áa]cticas)\b", re.IGNORECASE)),
    # Italian
    ("internship", re.compile(r"\btirocinio\b", re.IGNORECASE)),
    # Portuguese
    ("internship", re.compile(r"\best[áa]gi(?:o|ári[oa])\b", re.IGNORECASE)),
    # CJK / Korean (no word boundaries for non-latin scripts)
    ("internship", re.compile(r"实习生?|インターン(?:シップ)?|인턴(?:십)?")),
]

_PLACEMENT_PATTERN = re.compile(
    r"\b(?:industrial placement|placement (?:year|student|programme|program)"
    r"|vacation (?:scheme|programme|program)|spring (?:week|insight)"
    r"|insight (?:programme|program|week))\b",
    re.IGNORECASE,
)

# Title patterns are broad/high-recall: a genuine internship is almost always
# titled as such. Word boundaries avoid "internal"/"international"/"staging".
_TITLE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("internship", re.compile(r"\bintern(?:ship|ships|s)?\b", re.IGNORECASE)),
    ("co_op", re.compile(r"\bco[\s\-]?op(?:s)?\b", re.IGNORECASE)),
    ("summer_analyst", re.compile(r"\bsummer analyst\b", re.IGNORECASE)),
    ("placement", _PLACEMENT_PATTERN),
    *_MULTILINGUAL_PATTERNS,
]

# Description patterns are strict/high-precision: they require a role-defining
# phrase so that full-time postings merely *mentioning* an internship program
# in passing ("we also offer internships") are NOT flagged.
_DESCRIPTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "internship",
        re.compile(
            r"\b(?:summer|winter|spring|fall|autumn|graduate)?\s*intern(?:ship)?\s+"
            r"(?:program|programme|position|role|opportunit(?:y|ies)|opening|cohort)\b",
            re.IGNORECASE,
        ),
    ),
    ("internship", re.compile(r"\b(?:this|our)\s+internship\b", re.IGNORECASE)),
    ("internship", re.compile(r"\b\d+[\s\-]?(?:week|month)s?\s+intern(?:ship)?\b", re.IGNORECASE)),
    ("co_op", re.compile(r"\bco[\s\-]?op\s+(?:program|programme|position|role|term)\b", re.IGNORECASE)),
    ("summer_analyst", re.compile(r"\bsummer analyst\b", re.IGNORECASE)),
    ("placement", _PLACEMENT_PATTERN),
    *_MULTILINGUAL_PATTERNS,
]


@dataclass(slots=True)
class InternshipTag:
    is_internship: bool = False
    program_type: str | None = None
    confidence: float = 0.0
    evidence: list[str] = field(default_factory=list)


def detect_internship(title: str | None, description: str | None = None) -> InternshipTag:
    """Detect whether a posting is an internship-class role.

    Title evidence is weighted higher than description evidence because many
    full-time postings merely mention an internship program in passing.
    """
    clean_title = clean_text(title) or ""
    clean_description = clean_text(description) or ""

    title_type, title_evidence = _match_program(clean_title, _TITLE_PATTERNS)
    if title_type is not None:
        return InternshipTag(
            is_internship=True,
            program_type=title_type,
            confidence=0.95,
            evidence=title_evidence,
        )

    description_type, description_evidence = _match_program(clean_description, _DESCRIPTION_PATTERNS)
    if description_type is not None:
        return InternshipTag(
            is_internship=True,
            program_type=description_type,
            confidence=0.6,
            evidence=description_evidence,
        )

    return InternshipTag()


def _match_program(text: str, patterns: list[tuple[str, re.Pattern[str]]]) -> tuple[str | None, list[str]]:
    if not text:
        return None, []
    for program_type, pattern in patterns:
        match = pattern.search(text)
        if match:
            return program_type, [f'matched "{match.group(0).strip()}"']
    return None, []


def apply_internship_tag(
    title: str | None,
    description: str | None,
    existing_tags: list[str] | None = None,
) -> tuple[bool, list[str]]:
    """Return ``(is_internship, tags)`` with the internship tag merged in."""
    result = detect_internship(title, description)
    tags = list(existing_tags or [])
    if result.is_internship and INTERNSHIP_TAG not in tags:
        tags.append(INTERNSHIP_TAG)
    return result.is_internship, tags


__all__ = [
    "INTERNSHIP_TAG",
    "InternshipTag",
    "apply_internship_tag",
    "detect_internship",
]
