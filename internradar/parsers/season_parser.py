"""Season and year parsing for job titles and descriptions."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from internradar.parsers.text_cleaner import clean_text

SEASON_WORDS = {
    "summer": "summer",
    "winter": "winter",
    "fall": "fall",
    "spring": "spring",
}
MONTH_TO_SEASON = {
    "january": "winter",
    "february": "winter",
    "march": "spring",
    "april": "spring",
    "may": "summer",
    "june": "summer",
    "july": "summer",
    "august": "summer",
    "september": "fall",
    "october": "fall",
    "november": "fall",
    "december": "winter",
}
YEAR_PATTERN = re.compile(r"\b(20\d{2})\b")
SEASON_PATTERN = re.compile(r"\b(summer|winter|fall|spring)\b", re.IGNORECASE)
MONTH_PATTERN = re.compile(
    r"\b("
    r"january|february|march|april|may|june|july|august|"
    r"september|october|november|december"
    r")\b",
    re.IGNORECASE,
)


@dataclass(slots=True)
class SeasonParseResult:
    season: str | None = None
    year: int | None = None
    confidence: float = 0.0
    evidence: list[str] = field(default_factory=list)


def parse_season_and_year(title: str | None, description: str | None = None) -> SeasonParseResult:
    """Parse season and year, preferring title evidence over description evidence."""
    clean_title = clean_text(title)
    clean_description = clean_text(description)

    title_result = _parse_single_text(clean_title, from_title=True)
    if title_result.season is not None or title_result.year is not None:
        return title_result

    return _parse_single_text(clean_description, from_title=False)


def _parse_single_text(text: str, *, from_title: bool) -> SeasonParseResult:
    if not text:
        return SeasonParseResult()

    lowered = text.casefold()
    year_match = YEAR_PATTERN.search(lowered)
    season_match = SEASON_PATTERN.search(lowered)
    month_match = MONTH_PATTERN.search(lowered)

    if season_match and year_match:
        season = SEASON_WORDS[season_match.group(1).casefold()]
        year = int(year_match.group(1))
        return SeasonParseResult(
            season=season,
            year=year,
            confidence=0.95 if from_title else 0.85,
            evidence=[text],
        )

    if month_match and year_match:
        month = month_match.group(1).casefold()
        season = MONTH_TO_SEASON[month]
        return SeasonParseResult(
            season=season,
            year=int(year_match.group(1)),
            confidence=0.8 if from_title else 0.7,
            evidence=[text],
        )

    if year_match:
        return SeasonParseResult(
            season=None,
            year=int(year_match.group(1)),
            confidence=0.55 if from_title else 0.45,
            evidence=[text],
        )

    return SeasonParseResult()


__all__ = ["SeasonParseResult", "parse_season_and_year"]
