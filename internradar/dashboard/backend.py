"""Dashboard data loading, filtering, and action helpers."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from internradar.commands.export import run_export
from internradar.core.config import load_config, resolve_user_config_path
from internradar.core.database import (
    database_exists,
    load_job_raw_payload,
    load_jobs,
    load_jobs_by_ids,
    load_latest_scan_run,
    load_user_actions,
    record_user_action,
)
from internradar.core.errors import DatabaseError
from internradar.core.models import Job
from internradar.core.paths import local_database_path, local_exports_dir

DEFAULT_HIDDEN_GEM_THRESHOLD = 70.0
REVIEW_CONFIDENCE_THRESHOLD = 0.55
ELIGIBILITY_REVIEW_THRESHOLD = 0.35
POSITIVE_APPLICATION_STATES = {"saved", "applied", "oa_received", "interviewing", "offer"}


def ensure_dashboard_database(cwd: Path | None = None) -> None:
    """Require a local database before dashboard API work proceeds."""
    if not database_exists(cwd):
        raise DatabaseError(
            f"No local database found at {local_database_path(cwd)}. Run `internradar init` and `internradar scan` first.",
        )


def load_dashboard_jobs(
    *,
    cwd: Path | None = None,
) -> list[dict[str, Any]]:
    """Load normalized jobs and merge in latest user action state."""
    ensure_dashboard_database(cwd)
    jobs = load_jobs(cwd=cwd)
    actions_by_job = load_user_actions(cwd=cwd)
    return [_serialize_job(job, actions_by_job.get(job.id, {})) for job in jobs]


def filter_dashboard_jobs(
    jobs: list[dict[str, Any]],
    *,
    status: str | None = None,
    role_family: str | None = None,
    company: str | None = None,
    prestige_tier: str | None = None,
    location: str | None = None,
    season: str | None = None,
    year: int | None = None,
    application_status: str | None = None,
    source_type: str | None = None,
    remote_type: str | None = None,
    sponsorship: str | None = None,
    min_opportunity_score: float | None = None,
    min_hidden_gem_score: float | None = None,
    min_eligibility_score: float | None = None,
    search: str | None = None,
) -> list[dict[str, Any]]:
    """Filter dashboard jobs using API-friendly criteria."""
    filtered = list(jobs)
    if status:
        needle = status.casefold()
        filtered = [job for job in filtered if job["status"] == needle]
    if role_family:
        needle = role_family.casefold()
        filtered = [job for job in filtered if job["role_family"].casefold() == needle]
    if company:
        needle = company.casefold()
        filtered = [job for job in filtered if needle in job["company_name"].casefold()]
    if prestige_tier:
        needle = prestige_tier.casefold()
        filtered = [job for job in filtered if (job["prestige_tier"] or "").casefold() == needle]
    if location:
        needle = location.casefold()
        filtered = [job for job in filtered if any(needle in entry.casefold() for entry in job["locations"])]
    if season:
        needle = season.casefold()
        filtered = [job for job in filtered if (job["season"] or "").casefold() == needle]
    if year is not None:
        filtered = [job for job in filtered if job["year"] == year]
    if application_status:
        needle = application_status.casefold()
        filtered = [job for job in filtered if (job["application_status"] or "").casefold() == needle]
    if source_type:
        needle = source_type.casefold()
        filtered = [job for job in filtered if job["source_type"].casefold() == needle]
    if remote_type:
        needle = remote_type.casefold()
        filtered = [job for job in filtered if (job["remote_type"] or "").casefold() == needle]
    if sponsorship:
        needle = sponsorship.casefold()
        filtered = [job for job in filtered if (job["eligibility"]["sponsorship"] or "").casefold() == needle]
    if min_opportunity_score is not None:
        filtered = [job for job in filtered if float(job["scores"]["opportunity_score"]) >= min_opportunity_score]
    if min_hidden_gem_score is not None:
        filtered = [job for job in filtered if float(job["scores"]["hidden_gem_score"]) >= min_hidden_gem_score]
    if min_eligibility_score is not None:
        filtered = [job for job in filtered if float(job["scores"]["eligibility_score"]) >= min_eligibility_score]
    if search:
        needle = search.casefold()
        filtered = [
            job
            for job in filtered
            if needle in " ".join(
                [
                    job["company_name"],
                    job["title"],
                    job["role_family"],
                    job["description"] or "",
                    job["source_type"],
                    job["status"],
                ],
            ).casefold()
        ]
    return filtered


def sort_dashboard_jobs(
    jobs: list[dict[str, Any]],
    *,
    sort: str,
) -> list[dict[str, Any]]:
    """Sort dashboard jobs with stable tiebreakers."""
    normalized = sort.strip().casefold()
    mapping = {
        "opportunity_score": lambda job: float(job["scores"]["opportunity_score"]),
        "newest": lambda job: job["last_verified"],
        "prestige": lambda job: float(job["scores"]["prestige_score"]),
        "hidden_gem_score": lambda job: float(job["scores"]["hidden_gem_score"]),
        "eligibility_score": lambda job: float(job["scores"]["eligibility_score"]),
        "technical_depth": lambda job: float(job["scores"]["technical_depth_score"]),
        "company_name": lambda job: job["company_name"].casefold(),
        "company": lambda job: job["company_name"].casefold(),
        "location": lambda job: job["location_label"].casefold(),
    }
    key_func = mapping.get(normalized, mapping["opportunity_score"])
    reverse = normalized not in {"company_name", "company", "location"}
    return sorted(
        jobs,
        key=lambda job: (key_func(job), job["company_name"].casefold(), job["title"].casefold()),
        reverse=reverse,
    )


def paginate_jobs(
    jobs: list[dict[str, Any]],
    *,
    limit: int | None,
    offset: int,
) -> list[dict[str, Any]]:
    """Apply limit/offset pagination."""
    if offset < 0:
        offset = 0
    paged = jobs[offset:]
    if limit is not None:
        paged = paged[:limit]
    return paged


def load_job_detail(
    job_id: str,
    *,
    cwd: Path | None = None,
) -> dict[str, Any] | None:
    """Load one serialized job plus stored raw payload."""
    ensure_dashboard_database(cwd)
    jobs = load_jobs_by_ids([job_id], cwd=cwd)
    job = jobs.get(job_id)
    if job is None:
        return None
    action_state = load_user_actions(cwd=cwd).get(job.id, {})
    payload = _serialize_job(job, action_state)
    payload["raw_payload"] = load_job_raw_payload(job.id, cwd=cwd)
    return payload


def load_filter_options(
    *,
    cwd: Path | None = None,
) -> dict[str, Any]:
    """Build dashboard filter options from current saved jobs."""
    jobs = load_dashboard_jobs(cwd=cwd)
    return {
        "statuses": _sorted_unique(job["status"] for job in jobs),
        "role_families": _sorted_unique(job["role_family"] for job in jobs),
        "companies": _sorted_unique(job["company_name"] for job in jobs),
        "prestige_tiers": _sorted_unique(job["prestige_tier"] for job in jobs if job["prestige_tier"]),
        "locations": _sorted_unique(location for job in jobs for location in job["locations"]),
        "seasons": _sorted_unique(job["season"] for job in jobs if job["season"]),
        "years": sorted({job["year"] for job in jobs if job["year"] is not None}),
        "application_statuses": _sorted_unique(job["application_status"] for job in jobs if job["application_status"]),
        "source_types": _sorted_unique(job["source_type"] for job in jobs),
        "remote_types": _sorted_unique(job["remote_type"] for job in jobs if job["remote_type"]),
        "sponsorships": _sorted_unique(
            job["eligibility"]["sponsorship"]
            for job in jobs
            if job["eligibility"]["sponsorship"]
        ),
    }


def load_dashboard_summary(
    *,
    cwd: Path | None = None,
) -> dict[str, Any]:
    """Compute headline dashboard summary and insight panels."""
    jobs = sort_dashboard_jobs(load_dashboard_jobs(cwd=cwd), sort="opportunity_score")
    status_counts = Counter(job["status"] for job in jobs)
    role_counts = Counter(job["role_family"] for job in jobs)
    company_counts = Counter(job["company_name"] for job in jobs)
    latest_scan = load_latest_scan_run(cwd=cwd)
    saved_count = sum(1 for job in jobs if job["saved"])
    applied_count = sum(1 for job in jobs if job["applied"])
    hidden_gems = [job for job in jobs if float(job["scores"]["hidden_gem_score"]) >= DEFAULT_HIDDEN_GEM_THRESHOLD]
    open_jobs = [job for job in jobs if job["status"] in {"open", "likely_open"}]
    coming_soon = [job for job in jobs if job["status"] == "coming_soon"]
    review_needed = [job for job in jobs if job["needs_review"]]
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "database_ready": True,
        "total_jobs": len(jobs),
        "counts": {
            "open": status_counts.get("open", 0),
            "likely_open": status_counts.get("likely_open", 0),
            "coming_soon": status_counts.get("coming_soon", 0),
            "closed": status_counts.get("closed", 0),
            "unknown": status_counts.get("unknown", 0) + status_counts.get("requires_login", 0),
            "hidden_gems": len(hidden_gems),
            "saved": saved_count,
            "applied": applied_count,
            "review_needed": len(review_needed),
        },
        "apply_first": open_jobs[:5],
        "signals": {
            "hidden_gems": hidden_gems[:5],
            "coming_soon": coming_soon[:5],
            "review_needed": review_needed[:5],
        },
        "charts": {
            "status": _chart_rows(status_counts),
            "role_family": _chart_rows(role_counts, limit=8),
            "top_companies": _chart_rows(company_counts, limit=8),
        },
        "latest_scan": latest_scan,
        "pack": _resolve_dashboard_pack(latest_scan),
        "last_scan_at": (latest_scan or {}).get("completed_at"),
    }


def load_dashboard_settings(
    *,
    cwd: Path | None = None,
) -> dict[str, Any]:
    """Return read-only current config and related paths."""
    config = load_config(cwd=cwd)
    latest_scan = load_latest_scan_run(cwd=cwd)
    return {
        "read_only": True,
        "config_path": str(resolve_user_config_path(cwd=cwd) or ""),
        "database_path": str(local_database_path(cwd)),
        "exports_path": str(local_exports_dir(cwd)),
        "active_pack": _resolve_dashboard_pack(latest_scan) or _configured_pack(config),
        "ranking_preset": _read_nested(config, "ranking", "preset"),
        "candidate": _read_nested(config, "candidate"),
        "target_roles": _read_nested(config, "ranking", "target_roles") or [],
        "deprioritized_roles": _read_nested(config, "ranking", "deprioritized_roles") or [],
        "preferred_locations": _read_nested(config, "candidate", "preferred_locations") or [],
        "raw_config": config,
    }


def persist_dashboard_action(
    job_id: str,
    *,
    action: str,
    value: str | None = None,
    notes: str | None = None,
    cwd: Path | None = None,
) -> dict[str, Any]:
    """Record a dashboard action and return fresh job detail."""
    ensure_dashboard_database(cwd)
    normalized = action.strip().casefold()
    if normalized == "save":
        record_user_action(job_id, action_type="saved", action_value="true", notes=notes, cwd=cwd)
    elif normalized == "ignore":
        record_user_action(job_id, action_type="application_status", action_value="ignored", notes=notes, cwd=cwd)
    elif normalized == "mark_applied":
        record_user_action(job_id, action_type="applied", action_value="true", notes=notes, cwd=cwd)
    elif normalized == "mark_reviewed":
        record_user_action(job_id, action_type="reviewed", action_value="true", notes=notes, cwd=cwd)
    elif normalized in {"oa_received", "interviewing", "rejected", "offer", "not_interested", "saved", "applied"}:
        record_user_action(job_id, action_type="application_status", action_value=normalized, notes=notes, cwd=cwd)
    else:
        record_user_action(job_id, action_type=normalized, action_value=value, notes=notes, cwd=cwd)

    detail = load_job_detail(job_id, cwd=cwd)
    if detail is None:
        raise DatabaseError(f"Job '{job_id}' was not found in the local database.")
    return detail


def persist_dashboard_notes(
    job_id: str,
    *,
    notes: str,
    cwd: Path | None = None,
) -> dict[str, Any]:
    """Persist free-form dashboard notes and return fresh job detail."""
    ensure_dashboard_database(cwd)
    record_user_action(job_id, action_type="notes", action_value=notes, notes=notes, cwd=cwd)
    detail = load_job_detail(job_id, cwd=cwd)
    if detail is None:
        raise DatabaseError(f"Job '{job_id}' was not found in the local database.")
    return detail


def create_dashboard_export(
    *,
    format_name: str | None,
    all_formats: bool,
    output: Path | None,
    status: str | None,
    hidden_gems: bool,
    saved: bool,
    applied: bool,
    limit: int | None,
    sort: str,
    pack: str | None,
    include_closed: bool,
    cwd: Path | None = None,
) -> list[Path]:
    """Run existing exporters for dashboard-triggered exports."""
    return run_export(
        format_name=format_name,
        all_formats=all_formats,
        output=output,
        status=status,
        hidden_gems=hidden_gems,
        saved=saved,
        applied=applied,
        limit=limit,
        sort_key=sort,
        pack=pack,
        include_closed=include_closed,
        cwd=cwd,
    )


def _serialize_job(job: Job, action_state: dict[str, str]) -> dict[str, Any]:
    application_status = _normalized_application_status(action_state)
    saved = action_state.get("saved") in {"true", "1", "yes"} or application_status in POSITIVE_APPLICATION_STATES
    applied = action_state.get("applied") in {"true", "1", "yes"} or application_status in {
        "applied",
        "oa_received",
        "interviewing",
        "offer",
        "rejected",
    }
    payload = {
        "id": job.id,
        "company_id": job.company_id,
        "company_name": job.company_name,
        "title": job.title,
        "description": job.description,
        "apply_url": job.apply_url,
        "source_url": job.source_url,
        "source_type": job.source_type,
        "role_family": job.role.role_family,
        "role_subtype": job.role.role_subtype,
        "role_confidence": job.role.confidence,
        "role_evidence": list(job.role.evidence),
        "season": job.season,
        "year": job.year,
        "locations": list(job.locations),
        "location_label": ", ".join(job.locations) if job.locations else "Location TBD",
        "remote_type": job.remote_type,
        "status": job.status.status,
        "status_confidence": job.status.confidence,
        "status_evidence": list(job.status.evidence),
        "eligibility": job.eligibility.model_dump(mode="json"),
        "eligibility_summary": _eligibility_summary(job),
        "scores": job.scores.model_dump(mode="json"),
        "score_explanation": list(job.scores.explanation),
        "prestige_tier": job.prestige_tier,
        "tags": list(job.tags),
        "first_seen": job.first_seen.isoformat(),
        "last_seen": job.last_seen.isoformat(),
        "last_verified": job.last_verified.isoformat(),
        "application_status": application_status,
        "saved": saved,
        "applied": applied,
        "ignored": action_state.get("ignored") in {"true", "1", "yes"} or application_status == "ignored",
        "reviewed": action_state.get("reviewed") in {"true", "1", "yes"},
        "notes": action_state.get("notes", ""),
        "updated_at": action_state.get("updated_at"),
    }
    payload["needs_review"] = _needs_review(payload)
    return payload


def _needs_review(job: dict[str, Any]) -> bool:
    return any(
        (
            job["status"] in {"unknown", "requires_login"},
            float(job["role_confidence"]) < REVIEW_CONFIDENCE_THRESHOLD,
            float(job["eligibility"]["confidence"]) < ELIGIBILITY_REVIEW_THRESHOLD,
            not job["description"],
            job["year"] is None,
        ),
    )


def _normalized_application_status(action_state: dict[str, str]) -> str:
    status = action_state.get("application_status", "").strip()
    if status:
        return status
    if action_state.get("applied") in {"true", "1", "yes"}:
        return "applied"
    if action_state.get("saved") in {"true", "1", "yes"}:
        return "saved"
    return ""


def _eligibility_summary(job: Job) -> str:
    parts: list[str] = []
    if job.eligibility.degree_levels:
        parts.append(", ".join(job.eligibility.degree_levels))
    if job.eligibility.graduation_years:
        parts.append("Grad " + ", ".join(str(year) for year in job.eligibility.graduation_years))
    if job.eligibility.majors:
        parts.append(", ".join(job.eligibility.majors[:3]))
    if job.eligibility.sponsorship:
        parts.append("Sponsorship: " + job.eligibility.sponsorship)
    return " | ".join(parts)


def _chart_rows(counter: Counter[str], limit: int | None = None) -> list[dict[str, Any]]:
    rows = [{"label": label, "value": value} for label, value in counter.most_common(limit)]
    return rows


def _sorted_unique(values: Any) -> list[str]:
    items = {str(value) for value in values if value not in (None, "")}
    return sorted(items, key=str.casefold)


def _resolve_dashboard_pack(latest_scan: dict[str, Any] | None) -> str | None:
    if latest_scan is not None:
        summary = latest_scan.get("summary") or {}
        if isinstance(summary, dict):
            pack_name = summary.get("pack")
            if isinstance(pack_name, str) and pack_name.strip():
                return pack_name.strip()
        pack_name = latest_scan.get("pack")
        if isinstance(pack_name, str) and pack_name.strip():
            return pack_name.strip()
    return None


def _configured_pack(config: dict[str, Any]) -> str | None:
    scan = config.get("scan")
    if isinstance(scan, dict):
        value = scan.get("default_pack")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _read_nested(mapping: dict[str, Any], *keys: str) -> Any:
    current: Any = mapping
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current
