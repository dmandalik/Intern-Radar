"""Opportunity scoring orchestration."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from internradar.core.models import Company, Job, JobScores
from internradar.scoring.eligibility_score import score_eligibility
from internradar.scoring.freshness import score_freshness
from internradar.scoring.hidden_gems import score_hidden_gem
from internradar.scoring.prestige import score_prestige
from internradar.scoring.ranking_presets import resolve_ranking_preset
from internradar.scoring.role_fit import score_role_fit
from internradar.scoring.technical_depth import score_technical_depth


def score_job(
    job: Job,
    *,
    company: Company | None = None,
    config: Mapping[str, Any] | None = None,
    pack_name: str | None = None,
    preset: str | None = None,
    root: Path | None = None,
) -> Job:
    """Score a normalized job and return an updated copy."""
    preset_name, weights = resolve_ranking_preset(preset=preset, config=config)
    prestige_score, prestige_explanation, resolved_tier = score_prestige(
        job,
        company=company,
        config=config,
        pack_name=pack_name,
        root=root,
    )
    role_fit_score, role_fit_explanation = score_role_fit(job, config=config)
    technical_depth_score, technical_explanation = score_technical_depth(job)
    freshness_score, freshness_explanation = score_freshness(
        job,
        apply_now_mode=(preset_name == "apply_now"),
    )
    eligibility_score_value, eligibility_explanation = score_eligibility(job, config=config)
    hidden_gem_score, hidden_gem_explanation = score_hidden_gem(
        job,
        prestige_score=prestige_score,
        role_fit_score=role_fit_score,
        technical_depth_score=technical_depth_score,
        freshness_score=freshness_score,
        eligibility_score=eligibility_score_value,
    )
    component_scores = {
        "prestige": prestige_score,
        "role_fit": role_fit_score,
        "technical_depth": technical_depth_score,
        "freshness": freshness_score,
        "eligibility": eligibility_score_value,
        "hidden_gem": hidden_gem_score,
        "status_open": _status_open_score(job),
    }
    opportunity_score = _weighted_score(component_scores, weights)
    explanation = _build_explanation(
        preset_name=preset_name,
        weights=weights,
        component_scores=component_scores,
        prestige_explanation=prestige_explanation,
        role_fit_explanation=role_fit_explanation,
        technical_explanation=technical_explanation,
        freshness_explanation=freshness_explanation,
        eligibility_explanation=eligibility_explanation,
        hidden_gem_explanation=hidden_gem_explanation,
    )

    scores = JobScores(
        prestige_score=round(prestige_score, 2),
        role_fit_score=round(role_fit_score, 2),
        technical_depth_score=round(technical_depth_score, 2),
        hidden_gem_score=round(hidden_gem_score, 2),
        freshness_score=round(freshness_score, 2),
        eligibility_score=round(eligibility_score_value, 2),
        opportunity_score=round(opportunity_score, 2),
        explanation=explanation,
    )
    return job.model_copy(
        update={
            "scores": scores,
            "prestige_tier": resolved_tier,
        },
    )


def _weighted_score(component_scores: Mapping[str, float], weights: Mapping[str, float]) -> float:
    total = 0.0
    for key, weight in weights.items():
        total += component_scores.get(key, 0.0) * float(weight)
    return max(0.0, min(100.0, total))


def _status_open_score(job: Job) -> float:
    mapping = {
        "open": 100.0,
        "likely_open": 80.0,
        "coming_soon": 55.0,
        "requires_login": 35.0,
        "unknown": 40.0,
        "stale": 20.0,
        "closed": 0.0,
    }
    return mapping.get(job.status.status, 40.0)


def _build_explanation(
    *,
    preset_name: str,
    weights: Mapping[str, float],
    component_scores: Mapping[str, float],
    prestige_explanation: list[str],
    role_fit_explanation: list[str],
    technical_explanation: list[str],
    freshness_explanation: list[str],
    eligibility_explanation: list[str],
    hidden_gem_explanation: list[str],
) -> list[str]:
    weighted_components = sorted(
        (
            (component_scores.get(key, 0.0) * float(weight), key, component_scores.get(key, 0.0))
            for key, weight in weights.items()
        ),
        reverse=True,
    )
    explanation = [f"Opportunity score used the {preset_name} preset."]
    for _, key, score in weighted_components[:3]:
        explanation.append(f"{key} contributed strongly with score {score:.0f}.")

    explanation.extend(
        [
            prestige_explanation[0],
            role_fit_explanation[0],
            technical_explanation[0],
            freshness_explanation[0],
            eligibility_explanation[0],
            hidden_gem_explanation[0],
        ],
    )
    deduped: list[str] = []
    seen: set[str] = set()
    for item in explanation:
        normalized = item.casefold()
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(item)
    return deduped[:10]


__all__ = ["score_job"]
