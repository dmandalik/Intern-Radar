"""Role-fit scoring against target and deprioritized families."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from internradar.core.models import Job

DEFAULT_TARGET_ROLES = {
    "quant_developer",
    "trading_systems_engineer",
    "algorithmic_trading_engineer",
    "software_engineer_trading",
    "low_latency_engineer",
    "market_data_engineer",
    "infrastructure_engineer",
    "fpga_engineer",
    "hardware_trading_engineer",
    "ml_engineer_quant",
    "data_engineer_quant",
    "research_engineer_quant",
}
DEFAULT_ADJACENT_ROLES = {
    "quant_research",
    "quant_trading",
}
DEFAULT_DEPRIORITIZED_ROLES = {
    "finance_analyst",
    "trading_operations",
    "other",
}
DEFAULT_EXCLUDED_ROLES = set()


def score_role_fit(
    job: Job,
    *,
    config: Mapping[str, Any] | None = None,
) -> tuple[float, list[str]]:
    """Score role fit against configured target families."""
    target_roles, adjacent_roles, deprioritized_roles, excluded_roles = _resolve_role_preferences(config)
    family = job.role.role_family
    confidence_boost = min(5.0, job.role.confidence * 5.0)
    evidence = job.role.evidence[0] if job.role.evidence else None

    if family in target_roles:
        score = min(100.0, 92.0 + confidence_boost)
        explanation = [f"Role family '{family}' is in the target set."]
    elif family in adjacent_roles:
        score = 72.0 + confidence_boost
        explanation = [f"Role family '{family}' is adjacent to the target set."]
    elif family in deprioritized_roles:
        score = max(20.0, 35.0 - confidence_boost)
        explanation = [f"Role family '{family}' is deprioritized for this ranking profile."]
    elif family in excluded_roles:
        score = 10.0
        explanation = [f"Role family '{family}' is explicitly excluded."]
    elif family == "unknown":
        score = 40.0
        explanation = ["Role family is unknown, so role fit stays neutral-low."]
    else:
        score = 55.0
        explanation = [f"Role family '{family}' is not a primary target but remains somewhat relevant."]

    if evidence is not None:
        explanation.append(f"Classifier evidence: {evidence}")
    return round(score, 2), explanation


def _resolve_role_preferences(
    config: Mapping[str, Any] | None,
) -> tuple[set[str], set[str], set[str], set[str]]:
    scoring = config.get("scoring") if isinstance(config, Mapping) else None
    if not isinstance(scoring, Mapping):
        return (
            set(DEFAULT_TARGET_ROLES),
            set(DEFAULT_ADJACENT_ROLES),
            set(DEFAULT_DEPRIORITIZED_ROLES),
            set(DEFAULT_EXCLUDED_ROLES),
        )

    return (
        _string_set(scoring.get("target_roles")) or set(DEFAULT_TARGET_ROLES),
        _string_set(scoring.get("adjacent_roles")) or set(DEFAULT_ADJACENT_ROLES),
        _string_set(scoring.get("deprioritized_roles")) or set(DEFAULT_DEPRIORITIZED_ROLES),
        _string_set(scoring.get("excluded_roles")) or set(DEFAULT_EXCLUDED_ROLES),
    )


def _string_set(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {
        item.strip()
        for item in value
        if isinstance(item, str) and item.strip()
    }


__all__ = ["score_role_fit"]
