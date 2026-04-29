"""Normalization and parsing helpers for Intern Radar."""

from internradar.parsers.job_parser import (
    canonicalize_url,
    compute_content_hash,
    generate_stable_job_id,
    normalize_raw_job,
)
from internradar.parsers.eligibility_parser import (
    CandidateEligibilityMatch,
    apply_job_eligibility,
    evaluate_candidate_eligibility,
    parse_eligibility,
)
from internradar.parsers.location_parser import LocationParseResult, parse_location
from internradar.parsers.role_classifier import (
    classify_job_role,
    classify_role,
    resolve_role_keywords,
)
from internradar.parsers.season_parser import SeasonParseResult, parse_season_and_year
from internradar.parsers.text_cleaner import clean_text, clean_text_lower

__all__ = [
    "CandidateEligibilityMatch",
    "LocationParseResult",
    "SeasonParseResult",
    "apply_job_eligibility",
    "canonicalize_url",
    "clean_text",
    "clean_text_lower",
    "classify_job_role",
    "classify_role",
    "compute_content_hash",
    "evaluate_candidate_eligibility",
    "generate_stable_job_id",
    "normalize_raw_job",
    "parse_location",
    "parse_eligibility",
    "parse_season_and_year",
    "resolve_role_keywords",
]
