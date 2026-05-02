"""Prestige tier scoring."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from internradar.core.models import Company, Job
from internradar.core.pack_loader import PackLoaderError, load_pack_prestige_tiers

PRESTIGE_SCORE_MAP = {
    "S+": 100.0,
    "S": 90.0,
    "A": 80.0,
    "B": 70.0,
    "C": 60.0,
    "Unknown": 50.0,
}
TIER_ALIASES = {
    "tier_1": "S+",
    "tier_2": "S",
    "tier_3": "A",
    "tier_4": "B",
    "tier_5": "C",
    "unknown": "Unknown",
}


def score_prestige(
    job: Job,
    *,
    company: Company | None = None,
    config: Mapping[str, Any] | None = None,
    pack_name: str | None = None,
    root: Path | None = None,
) -> tuple[float, list[str], str]:
    """Return prestige score, explanation, and resolved tier label."""
    resolved_tier, source = resolve_prestige_tier(
        job=job,
        company=company,
        config=config,
        pack_name=pack_name,
        root=root,
    )
    score = PRESTIGE_SCORE_MAP.get(resolved_tier, PRESTIGE_SCORE_MAP["Unknown"])
    if source == "default":
        explanation = ["No prestige tier was configured, so a neutral prestige score was used."]
    else:
        explanation = [f"Prestige tier {resolved_tier} came from {source}."]
    return score, explanation, resolved_tier


def resolve_prestige_tier(
    *,
    job: Job,
    company: Company | None = None,
    config: Mapping[str, Any] | None = None,
    pack_name: str | None = None,
    root: Path | None = None,
) -> tuple[str, str]:
    """Resolve normalized prestige tier and the source of that tier."""
    override_tier = _override_tier(company=company, job=job, config=config)
    if override_tier is not None:
        return override_tier, "user override"

    explicit_tier = _normalize_tier_label(job.prestige_tier)
    if explicit_tier is not None:
        return explicit_tier, "job/company metadata"

    company_tier = _normalize_tier_label(company.default_prestige_tier if company is not None else None)
    if company_tier is not None:
        return company_tier, "company profile"

    if pack_name is not None and company is not None:
        pack_tier = _pack_tier_for_company(company, pack_name=pack_name, root=root)
        if pack_tier is not None:
            return pack_tier, "pack defaults"

    return "Unknown", "default"


def _override_tier(
    *,
    company: Company | None,
    job: Job,
    config: Mapping[str, Any] | None,
) -> str | None:
    if not isinstance(config, Mapping):
        return None
    scoring = config.get("scoring")
    if not isinstance(scoring, Mapping):
        return None
    overrides = scoring.get("prestige_overrides")
    if not isinstance(overrides, Mapping):
        return None

    candidates = [
        job.company_id,
        job.company_name,
        company.id if company is not None else None,
        company.name if company is not None else None,
    ]
    normalized_overrides = {
        str(key).casefold(): value
        for key, value in overrides.items()
    }
    for candidate in candidates:
        if not isinstance(candidate, str):
            continue
        override = normalized_overrides.get(candidate.casefold())
        if override is None:
            continue
        normalized = _normalize_tier_label(override)
        if normalized is not None:
            return normalized
    return None


def _pack_tier_for_company(
    company: Company,
    *,
    pack_name: str,
    root: Path | None,
) -> str | None:
    try:
        payload = load_pack_prestige_tiers(pack_name, root=root)
    except PackLoaderError:
        return None

    prestige_tiers = payload.get("prestige_tiers")
    if not isinstance(prestige_tiers, Mapping):
        return None

    candidates = {company.name.casefold(), *(alias.casefold() for alias in company.aliases)}
    for tier_label, names in prestige_tiers.items():
        if not isinstance(names, list):
            continue
        if any(isinstance(name, str) and name.casefold() in candidates for name in names):
            return _normalize_tier_label(tier_label)
    return None


def _normalize_tier_label(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    stripped = value.strip()
    if stripped in PRESTIGE_SCORE_MAP:
        return stripped
    aliased = TIER_ALIASES.get(stripped.casefold())
    if aliased is not None:
        return aliased
    if stripped.casefold() == "unknown":
        return "Unknown"
    return stripped if stripped in PRESTIGE_SCORE_MAP else None


__all__ = ["PRESTIGE_SCORE_MAP", "resolve_prestige_tier", "score_prestige"]
