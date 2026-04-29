"""Rule-based role classification with weighted evidence."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from internradar.core.models import ClassifiedRole, Job
from internradar.core.pack_loader import PackLoaderError, load_pack_role_keywords
from internradar.parsers.text_cleaner import clean_text_lower

NEGATIVE_EXEMPT_FAMILIES = {"finance_analyst", "trading_operations", "other", "unknown"}
DEFAULT_ROLE_PREFERENCES = [
    "trading_systems_engineer",
    "software_engineer_trading",
    "low_latency_engineer",
    "algorithmic_trading_engineer",
    "market_data_engineer",
    "infrastructure_engineer",
    "fpga_engineer",
    "hardware_trading_engineer",
    "quant_developer",
    "ml_engineer_quant",
    "data_engineer_quant",
    "research_engineer_quant",
    "quant_trading",
    "quant_research",
    "trading_operations",
    "finance_analyst",
    "other",
    "unknown",
]
FALLBACK_ROLE_KEYWORDS: dict[str, Any] = {
    "negative_keywords": [
        "sales",
        "operations",
        "compliance",
        "accounting",
        "marketing",
        "business development",
        "investment banking",
        "wealth management",
        "client services",
        "campus ambassador",
    ],
    "role_preferences": DEFAULT_ROLE_PREFERENCES,
    "role_families": {
        "quant_developer": {
            "strong": [
                "quant developer",
                "quantitative developer",
                "quantitative software developer",
                "quant dev",
                "research engineer",
                "trading developer",
            ],
            "medium": [
                "backtesting",
                "trading models",
                "research platform",
                "python",
                "c++",
                "quantitative systems",
            ],
            "categories": ["quant_developer"],
        },
        "trading_systems_engineer": {
            "strong": [
                "trading systems",
                "trading platform",
                "trade execution",
                "execution systems",
                "order management",
                "market connectivity",
            ],
            "medium": [
                "exchange connectivity",
                "order book",
                "matching engine",
                "market data",
                "real-time systems",
            ],
            "categories": ["trading_systems_engineer"],
        },
        "algorithmic_trading_engineer": {
            "strong": [
                "algorithmic trading",
                "algo trading",
                "trading algorithms",
                "execution algorithms",
            ],
            "medium": [
                "signal generation",
                "backtesting",
                "simulation",
                "market microstructure",
                "strategy development",
            ],
            "categories": ["algorithmic_trading_engineer"],
        },
        "software_engineer_trading": {
            "strong": [
                "software engineer intern",
                "software engineering intern",
                "trading software",
                "engineering intern trading",
                "software engineer",
            ],
            "medium": [
                "python",
                "java",
                "c++",
                "distributed systems",
                "backend",
                "infrastructure",
                "trading",
            ],
            "categories": ["software_engineer_trading"],
        },
        "low_latency_engineer": {
            "strong": [
                "low latency",
                "ultra-low latency",
                "latency-sensitive",
                "high performance c++",
                "performance critical",
                "kernel bypass",
            ],
            "medium": [
                "network programming",
                "linux systems",
                "profiling",
                "optimization",
                "real-time systems",
                "multithreading",
                "concurrency",
            ],
            "categories": ["low_latency_engineer"],
        },
        "market_data_engineer": {
            "strong": [
                "market data",
                "market data engineer",
                "data feeds",
                "exchange data",
            ],
            "medium": [
                "streaming data",
                "tick data",
                "order book",
                "real-time data",
            ],
            "categories": ["market_data_engineer"],
        },
        "infrastructure_engineer": {
            "strong": [
                "infrastructure engineer",
                "platform engineer",
                "systems engineer",
                "distributed systems",
            ],
            "medium": [
                "kubernetes",
                "linux",
                "backend",
                "databases",
                "cloud",
                "observability",
            ],
            "categories": ["infrastructure_engineer"],
        },
        "fpga_engineer": {
            "strong": [
                "fpga",
                "verilog",
                "vhdl",
                "hardware acceleration",
                "hardware engineer intern",
            ],
            "medium": [
                "digital logic",
                "computer architecture",
                "low latency hardware",
                "rtl",
            ],
            "categories": ["fpga_engineer", "hardware_trading_engineer"],
        },
        "hardware_trading_engineer": {
            "strong": [
                "hardware trading",
                "trading hardware",
                "network card",
                "smartnic",
            ],
            "medium": [
                "fpga",
                "digital logic",
                "latency hardware",
            ],
            "categories": ["hardware_trading_engineer"],
        },
        "ml_engineer_quant": {
            "strong": [
                "machine learning engineer",
                "ml engineer",
                "ai engineer",
            ],
            "medium": [
                "models",
                "prediction",
                "deep learning",
                "pytorch",
                "tensorflow",
                "feature engineering",
                "trading",
            ],
            "categories": ["ml_engineer_quant"],
        },
        "data_engineer_quant": {
            "strong": [
                "data engineer",
                "data engineering",
                "data platform",
                "data infrastructure",
            ],
            "medium": [
                "streaming data",
                "pipelines",
                "etl",
                "warehouse",
                "trading data",
            ],
            "categories": ["data_engineer_quant"],
        },
        "research_engineer_quant": {
            "strong": [
                "research engineer",
                "research platform engineer",
                "simulation engineer",
            ],
            "medium": [
                "backtesting",
                "research platform",
                "models",
                "python",
            ],
            "categories": ["research_engineer_quant"],
        },
        "quant_trading": {
            "strong": [
                "quantitative trading intern",
                "quant trader",
                "trading intern",
                "trader intern",
            ],
            "medium": [
                "market making",
                "options trading",
                "risk taking",
                "decision making",
            ],
            "categories": ["quant_trading"],
        },
        "quant_research": {
            "strong": [
                "quantitative research intern",
                "quant researcher",
                "research scientist",
                "alpha research",
            ],
            "medium": [
                "statistics",
                "probability",
                "mathematics",
                "optimization",
                "signals",
            ],
            "categories": ["quant_research"],
        },
        "finance_analyst": {
            "strong": [
                "sales and trading",
                "summer analyst",
                "finance analyst",
                "trading analyst",
            ],
            "medium": [
                "analyst",
                "capital markets",
                "portfolio",
                "investment",
            ],
        },
        "trading_operations": {
            "strong": [
                "trading operations",
                "trade support",
                "middle office",
                "operations analyst",
            ],
            "medium": [
                "post-trade",
                "reconciliation",
                "settlement",
                "client onboarding",
            ],
        },
        "other": {
            "strong": [],
            "medium": [],
        },
        "unknown": {
            "strong": [],
            "medium": [],
        },
    },
}


@dataclass(slots=True)
class _RoleFamilyConfig:
    strong: list[str] = field(default_factory=list)
    medium: list[str] = field(default_factory=list)
    department_keywords: list[str] = field(default_factory=list)
    category_keywords: list[str] = field(default_factory=list)
    negative_keywords: list[str] = field(default_factory=list)
    role_subtype: str | None = None


@dataclass(slots=True)
class _RoleMatch:
    family: str
    score: int = 0
    evidence: list[str] = field(default_factory=list)
    strong_title_match: bool = False
    any_title_match: bool = False
    context_match: bool = False
    positive_hits: int = 0


def classify_role(
    title: str,
    description: str | None = None,
    *,
    department: str | None = None,
    company_categories: list[str] | None = None,
    role_keywords: Mapping[str, Any] | None = None,
    pack_name: str | None = None,
    root: Path | None = None,
) -> ClassifiedRole:
    """Classify a role family from text using pack-driven weighted keywords."""
    config = resolve_role_keywords(role_keywords=role_keywords, pack_name=pack_name, root=root)
    normalized_title = clean_text_lower(title)
    normalized_description = clean_text_lower(description)
    normalized_department = clean_text_lower(department)
    normalized_categories = [clean_text_lower(category) for category in company_categories or []]

    matches = [
        _score_role_family(
            family=family,
            config=family_config,
            title=normalized_title,
            description=normalized_description,
            department=normalized_department,
            categories=normalized_categories,
            global_negative_keywords=config["negative_keywords"],
        )
        for family, family_config in config["role_families"].items()
        if family not in {"other", "unknown"}
    ]
    matches.sort(
        key=lambda match: (
            match.score,
            1 if match.strong_title_match else 0,
            1 if match.any_title_match else 0,
            -_preference_index(match.family, config["role_preferences"]),
        ),
        reverse=True,
    )

    if not matches:
        return ClassifiedRole(role_family="unknown", confidence=0.0, evidence=[])

    top = matches[0]
    second_score = matches[1].score if len(matches) > 1 else 0
    if top.score < 3 or top.positive_hits == 0:
        fallback_family = "other" if top.evidence else "unknown"
        fallback_evidence = top.evidence[:2] if fallback_family == "other" else []
        return ClassifiedRole(
            role_family=fallback_family,
            confidence=0.15 if fallback_family == "other" else 0.0,
            evidence=fallback_evidence,
        )

    confidence = _compute_confidence(top, second_score)
    return ClassifiedRole(
        role_family=top.family,
        role_subtype=config["role_families"][top.family].role_subtype,
        confidence=confidence,
        evidence=top.evidence[:8],
    )


def classify_job_role(
    job: Job,
    *,
    company_categories: list[str] | None = None,
    role_keywords: Mapping[str, Any] | None = None,
    pack_name: str | None = None,
    root: Path | None = None,
) -> Job:
    """Return a copy of a normalized job with its role field classified."""
    classified = classify_role(
        title=job.title,
        description=job.description,
        company_categories=company_categories,
        role_keywords=role_keywords,
        pack_name=pack_name,
        root=root,
    )
    return job.model_copy(update={"role": classified})


def resolve_role_keywords(
    *,
    role_keywords: Mapping[str, Any] | None = None,
    pack_name: str | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    """Resolve role keywords from explicit config, pack config, or built-in fallbacks."""
    fallback = _normalize_role_keyword_payload(FALLBACK_ROLE_KEYWORDS, merge_with_fallback=False)
    loaded = role_keywords
    if loaded is None and pack_name is not None:
        try:
            loaded = load_pack_role_keywords(pack_name, root=root)
        except PackLoaderError:
            loaded = None

    if loaded is None:
        return fallback

    resolved = _normalize_role_keyword_payload(loaded, merge_with_fallback=False)
    return _merge_role_keyword_configs(fallback, resolved)


def _normalize_role_keyword_payload(
    payload: Mapping[str, Any],
    *,
    merge_with_fallback: bool,
) -> dict[str, Any]:
    role_keywords = payload.get("role_keywords") if "role_keywords" in payload else payload
    if not isinstance(role_keywords, Mapping):
        role_keywords = {}

    negative_keywords = _normalize_string_list(role_keywords.get("negative_keywords"))
    role_preferences = _normalize_string_list(role_keywords.get("role_preferences"))

    raw_role_families = role_keywords.get("role_families")
    if not isinstance(raw_role_families, Mapping):
        raw_role_families = {
            family: {"medium": keywords}
            for family, keywords in role_keywords.items()
            if family not in {"negative_keywords", "role_preferences"} and isinstance(keywords, list)
        }

    families: dict[str, _RoleFamilyConfig] = {}
    for family, settings in raw_role_families.items():
        if isinstance(settings, list):
            families[family] = _RoleFamilyConfig(medium=_normalize_string_list(settings))
            continue
        if not isinstance(settings, Mapping):
            continue
        families[family] = _RoleFamilyConfig(
            strong=_normalize_string_list(settings.get("strong")),
            medium=_normalize_string_list(settings.get("medium")),
            department_keywords=_normalize_string_list(settings.get("departments")),
            category_keywords=_normalize_string_list(settings.get("categories")),
            negative_keywords=_normalize_string_list(settings.get("negative_keywords")),
            role_subtype=_normalize_optional_string(settings.get("role_subtype")),
        )

    config = {
        "negative_keywords": negative_keywords,
        "role_preferences": role_preferences,
        "role_families": families,
    }
    if merge_with_fallback:
        return _merge_role_keyword_configs(
            _normalize_role_keyword_payload(FALLBACK_ROLE_KEYWORDS, merge_with_fallback=False),
            config,
        )
    return config


def _merge_role_keyword_configs(
    fallback: dict[str, Any],
    loaded: dict[str, Any],
) -> dict[str, Any]:
    merged_families: dict[str, _RoleFamilyConfig] = {}
    all_families = set(fallback["role_families"]) | set(loaded["role_families"])
    for family in all_families:
        base = fallback["role_families"].get(family, _RoleFamilyConfig())
        override = loaded["role_families"].get(family, _RoleFamilyConfig())
        merged_families[family] = _RoleFamilyConfig(
            strong=override.strong or base.strong,
            medium=override.medium or base.medium,
            department_keywords=override.department_keywords or base.department_keywords,
            category_keywords=override.category_keywords or base.category_keywords,
            negative_keywords=override.negative_keywords or base.negative_keywords,
            role_subtype=override.role_subtype or base.role_subtype,
        )

    role_preferences = loaded["role_preferences"] or fallback["role_preferences"]
    for family in DEFAULT_ROLE_PREFERENCES:
        if family not in role_preferences:
            role_preferences.append(family)
    for family in merged_families:
        if family not in role_preferences:
            role_preferences.append(family)

    negative_keywords = loaded["negative_keywords"] or fallback["negative_keywords"]
    return {
        "negative_keywords": negative_keywords,
        "role_preferences": role_preferences,
        "role_families": merged_families,
    }


def _score_role_family(
    *,
    family: str,
    config: _RoleFamilyConfig,
    title: str,
    description: str,
    department: str,
    categories: list[str],
    global_negative_keywords: list[str],
) -> _RoleMatch:
    match = _RoleMatch(family=family)
    matched_title_keywords: list[str] = []
    matched_description_keywords: list[str] = []

    for keyword in _sorted_keywords(config.strong):
        if keyword in title and not _is_subsumed(keyword, matched_title_keywords):
            matched_title_keywords.append(keyword)
            match.score += 5
            match.positive_hits += 1
            match.strong_title_match = True
            match.any_title_match = True
            match.evidence.append(f'title matched strong keyword "{keyword}"')
            if title == keyword:
                match.score += 2
                match.evidence.append(f'title exactly matched role keyword "{keyword}"')
        elif keyword in description and not _is_subsumed(keyword, matched_description_keywords):
            matched_description_keywords.append(keyword)
            match.score += 2
            match.positive_hits += 1
            match.evidence.append(f'description matched strong keyword "{keyword}"')

    for keyword in _sorted_keywords(config.medium):
        if keyword in title and not _is_subsumed(keyword, matched_title_keywords):
            matched_title_keywords.append(keyword)
            match.score += 3
            match.positive_hits += 1
            match.any_title_match = True
            match.evidence.append(f'title matched medium keyword "{keyword}"')
        elif keyword in description and not _is_subsumed(keyword, matched_description_keywords):
            matched_description_keywords.append(keyword)
            match.score += 1
            match.positive_hits += 1
            match.evidence.append(f'description matched medium keyword "{keyword}"')

    for keyword in config.department_keywords:
        if keyword in department:
            match.score += 2
            match.context_match = True
            match.positive_hits += 1
            match.evidence.append(f'department matched keyword "{keyword}"')

    for keyword in config.category_keywords:
        if any(keyword in category for category in categories):
            match.score += 1
            match.context_match = True
            match.positive_hits += 1
            match.evidence.append(f'company category matched keyword "{keyword}"')

    if family not in NEGATIVE_EXEMPT_FAMILIES:
        for keyword in global_negative_keywords:
            if keyword in title or keyword in description or keyword in department:
                match.score -= 3
                match.evidence.append(f'negative keyword "{keyword}" lowered score for {family}')
        for keyword in config.negative_keywords:
            if keyword in title or keyword in description or keyword in department:
                match.score -= 3
                match.evidence.append(f'negative keyword "{keyword}" lowered score for {family}')

    return match


def _compute_confidence(top: _RoleMatch, second_score: int) -> float:
    score_component = min(0.55, top.score / 20.0)
    margin_component = min(0.2, max(top.score - second_score, 0) / 10.0)
    title_component = 0.15 if top.strong_title_match else 0.08 if top.any_title_match else 0.0
    context_component = 0.05 if top.context_match else 0.0
    confidence = min(0.98, score_component + margin_component + title_component + context_component)
    if top.score < 5:
        confidence = min(confidence, 0.45)
    elif top.score < 8:
        confidence = min(confidence, 0.65)
    return round(confidence, 3)


def _preference_index(family: str, preferences: list[str]) -> int:
    try:
        return len(preferences) - preferences.index(family)
    except ValueError:
        return 0


def _normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip().casefold() for item in value if isinstance(item, str) and item.strip()]


def _normalize_optional_string(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _sorted_keywords(keywords: list[str]) -> list[str]:
    return sorted(keywords, key=len, reverse=True)


def _is_subsumed(keyword: str, existing_matches: list[str]) -> bool:
    return any(keyword in existing for existing in existing_matches)


__all__ = [
    "classify_job_role",
    "classify_role",
    "resolve_role_keywords",
]
