"""Ranking preset resolution for opportunity scoring."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

DEFAULT_PRESET = "cs_algo_engineering"
RANKING_PRESETS: dict[str, dict[str, float]] = {
    "cs_algo_engineering": {
        "role_fit": 0.35,
        "technical_depth": 0.20,
        "freshness": 0.15,
        "eligibility": 0.15,
        "prestige": 0.10,
        "hidden_gem": 0.05,
    },
    "prestige_first": {
        "prestige": 0.40,
        "role_fit": 0.25,
        "freshness": 0.15,
        "eligibility": 0.10,
        "hidden_gem": 0.05,
        "technical_depth": 0.05,
    },
    "hidden_gems": {
        "hidden_gem": 0.35,
        "role_fit": 0.25,
        "freshness": 0.20,
        "eligibility": 0.10,
        "technical_depth": 0.10,
    },
    "apply_now": {
        "freshness": 0.30,
        "status_open": 0.25,
        "role_fit": 0.20,
        "eligibility": 0.15,
        "prestige": 0.10,
    },
    "beginner_friendly": {
        "eligibility": 0.35,
        "freshness": 0.20,
        "role_fit": 0.20,
        "hidden_gem": 0.15,
        "prestige": 0.10,
    },
}


def resolve_ranking_preset(
    preset: str | None = None,
    config: Mapping[str, Any] | None = None,
) -> tuple[str, dict[str, float]]:
    """Resolve ranking preset weights from an explicit name or config."""
    configured_name = _configured_preset_name(config)
    preset_name = (preset or configured_name or DEFAULT_PRESET).strip()
    if not preset_name:
        preset_name = DEFAULT_PRESET

    normalized_name = preset_name.casefold()
    for known_name, weights in RANKING_PRESETS.items():
        if known_name.casefold() == normalized_name:
            return known_name, dict(weights)

    if normalized_name == "custom":
        custom_weights = _custom_weights(config)
        if custom_weights:
            return "custom", custom_weights

    return DEFAULT_PRESET, dict(RANKING_PRESETS[DEFAULT_PRESET])


def available_presets() -> list[str]:
    return [*RANKING_PRESETS.keys(), "custom"]


def _configured_preset_name(config: Mapping[str, Any] | None) -> str | None:
    if not isinstance(config, Mapping):
        return None
    scoring = config.get("scoring")
    if isinstance(scoring, Mapping):
        value = scoring.get("preset")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _custom_weights(config: Mapping[str, Any] | None) -> dict[str, float] | None:
    if not isinstance(config, Mapping):
        return None
    scoring = config.get("scoring")
    if not isinstance(scoring, Mapping):
        return None
    custom = scoring.get("custom_preset")
    if not isinstance(custom, Mapping):
        return None

    weights: dict[str, float] = {}
    total = 0.0
    for key, value in custom.items():
        if not isinstance(value, (int, float)):
            continue
        numeric = float(value)
        if numeric <= 0:
            continue
        weights[str(key)] = numeric
        total += numeric

    if not weights or total <= 0:
        return None
    return {key: round(value / total, 4) for key, value in weights.items()}


__all__ = ["DEFAULT_PRESET", "RANKING_PRESETS", "available_presets", "resolve_ranking_preset"]
