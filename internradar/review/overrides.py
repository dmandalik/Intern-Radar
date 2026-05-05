"""Local manual overrides for companies, jobs, and ignore rules."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from internradar.core.models import Company, Job
from internradar.core.paths import home_overrides_path, local_overrides_path


class OverrideError(ValueError):
    """Raised when manual overrides cannot be loaded or applied safely."""


@dataclass(slots=True)
class ReviewOverrides:
    company_overrides: dict[str, dict[str, Any]] = field(default_factory=dict)
    job_overrides: dict[str, dict[str, Any]] = field(default_factory=dict)
    ignored_companies: list[str] = field(default_factory=list)
    ignored_keywords: list[str] = field(default_factory=list)
    source_path: Path | None = None


@dataclass(slots=True)
class AppliedOverrides:
    company: Company
    job: Job
    application_status: str | None = None
    notes: str | None = None
    ignore_reasons: list[str] = field(default_factory=list)


def load_overrides(
    *,
    cwd: Path | None = None,
    home: Path | None = None,
) -> ReviewOverrides:
    """Load home and local overrides with local precedence."""
    merged: dict[str, Any] = {}
    source_path: Path | None = None
    for path in (home_overrides_path(home), local_overrides_path(cwd)):
        if not path.exists():
            continue
        payload = _read_yaml_mapping(path)
        merged = _deep_merge(merged, payload)
        source_path = path

    return ReviewOverrides(
        company_overrides=_mapping_of_mappings(merged.get("company_overrides")),
        job_overrides=_mapping_of_mappings(merged.get("job_overrides")),
        ignored_companies=_string_list(merged.get("ignored_companies")),
        ignored_keywords=_string_list(merged.get("ignored_keywords")),
        source_path=source_path,
    )


def apply_score_relevant_overrides(
    job: Job,
    *,
    company: Company,
    overrides: ReviewOverrides,
) -> tuple[Company, Job]:
    """Apply company/job overrides that affect persisted fields or scoring."""
    overridden_company = apply_company_overrides(company, overrides)
    overridden_job = apply_job_overrides(job, overrides)
    job_override = overrides.job_overrides.get(overridden_job.id, {})
    explicit_job_prestige = _optional_string(job_override.get("prestige_tier"))
    if explicit_job_prestige is None and overridden_company.default_prestige_tier:
        overridden_job = overridden_job.model_copy(
            update={"prestige_tier": overridden_company.default_prestige_tier},
        )
    return overridden_company, overridden_job


def apply_overrides(
    job: Job,
    *,
    company: Company,
    overrides: ReviewOverrides,
) -> AppliedOverrides:
    """Apply all relevant overrides and return persisted action hints."""
    overridden_company, overridden_job = apply_score_relevant_overrides(
        job,
        company=company,
        overrides=overrides,
    )
    job_override = overrides.job_overrides.get(overridden_job.id, {})
    ignore_reasons = ignored_reasons_for_job(overridden_job, company=overridden_company, overrides=overrides)
    application_status = _optional_string(job_override.get("application_status"))
    notes = _optional_string(job_override.get("notes"))
    if ignore_reasons and application_status is None:
        application_status = "ignored"
    if ignore_reasons and notes is None:
        notes = "; ".join(ignore_reasons)
    return AppliedOverrides(
        company=overridden_company,
        job=overridden_job,
        application_status=application_status,
        notes=notes,
        ignore_reasons=ignore_reasons,
    )


def apply_company_overrides(company: Company, overrides: ReviewOverrides) -> Company:
    """Apply company-level overrides using ID, name, or aliases as keys."""
    override = _match_company_override(company, overrides.company_overrides)
    if not override:
        return company

    updates: dict[str, Any] = {}
    prestige_tier = _optional_string(override.get("prestige_tier"))
    if prestige_tier is not None:
        updates["default_prestige_tier"] = prestige_tier
    notes = _optional_string(override.get("notes"))
    if notes is not None:
        updates["notes"] = notes
    return company.model_copy(update=updates) if updates else company


def apply_job_overrides(job: Job, overrides: ReviewOverrides) -> Job:
    """Apply job-level manual overrides to normalized jobs."""
    override = overrides.job_overrides.get(job.id, {})
    if not override:
        return job

    current = job
    prestige_tier = _optional_string(override.get("prestige_tier"))
    if prestige_tier is not None:
        current = current.model_copy(update={"prestige_tier": prestige_tier})

    role_family = _optional_string(override.get("role_family"))
    if role_family is not None:
        current = current.model_copy(
            update={
                "role": current.role.model_copy(
                    update={
                        "role_family": role_family,
                        "confidence": 1.0,
                        "evidence": [f"manual override set role family to '{role_family}'"],
                    },
                ),
            },
        )

    status = _optional_string(override.get("status"))
    if status is not None:
        current = current.model_copy(
            update={
                "status": current.status.model_copy(
                    update={
                        "status": status,
                        "confidence": 1.0,
                        "evidence": [f"manual override set status to '{status}'"],
                        "checked_at": datetime.now(UTC),
                    },
                ),
                "last_verified": datetime.now(UTC),
            },
        )

    return current


def ignored_reasons_for_job(
    job: Job,
    *,
    company: Company,
    overrides: ReviewOverrides,
) -> list[str]:
    """Return human-readable ignore reasons for a job."""
    reasons: list[str] = []
    ignored_companies = {entry.casefold() for entry in overrides.ignored_companies}
    company_values = {company.id.casefold(), company.name.casefold(), *(alias.casefold() for alias in company.aliases)}
    if ignored_companies & company_values:
        reasons.append(f"ignored company '{company.name}'")

    haystack = " ".join(part for part in [job.title, job.description or ""] if part).casefold()
    for keyword in overrides.ignored_keywords:
        needle = keyword.casefold()
        if needle and needle in haystack:
            reasons.append(f"ignored keyword '{keyword}'")
    return reasons


def _match_company_override(
    company: Company,
    overrides: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    candidates = {company.id.casefold(), company.name.casefold(), *(alias.casefold() for alias in company.aliases)}
    for key, value in overrides.items():
        if key.casefold() in candidates:
            return value
    return None


def _read_yaml_mapping(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise OverrideError(f"Invalid overrides YAML in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise OverrideError(f"Expected a mapping in overrides file: {path}")
    return dict(data)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(merged.get(key), dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _mapping_of_mappings(value: Any) -> dict[str, dict[str, Any]]:
    if value in (None, ""):
        return {}
    if not isinstance(value, dict):
        raise OverrideError("Expected override sections to be mappings.")
    normalized: dict[str, dict[str, Any]] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, dict):
            raise OverrideError("Expected override entries to map strings to mappings.")
        normalized[key] = dict(item)
    return normalized


def _string_list(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise OverrideError("Expected ignored override entries to be string lists.")
    return [item.strip() for item in value if item.strip()]


def _optional_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None
