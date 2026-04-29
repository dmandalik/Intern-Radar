"""Evidence-based eligibility parsing and candidate matching."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from internradar.core.models import EligibilityInfo, Job
from internradar.parsers.text_cleaner import clean_text

SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?;])\s+|\n+")
GRADUATION_CUE_PATTERN = re.compile(
    r"\b(graduat(?:e|ing|ion)|class of|expected graduation|students graduating|degree date)\b",
    re.IGNORECASE,
)
YEAR_PATTERN = re.compile(r"\b(20\d{2})\b")
YEAR_LIST_PATTERN = re.compile(r"\b(20\d{2})\s*(?:or|and|/)\s*(20\d{2})\b", re.IGNORECASE)
CLASS_OF_PATTERN = re.compile(r"\bclass of\s+(20\d{2})\b", re.IGNORECASE)
GRADUATING_IN_PATTERN = re.compile(
    r"\b(?:graduating|graduate|expected graduation(?: date)?(?: of)?)\b[^.]{0,80}?\b(20\d{2})\b",
    re.IGNORECASE,
)
GRAD_RANGE_PATTERN = re.compile(
    r"\b(?:graduating|graduate|expected graduation(?: date)?(?: of)?)\b[^.]{0,80}?"
    r"between\s+([A-Za-z]+)\s+(20\d{2})\s+and\s+([A-Za-z]+)\s+(20\d{2})\b",
    re.IGNORECASE,
)
GPA_PATTERNS = (
    re.compile(r"\bminimum(?: cumulative)? gpa(?: of)?\s*([0-4]\.\d{1,2})\b", re.IGNORECASE),
    re.compile(r"\bgpa\s*([0-4]\.\d{1,2})\s*(?:or higher|minimum|required)?\b", re.IGNORECASE),
    re.compile(r"\b([0-4]\.\d{1,2})\s*minimum gpa\b", re.IGNORECASE),
)
BACHELOR_PATTERNS = (
    re.compile(r"\bbachelor'?s degree\b", re.IGNORECASE),
    re.compile(r"\bbachelors degree\b", re.IGNORECASE),
    re.compile(r"\bundergraduate\b", re.IGNORECASE),
    re.compile(r"\bcurrently pursuing a b\.?s\.?\b", re.IGNORECASE),
    re.compile(r"\bcurrently pursuing a b\.?a\.?\b", re.IGNORECASE),
    re.compile(r"\bpursuing a bachelor'?s\b", re.IGNORECASE),
    re.compile(r"\bpursuing a bachelors\b", re.IGNORECASE),
    re.compile(r"\b(?:bs|b\.s\.|ba|b\.a\.)\b[^.]{0,20}\bdegree\b", re.IGNORECASE),
)
MASTER_PATTERNS = (
    re.compile(r"\bmaster'?s degree\b", re.IGNORECASE),
    re.compile(r"\bmasters degree\b", re.IGNORECASE),
    re.compile(r"\bgraduate degree\b", re.IGNORECASE),
    re.compile(r"\bm\.?s\.?\b", re.IGNORECASE),
)
PHD_PATTERNS = (
    re.compile(r"\bph\.?d\.?\b", re.IGNORECASE),
    re.compile(r"\bdoctorate\b", re.IGNORECASE),
    re.compile(r"\bdoctoral\b", re.IGNORECASE),
)
REQUIRES_MASTER_PATTERNS = (
    re.compile(r"\bmaster'?s degree required\b", re.IGNORECASE),
    re.compile(r"\bmust be pursuing a master'?s\b", re.IGNORECASE),
    re.compile(r"\bgraduate student\b", re.IGNORECASE),
    re.compile(r"\bgraduate degree required\b", re.IGNORECASE),
)
REQUIRES_PHD_PATTERNS = (
    re.compile(r"\bph\.?d\.? required\b", re.IGNORECASE),
    re.compile(r"\bdoctor(?:al|ate) required\b", re.IGNORECASE),
    re.compile(r"\bmust be pursuing a ph\.?d\.?\b", re.IGNORECASE),
    re.compile(r"\bph\.?d\.? candidates only\b", re.IGNORECASE),
)
CLASS_YEAR_PATTERNS = {
    "freshman": re.compile(r"\bfreshm(?:a|e)n\b|\bfirst[- ]years?\b", re.IGNORECASE),
    "sophomore": re.compile(r"\bsophomores?\b|\bsecond[- ]years?\b", re.IGNORECASE),
    "junior": re.compile(r"\bjunior\b", re.IGNORECASE),
    "senior": re.compile(r"\bsenior\b", re.IGNORECASE),
    "rising junior": re.compile(r"\brising junior\b", re.IGNORECASE),
    "rising senior": re.compile(r"\brising senior\b", re.IGNORECASE),
    "penultimate year": re.compile(r"\bpenultimate year\b", re.IGNORECASE),
    "final year": re.compile(r"\bfinal year\b", re.IGNORECASE),
    "undergraduate": re.compile(r"\bundergraduate student\b|\bundergraduate\b", re.IGNORECASE),
}
FRESHMAN_SOPHOMORE_PATTERNS = (
    re.compile(r"\b(open to|eligible|welcome|accept(?:ed)?|considered?)\b[^.]{0,40}?\b(first[- ]years?|freshm(?:a|e)n|sophomores?)\b", re.IGNORECASE),
    re.compile(r"\b(first[- ]years?|freshm(?:a|e)n|sophomores?)\b[^.]{0,40}?\b(open to|eligible|welcome|accept(?:ed)?|considered?)\b", re.IGNORECASE),
)
UPPERCLASS_ONLY_PATTERNS = (
    re.compile(r"\b(?:junior|senior|penultimate year|final year)\b[^.]{0,30}\bonly\b", re.IGNORECASE),
    re.compile(r"\bonly\b[^.]{0,30}\b(?:junior|senior|penultimate year|final year)\b", re.IGNORECASE),
)
MAJOR_PATTERNS = {
    "computer science": (re.compile(r"\bcomputer science\b", re.IGNORECASE),),
    "computer engineering": (re.compile(r"\bcomputer engineering\b", re.IGNORECASE),),
    "electrical engineering": (re.compile(r"\belectrical engineering\b", re.IGNORECASE),),
    "mathematics": (re.compile(r"\bmathematics\b|\bmath\b", re.IGNORECASE),),
    "statistics": (re.compile(r"\bstatistics\b|\bstatistical\b", re.IGNORECASE),),
    "physics": (re.compile(r"\bphysics\b", re.IGNORECASE),),
    "engineering": (re.compile(r"\bengineering\b", re.IGNORECASE),),
    "operations research": (re.compile(r"\boperations research\b", re.IGNORECASE),),
    "data science": (re.compile(r"\bdata science\b", re.IGNORECASE),),
    "machine learning": (re.compile(r"\bmachine learning\b", re.IGNORECASE),),
    "applied math": (re.compile(r"\bapplied math(?:ematics)?\b", re.IGNORECASE),),
    "quantitative field": (re.compile(r"\bquantitative field\b", re.IGNORECASE),),
    "stem": (re.compile(r"\bstem\b", re.IGNORECASE),),
}
NO_SPONSORSHIP_PATTERNS = (
    re.compile(r"\bdo not sponsor visas\b", re.IGNORECASE),
    re.compile(r"\bsponsorship is not available\b", re.IGNORECASE),
    re.compile(r"\bmust be authorized to work without sponsorship\b", re.IGNORECASE),
    re.compile(r"\bwill not sponsor\b", re.IGNORECASE),
    re.compile(r"\bwithout the need for sponsorship\b", re.IGNORECASE),
    re.compile(r"\bwithout sponsorship now or in the future\b", re.IGNORECASE),
    re.compile(r"\blegally authorized to work without sponsorship\b", re.IGNORECASE),
)
MAYBE_SPONSORSHIP_PATTERNS = (
    re.compile(r"\bvisa sponsorship may be available\b", re.IGNORECASE),
    re.compile(r"\bsponsorship may be considered\b", re.IGNORECASE),
)
AVAILABLE_SPONSORSHIP_PATTERNS = (
    re.compile(r"\bwe sponsor visas\b", re.IGNORECASE),
    re.compile(r"\bsponsorship available\b", re.IGNORECASE),
)
CITIZENSHIP_PATTERNS = {
    "security_clearance_required": (
        re.compile(r"\bsecurity clearance required\b", re.IGNORECASE),
    ),
    "itar_restricted": (
        re.compile(r"\bitar restrictions?\b", re.IGNORECASE),
        re.compile(r"\bexport control restrictions?\b", re.IGNORECASE),
    ),
    "us_citizen_required": (
        re.compile(r"\bu\.?\s*s\.?\s+citizenship required\b", re.IGNORECASE),
        re.compile(r"\bmust be a u\.?\s*s\.?\s+citizen\b", re.IGNORECASE),
        re.compile(r"\bus citizen required\b", re.IGNORECASE),
    ),
}
SIGNAL_WEIGHTS = {
    "degree": 0.20,
    "graduation": 0.20,
    "sponsorship": 0.15,
    "citizenship": 0.15,
    "major": 0.15,
    "class_year": 0.10,
    "gpa": 0.05,
}
TECHNICAL_MAJOR_GROUP = {
    "computer science",
    "computer engineering",
    "electrical engineering",
    "mathematics",
    "statistics",
    "physics",
    "engineering",
    "operations research",
    "data science",
    "machine learning",
    "applied math",
}


@dataclass(slots=True)
class CandidateEligibilityMatch:
    score: float
    explanation: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)


def parse_eligibility(title: str | None, description: str | None) -> EligibilityInfo:
    """Parse conservative eligibility requirements from job text."""
    snippets = _extract_snippets(title, description)
    normalized = [snippet.casefold() for snippet in snippets]

    evidence: list[str] = []
    degree_levels, requires_masters, requires_phd, undergrad_friendly = _parse_degrees(snippets, normalized, evidence)
    graduation_years = _parse_graduation_years(snippets, normalized, evidence)
    class_years, freshman_sophomore_friendly = _parse_class_years(snippets, normalized, evidence)
    majors = _parse_majors(snippets, normalized, evidence)
    sponsorship = _parse_sponsorship(snippets, normalized, evidence)
    citizenship_requirement = _parse_citizenship(snippets, normalized, evidence)
    minimum_gpa = _parse_gpa(snippets, normalized, evidence)

    confidence = _compute_confidence(
        degree_levels=degree_levels,
        graduation_years=graduation_years,
        sponsorship=sponsorship,
        citizenship_requirement=citizenship_requirement,
        majors=majors,
        class_years=class_years,
        minimum_gpa=minimum_gpa,
    )

    return EligibilityInfo(
        degree_levels=degree_levels,
        graduation_years=graduation_years,
        majors=majors,
        citizenship_requirement=citizenship_requirement,
        sponsorship=sponsorship,
        minimum_gpa=minimum_gpa,
        class_years=class_years,
        requires_phd=requires_phd,
        requires_masters=requires_masters,
        undergrad_friendly=undergrad_friendly,
        freshman_sophomore_friendly=freshman_sophomore_friendly,
        confidence=confidence,
        raw_evidence=_dedupe_preserve_order(evidence),
    )


def apply_job_eligibility(job: Job) -> Job:
    """Return a copy of a normalized job with parsed eligibility."""
    eligibility = parse_eligibility(job.title, job.description)
    return job.model_copy(update={"eligibility": eligibility})


def evaluate_candidate_eligibility(
    eligibility_info: EligibilityInfo,
    candidate_config: dict[str, Any] | None,
) -> CandidateEligibilityMatch:
    """Evaluate a candidate against parsed eligibility with explanations."""
    if not candidate_config:
        return CandidateEligibilityMatch(
            score=0.5,
            explanation=["No candidate configuration was provided."],
        )

    score = 0.5
    explanation: list[str] = []
    blockers: list[str] = []
    hard_cap: float | None = None

    candidate_degree = _normalize_degree_level(candidate_config.get("degree_level"))
    candidate_year = _normalize_optional_int(candidate_config.get("graduation_year"))
    candidate_major = _normalize_optional_string(candidate_config.get("major"))
    needs_sponsorship = bool(candidate_config.get("needs_sponsorship"))
    citizenship = _normalize_optional_string(candidate_config.get("citizenship"))

    if eligibility_info.requires_phd and candidate_degree != "phd":
        blockers.append("Role requires a PhD.")
        explanation.append("Eligibility requires a PhD, which conflicts with the candidate profile.")
        score = min(score, 0.05)
        hard_cap = 0.05
    elif eligibility_info.requires_masters and candidate_degree not in {"masters", "phd"}:
        blockers.append("Role requires a master's-level candidate.")
        explanation.append("Eligibility requires a master's degree or higher.")
        score = min(score, 0.10)
        hard_cap = 0.10
    elif candidate_degree and _degree_is_accepted(candidate_degree, eligibility_info):
        score += 0.15
        explanation.append(f"Candidate degree level '{candidate_degree}' matches the posting requirements.")

    if eligibility_info.graduation_years:
        if candidate_year in eligibility_info.graduation_years:
            score += 0.15
            explanation.append(f"Graduation year {candidate_year} is explicitly accepted.")
        else:
            score -= 0.20
            explanation.append(
                f"Graduation year {candidate_year} does not match the accepted years {eligibility_info.graduation_years}.",
            )

    if eligibility_info.majors and candidate_major is not None:
        if _major_matches(candidate_major, eligibility_info.majors):
            score += 0.10
            explanation.append(f"Candidate major '{candidate_major}' matches the posting.")
        else:
            score -= 0.10
            explanation.append(f"Candidate major '{candidate_major}' is outside the listed fields {eligibility_info.majors}.")

    if eligibility_info.sponsorship == "not_available" and needs_sponsorship:
        blockers.append("Visa sponsorship is not available.")
        explanation.append("Posting says sponsorship is not available.")
        score = min(score, 0.02)
        hard_cap = 0.02
    elif eligibility_info.sponsorship in {"available", "maybe"} and needs_sponsorship:
        score += 0.05
        explanation.append(f"Posting indicates sponsorship is {eligibility_info.sponsorship}.")

    if eligibility_info.citizenship_requirement == "us_citizen_required" and citizenship not in {"us", "us_citizen", "u.s. citizen"}:
        blockers.append("U.S. citizenship required.")
        explanation.append("Posting requires U.S. citizenship.")
        score = min(score, 0.02)
        hard_cap = 0.02
    elif eligibility_info.citizenship_requirement == "security_clearance_required" and citizenship not in {"us", "us_citizen", "u.s. citizen"}:
        blockers.append("Security clearance requirement may block eligibility.")
        explanation.append("Posting requires a security clearance.")
        score = min(score, 0.10)
        hard_cap = 0.10
    elif eligibility_info.citizenship_requirement == "itar_restricted" and citizenship not in {"us", "us_citizen", "u.s. citizen"}:
        blockers.append("ITAR restrictions may block eligibility.")
        explanation.append("Posting includes ITAR or export control restrictions.")
        score = min(score, 0.10)
        hard_cap = 0.10

    if eligibility_info.confidence == 0.0 and not explanation:
        explanation.append("Posting eligibility is mostly unknown; candidate fit remains uncertain.")

    if hard_cap is not None:
        score = min(score, hard_cap)
    score = max(0.0, min(1.0, round(score, 3)))
    return CandidateEligibilityMatch(score=score, explanation=explanation, blockers=blockers)


def _parse_degrees(
    snippets: list[str],
    normalized: list[str],
    evidence: list[str],
) -> tuple[list[str], bool, bool, bool | None]:
    degree_levels: list[str] = []
    bachelor_found = _find_pattern_evidence(snippets, BACHELOR_PATTERNS, evidence)
    master_found = _find_pattern_evidence(snippets, MASTER_PATTERNS, evidence)
    phd_found = _find_pattern_evidence(snippets, PHD_PATTERNS, evidence)

    if bachelor_found:
        degree_levels.append("bachelors")
    if master_found:
        degree_levels.append("masters")
    if phd_found:
        degree_levels.append("phd")

    requires_masters = any(pattern.search(text) for text in normalized for pattern in REQUIRES_MASTER_PATTERNS)
    requires_phd = any(pattern.search(text) for text in normalized for pattern in REQUIRES_PHD_PATTERNS)
    if requires_masters:
        _add_evidence_for_patterns(snippets, REQUIRES_MASTER_PATTERNS, evidence)
    if requires_phd:
        _add_evidence_for_patterns(snippets, REQUIRES_PHD_PATTERNS, evidence)

    undergrad_friendly: bool | None
    if (bachelor_found or "bachelors" in degree_levels) and not requires_phd:
        undergrad_friendly = True
    elif requires_phd or (requires_masters and not bachelor_found):
        undergrad_friendly = False
    else:
        undergrad_friendly = None

    return _dedupe_preserve_order(degree_levels), requires_masters, requires_phd, undergrad_friendly


def _parse_graduation_years(
    snippets: list[str],
    normalized: list[str],
    evidence: list[str],
) -> list[int]:
    years: list[int] = []
    for snippet, lowered in zip(snippets, normalized, strict=True):
        if not GRADUATION_CUE_PATTERN.search(lowered):
            continue

        range_match = GRAD_RANGE_PATTERN.search(snippet)
        if range_match:
            start_year = int(range_match.group(2))
            end_year = int(range_match.group(4))
            if 0 <= end_year - start_year <= 4:
                years.extend(range(start_year, end_year + 1))
                evidence.append(snippet)
                continue

        class_match = CLASS_OF_PATTERN.search(snippet)
        if class_match:
            years.append(int(class_match.group(1)))
            evidence.append(snippet)
            continue

        graduating_match = GRADUATING_IN_PATTERN.search(snippet)
        if graduating_match:
            years.append(int(graduating_match.group(1)))
            evidence.append(snippet)

        year_list_match = YEAR_LIST_PATTERN.search(snippet)
        if year_list_match:
            years.extend([int(year_list_match.group(1)), int(year_list_match.group(2))])
            evidence.append(snippet)
            continue

        for match in YEAR_PATTERN.finditer(snippet):
            year = int(match.group(1))
            if 2020 <= year <= 2035:
                years.append(year)
                evidence.append(snippet)
    return sorted(set(years))


def _parse_class_years(
    snippets: list[str],
    normalized: list[str],
    evidence: list[str],
) -> tuple[list[str], bool | None]:
    class_years: list[str] = []
    freshman_or_sophomore = False
    upperclass_only = False

    for label, pattern in CLASS_YEAR_PATTERNS.items():
        found = False
        for snippet, lowered in zip(snippets, normalized, strict=True):
            if pattern.search(lowered):
                class_years.append(label)
                evidence.append(snippet)
                found = True
                if label in {"freshman", "sophomore"}:
                    freshman_or_sophomore = True
                if label in {"junior", "senior", "penultimate year", "final year", "rising junior", "rising senior"}:
                    upperclass_only = True
        if found:
            continue

    freshman_sophomore_friendly: bool | None = None
    if any(pattern.search(text) for text in normalized for pattern in FRESHMAN_SOPHOMORE_PATTERNS) or freshman_or_sophomore:
        freshman_sophomore_friendly = True
    elif any(pattern.search(text) for text in normalized for pattern in UPPERCLASS_ONLY_PATTERNS) or (upperclass_only and not freshman_or_sophomore):
        freshman_sophomore_friendly = False

    return _dedupe_preserve_order(class_years), freshman_sophomore_friendly


def _parse_majors(
    snippets: list[str],
    normalized: list[str],
    evidence: list[str],
) -> list[str]:
    del normalized
    majors: list[str] = []
    for major, patterns in MAJOR_PATTERNS.items():
        for snippet in snippets:
            if any(pattern.search(snippet) for pattern in patterns):
                majors.append(major)
                evidence.append(snippet)
                break
    return _dedupe_preserve_order(majors)


def _parse_sponsorship(
    snippets: list[str],
    normalized: list[str],
    evidence: list[str],
) -> str:
    if _find_pattern_evidence(snippets, NO_SPONSORSHIP_PATTERNS, evidence):
        return "not_available"
    if _find_pattern_evidence(snippets, AVAILABLE_SPONSORSHIP_PATTERNS, evidence):
        return "available"
    if _find_pattern_evidence(snippets, MAYBE_SPONSORSHIP_PATTERNS, evidence):
        return "maybe"
    return "unknown"


def _parse_citizenship(
    snippets: list[str],
    normalized: list[str],
    evidence: list[str],
) -> str | None:
    del normalized
    combined = " ".join(snippets)
    for label, patterns in CITIZENSHIP_PATTERNS.items():
        if _find_pattern_evidence(snippets, patterns, evidence):
            return label
        if any(pattern.search(combined) for pattern in patterns):
            evidence.append(combined)
            return label
    return None


def _parse_gpa(
    snippets: list[str],
    normalized: list[str],
    evidence: list[str],
) -> float | None:
    del normalized
    for snippet in snippets:
        for pattern in GPA_PATTERNS:
            match = pattern.search(snippet)
            if match:
                evidence.append(snippet)
                return float(match.group(1))
    return None


def _compute_confidence(
    *,
    degree_levels: list[str],
    graduation_years: list[int],
    sponsorship: str,
    citizenship_requirement: str | None,
    majors: list[str],
    class_years: list[str],
    minimum_gpa: float | None,
) -> float:
    confidence = 0.0
    if degree_levels:
        confidence += SIGNAL_WEIGHTS["degree"]
    if graduation_years:
        confidence += SIGNAL_WEIGHTS["graduation"]
    if sponsorship != "unknown":
        confidence += SIGNAL_WEIGHTS["sponsorship"]
    if citizenship_requirement is not None:
        confidence += SIGNAL_WEIGHTS["citizenship"]
    if majors:
        confidence += SIGNAL_WEIGHTS["major"]
    if class_years:
        confidence += SIGNAL_WEIGHTS["class_year"]
    if minimum_gpa is not None:
        confidence += SIGNAL_WEIGHTS["gpa"]
    return round(min(confidence, 1.0), 2)


def _extract_snippets(title: str | None, description: str | None) -> list[str]:
    snippets: list[str] = []
    for part in (title, description):
        cleaned = clean_text(part)
        if not cleaned:
            continue
        split = [chunk.strip() for chunk in SENTENCE_SPLIT_PATTERN.split(cleaned) if chunk.strip()]
        snippets.extend(split or [cleaned])
    return snippets


def _find_pattern_evidence(snippets: list[str], patterns: tuple[re.Pattern[str], ...], evidence: list[str]) -> bool:
    found = False
    for snippet in snippets:
        if any(pattern.search(snippet) for pattern in patterns):
            evidence.append(snippet)
            found = True
    return found


def _add_evidence_for_patterns(snippets: list[str], patterns: tuple[re.Pattern[str], ...], evidence: list[str]) -> None:
    _find_pattern_evidence(snippets, patterns, evidence)


def _degree_is_accepted(candidate_degree: str, info: EligibilityInfo) -> bool:
    if not info.degree_levels:
        return True
    if candidate_degree in info.degree_levels:
        return True
    if candidate_degree == "bachelors" and info.undergrad_friendly:
        return True
    if candidate_degree == "masters" and "phd" in info.degree_levels:
        return False
    if candidate_degree == "phd" and ("masters" in info.degree_levels or "bachelors" in info.degree_levels):
        return True
    return False


def _major_matches(candidate_major: str, accepted_majors: list[str]) -> bool:
    candidate = candidate_major.casefold()
    accepted = {major.casefold() for major in accepted_majors}
    if candidate in accepted:
        return True
    if "stem" in accepted and candidate in TECHNICAL_MAJOR_GROUP:
        return True
    if "engineering" in accepted and "engineering" in candidate:
        return True
    if "quantitative field" in accepted and candidate in TECHNICAL_MAJOR_GROUP:
        return True
    return False


def _normalize_degree_level(value: Any) -> str | None:
    text = _normalize_optional_string(value)
    if text is None:
        return None
    if "phd" in text or "ph.d" in text or "doctor" in text:
        return "phd"
    if "master" in text or text in {"ms", "m.s."}:
        return "masters"
    if "bachelor" in text or "undergrad" in text or text in {"bs", "b.s.", "ba", "b.a."}:
        return "bachelors"
    return text


def _normalize_optional_string(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip().casefold()
    return None


def _normalize_optional_int(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _dedupe_preserve_order(values: list[Any]) -> list[Any]:
    seen: set[Any] = set()
    ordered: list[Any] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


__all__ = [
    "CandidateEligibilityMatch",
    "apply_job_eligibility",
    "evaluate_candidate_eligibility",
    "parse_eligibility",
]
