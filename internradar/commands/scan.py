"""Full scan command and normalized job pipeline wiring."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Optional

import typer

from internradar.collectors.base import BaseCollector, collect_for_company
from internradar.collectors.registry import CollectorRegistry
from internradar.core.config import AppConfig, load_config
from internradar.core.database import (
    JobWriteSummary,
    complete_scan_run,
    create_scan_run,
    database_exists,
    load_jobs_by_ids,
    upsert_jobs,
)
from internradar.core.errors import CollectorError, DatabaseError
from internradar.core.models import Company, Job, RawJob
from internradar.core.pack_loader import (
    PackLoaderError,
    PackValidationError,
    load_pack_firms,
)
from internradar.core.paths import local_database_path
from internradar.parsers.eligibility_parser import apply_job_eligibility
from internradar.parsers.job_parser import normalize_raw_job
from internradar.parsers.role_classifier import classify_role
from internradar.review.overrides import (
    AppliedOverrides,
    OverrideError,
    apply_overrides,
    load_overrides,
)
from internradar.review.user_actions import add_job_notes, set_job_action
from internradar.scoring.opportunity_score import score_job
from internradar.verification.duplicate_detector import deduplicate_jobs, find_duplicates
from internradar.verification.status_checker import check_job_status

DEFAULT_PACK_NAME = "quant_engineering"
STATUS_ORDER = [
    "open",
    "likely_open",
    "coming_soon",
    "closed",
    "requires_login",
    "stale",
    "unknown",
]


class ScanCommandError(Exception):
    """Raised when a scan cannot be planned or started."""


@dataclass(slots=True)
class CompanyScanPlan:
    company: Company
    collectors: list[str] = field(default_factory=list)


@dataclass(slots=True)
class NormalizedJobRecord:
    company: Company
    raw_job: RawJob
    job: Job


@dataclass(slots=True)
class ScanSummary:
    pack_name: str
    firms_loaded: int
    firms_selected: int
    dry_run: bool
    available_sources: list[str] = field(default_factory=list)
    plans: list[CompanyScanPlan] = field(default_factory=list)
    sources_attempted: int = 0
    raw_jobs_found: int = 0
    normalized_jobs: int = 0
    deduplicated_jobs: int = 0
    duplicates_merged: int = 0
    jobs_saved: int = 0
    new_jobs: int = 0
    changed_jobs: int = 0
    jobs_by_source: dict[str, int] = field(default_factory=dict)
    status_counts: dict[str, int] = field(default_factory=dict)
    role_family_counts: dict[str, int] = field(default_factory=dict)
    errors: list[CollectorError] = field(default_factory=list)
    skipped_no_collector: list[str] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    persisted: bool = False
    database_path: Path | None = None
    persistence_warning: str | None = None
    scan_run_id: int | None = None


def scan(
    pack: Optional[str] = typer.Option(
        None,
        "--pack",
        help="Pack name to scan. Defaults to config or quant_engineering.",
    ),
    max_firms: Optional[int] = typer.Option(
        None,
        "--max-firms",
        min=1,
        help="Limit the number of selected firms after filtering.",
    ),
    company: Optional[str] = typer.Option(
        None,
        "--company",
        help="Filter companies by name, alias, or ID.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Plan the scan without making requests or collecting jobs.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        help="Show detailed collector errors in the summary.",
    ),
    source: Optional[str] = typer.Option(
        None,
        "--source",
        help="Restrict the scan to a collector source type such as greenhouse.",
    ),
    project_root: Optional[Path] = typer.Option(
        None,
        "--project-root",
        help="Override the project root when resolving packs.",
        hidden=True,
    ),
) -> None:
    """Run the full scan pipeline from raw collection to persistence."""
    try:
        summary = run_scan(
            pack=pack,
            max_firms=max_firms,
            company_query=company,
            dry_run=dry_run,
            verbose=verbose,
            source=source,
            project_root=project_root,
        )
    except (OverrideError, PackLoaderError, PackValidationError, ScanCommandError) as exc:
        typer.echo(f"Error: {exc}")
        raise typer.Exit(1) from exc
    except DatabaseError as exc:
        typer.echo(f"Error: {exc}")
        raise typer.Exit(1) from exc

    if summary.dry_run:
        _render_dry_run(summary)
        return

    _render_scan_summary(summary, verbose=verbose)


def run_scan(
    *,
    pack: str | None,
    max_firms: int | None,
    company_query: str | None,
    dry_run: bool,
    verbose: bool,
    source: str | None,
    project_root: Path | None,
) -> ScanSummary:
    """Plan and optionally execute a scan through normalization and persistence."""
    del verbose

    config = load_config()
    overrides = load_overrides()
    pack_name = _resolve_pack_name(pack, config)
    firms = load_pack_firms(pack_name, root=project_root)
    selected_firms = _select_firms(firms, company_query=company_query, max_firms=max_firms)

    registry = build_registry()
    available_sources = sorted(
        {collector.source_type for collector in registry.all_collectors()},
        key=str.casefold,
    )
    source_filter = _normalize_source_filter(source, available_sources)
    plans = _build_scan_plans(selected_firms, registry, source_filter)

    summary = ScanSummary(
        pack_name=pack_name,
        firms_loaded=len(firms),
        firms_selected=len(selected_firms),
        dry_run=dry_run,
        available_sources=available_sources,
        plans=plans,
    )

    if dry_run:
        summary.completed_at = datetime.now(UTC)
        return summary

    database_path = local_database_path()
    summary.database_path = database_path
    if database_exists():
        summary.scan_run_id = create_scan_run(
            started_at=summary.started_at,
            pack=pack_name,
            trigger=f"scan:{pack_name}",
        )
    else:
        summary.persistence_warning = (
            "Local database not initialized; run `internradar init` to persist jobs and scan history."
        )

    raw_job_counter: Counter[str] = Counter()
    normalized_records: list[NormalizedJobRecord] = []
    for plan in plans:
        if not plan.collectors:
            summary.skipped_no_collector.append(plan.company.name)
            continue

        summary.sources_attempted += len(plan.collectors)
        raw_jobs, errors = collect_for_company(
            company=plan.company,
            collectors=_collectors_for_plan(plan, registry),
            config=config,
        )
        summary.raw_jobs_found += len(raw_jobs)
        summary.errors.extend(errors)
        for raw_job in raw_jobs:
            raw_job_counter[raw_job.source_type] += 1
            normalized_records.append(
                _normalize_record(
                    raw_job=raw_job,
                    company=plan.company,
                    pack_name=pack_name,
                    project_root=project_root,
                ),
            )

    summary.jobs_by_source = dict(sorted(raw_job_counter.items(), key=lambda item: item[0].casefold()))
    summary.normalized_jobs = len(normalized_records)

    deduped_jobs, raw_records_by_id = _deduplicate_records(normalized_records)
    summary.deduplicated_jobs = len(deduped_jobs)
    summary.duplicates_merged = max(0, summary.normalized_jobs - summary.deduplicated_jobs)
    company_by_id = {firm.id: firm for firm in firms}
    applied_overrides_by_job_id: dict[str, AppliedOverrides] = {}
    score_ready_jobs: list[Job] = []
    for job in deduped_jobs:
        company = company_by_id.get(job.company_id, Company(id=job.company_id, name=job.company_name))
        applied = apply_overrides(job, company=company, overrides=overrides)
        company_by_id[job.company_id] = applied.company
        applied_overrides_by_job_id[job.id] = applied
        score_ready_jobs.append(applied.job)

    summary.status_counts = _sorted_counter(
        (job.status.status for job in score_ready_jobs),
        preferred_order=STATUS_ORDER,
    )
    summary.role_family_counts = _sorted_counter(
        (job.role.role_family for job in score_ready_jobs),
        sort_by_count=True,
    )

    existing_jobs: dict[str, Job] = {}
    if summary.scan_run_id is not None:
        existing_jobs = load_jobs_by_ids([job.id for job in score_ready_jobs])

    score_ready_jobs = _reconcile_existing_jobs(score_ready_jobs, existing_jobs)
    deduped_jobs = [
        score_job(
            job,
            company=company_by_id.get(job.company_id),
            config=config,
            pack_name=pack_name,
            root=project_root,
        )
        for job in score_ready_jobs
    ]

    if summary.scan_run_id is not None:
        write_summary = upsert_jobs(
            deduped_jobs,
            raw_records_by_id=raw_records_by_id,
            scan_run_id=summary.scan_run_id,
            existing_jobs=existing_jobs,
        )
        summary.jobs_saved = write_summary.jobs_saved
        summary.new_jobs = write_summary.inserted
        summary.changed_jobs = write_summary.changed
        summary.persisted = True
        _persist_override_actions(applied_overrides_by_job_id)
        complete_scan_run(
            scan_run_id=summary.scan_run_id,
            completed_at=datetime.now(UTC),
            status="completed_with_errors" if summary.errors else "completed",
            summary=_summary_payload(summary),
        )

    summary.completed_at = datetime.now(UTC)
    return summary


def build_registry() -> CollectorRegistry:
    """Build the default collector registry for scans."""
    return CollectorRegistry.with_defaults()


def _resolve_pack_name(pack: str | None, config: AppConfig) -> str:
    if pack and pack.strip():
        return pack.strip()

    scan_config = config.get("scan")
    if isinstance(scan_config, dict):
        configured_pack = scan_config.get("default_pack")
        if isinstance(configured_pack, str) and configured_pack.strip():
            return configured_pack.strip()

    configured_pack = config.get("default_pack")
    if isinstance(configured_pack, str) and configured_pack.strip():
        return configured_pack.strip()

    return DEFAULT_PACK_NAME


def _select_firms(
    firms: list[Company],
    *,
    company_query: str | None,
    max_firms: int | None,
) -> list[Company]:
    selected = firms
    if company_query:
        needle = company_query.strip().casefold()
        selected = [company for company in firms if _company_matches(company, needle)]
        if not selected:
            raise ScanCommandError(
                f"No firms matched company filter '{company_query}'.",
            )

    if max_firms is not None:
        selected = selected[:max_firms]

    return selected


def _company_matches(company: Company, needle: str) -> bool:
    exact_values = [company.id, company.name, *company.aliases]
    if any(value.casefold() == needle for value in exact_values):
        return True

    partial_values = [company.id, company.name, *company.aliases]
    return any(needle in value.casefold() for value in partial_values)


def _normalize_source_filter(
    source: str | None,
    available_sources: list[str],
) -> str | None:
    if source is None:
        return None

    normalized = source.strip().casefold()
    for available_source in available_sources:
        if available_source.casefold() == normalized:
            return available_source

    available = ", ".join(available_sources)
    raise ScanCommandError(
        f"Unknown collector source '{source}'. Available sources: {available}.",
    )


def _build_scan_plans(
    companies: list[Company],
    registry: CollectorRegistry,
    source_filter: str | None,
) -> list[CompanyScanPlan]:
    plans: list[CompanyScanPlan] = []
    for company in companies:
        collectors = registry.get_collectors_for_company(company)
        if source_filter is not None:
            collectors = [
                collector
                for collector in collectors
                if collector.source_type.casefold() == source_filter.casefold()
            ]

        plans.append(
            CompanyScanPlan(
                company=company,
                collectors=[collector.source_type for collector in collectors],
            ),
        )

    return plans


def _collectors_for_plan(
    plan: CompanyScanPlan,
    registry: CollectorRegistry,
) -> list[BaseCollector]:
    allowed_sources = {source.casefold() for source in plan.collectors}
    return [
        collector
        for collector in registry.get_collectors_for_company(plan.company)
        if collector.source_type.casefold() in allowed_sources
    ]


def _normalize_record(
    *,
    raw_job: RawJob,
    company: Company,
    pack_name: str,
    project_root: Path | None,
) -> NormalizedJobRecord:
    job = normalize_raw_job(raw_job, company=company)
    job = job.model_copy(
        update={
            "role": classify_role(
                title=job.title,
                description=job.description,
                department=raw_job.department,
                company_categories=company.categories,
                pack_name=pack_name,
                root=project_root,
            ),
        },
    )
    job = apply_job_eligibility(job)
    status = check_job_status(
        raw_job,
        page_text=raw_job.description_raw,
        source_type=job.source_type,
        listed_in_current_source=True,
    )
    job = job.model_copy(
        update={
            "status": status,
            "last_verified": status.checked_at,
        },
    )
    return NormalizedJobRecord(company=company, raw_job=raw_job, job=job)


def _deduplicate_records(
    records: list[NormalizedJobRecord],
) -> tuple[list[Job], dict[str, Any]]:
    jobs = [record.job for record in records]
    if not jobs:
        return [], {}

    duplicate_groups = find_duplicates(jobs)
    deduped_jobs = deduplicate_jobs(jobs)
    grouped_member_ids: dict[str, set[str]] = {}
    for group in duplicate_groups:
        member_ids = {job.id for job in group.jobs}
        final_job = next((job for job in deduped_jobs if job.id in member_ids), None)
        if final_job is None:
            continue
        grouped_member_ids[final_job.id] = member_ids

    raw_records_by_id: dict[str, Any] = {}
    for job in deduped_jobs:
        member_ids = grouped_member_ids.get(job.id, {job.id})
        matching_records = [record for record in records if record.job.id in member_ids]
        raw_records_by_id[job.id] = {
            "merged_records": len(matching_records),
            "records": [record.raw_job.model_dump(mode="json") for record in matching_records],
        }

    return deduped_jobs, raw_records_by_id


def _reconcile_existing_jobs(
    jobs: list[Job],
    existing_jobs: dict[str, Job],
) -> list[Job]:
    reconciled: list[Job] = []
    for job in jobs:
        existing = existing_jobs.get(job.id)
        if existing is None:
            reconciled.append(job)
            continue
        reconciled.append(
            job.model_copy(
                update={
                    "first_seen": existing.first_seen,
                },
            ),
        )
    return reconciled


def _sorted_counter(
    values: Any,
    *,
    preferred_order: list[str] | None = None,
    sort_by_count: bool = False,
) -> dict[str, int]:
    counter = Counter(value for value in values if value)
    if preferred_order is not None:
        ordered: dict[str, int] = {}
        for key in preferred_order:
            if key in counter:
                ordered[key] = counter.pop(key)
        for key, count in sorted(counter.items(), key=lambda item: item[0].casefold()):
            ordered[key] = count
        return ordered
    if sort_by_count:
        return dict(sorted(counter.items(), key=lambda item: (-item[1], item[0].casefold())))
    return dict(sorted(counter.items(), key=lambda item: item[0].casefold()))


def _summary_payload(summary: ScanSummary) -> dict[str, Any]:
    return {
        "pack": summary.pack_name,
        "firms_loaded": summary.firms_loaded,
        "firms_selected": summary.firms_selected,
        "sources_attempted": summary.sources_attempted,
        "raw_jobs_found": summary.raw_jobs_found,
        "normalized_jobs": summary.normalized_jobs,
        "deduplicated_jobs": summary.deduplicated_jobs,
        "duplicates_merged": summary.duplicates_merged,
        "jobs_saved": summary.jobs_saved,
        "new_jobs": summary.new_jobs,
        "changed_jobs": summary.changed_jobs,
        "collector_errors": len(summary.errors),
        "jobs_by_source": summary.jobs_by_source,
        "status_counts": summary.status_counts,
        "role_family_counts": summary.role_family_counts,
    }


def _persist_override_actions(
    applied_overrides_by_job_id: dict[str, AppliedOverrides],
) -> None:
    for job_id, applied in applied_overrides_by_job_id.items():
        if applied.application_status:
            set_job_action(job_id, action=applied.application_status)
        if applied.notes:
            add_job_notes(job_id, notes=applied.notes)


def _render_dry_run(summary: ScanSummary) -> None:
    typer.echo("Dry run: Intern Radar scan")
    typer.echo("")
    typer.echo(f"Pack: {summary.pack_name}")
    typer.echo(f"Firms loaded: {summary.firms_loaded}")
    typer.echo(f"Firms selected: {summary.firms_selected}")
    typer.echo(
        f"Collectors available: {', '.join(summary.available_sources) if summary.available_sources else 'none'}",
    )
    typer.echo("")
    typer.echo("Would scan:")
    for plan in summary.plans:
        sources = ", ".join(plan.collectors) if plan.collectors else "no matching collectors"
        typer.echo(f"- {plan.company.name}: {sources}")


def _render_scan_summary(summary: ScanSummary, *, verbose: bool) -> None:
    typer.echo("Scan complete.")
    typer.echo("")
    typer.echo(f"Pack: {summary.pack_name}")
    typer.echo(f"Firms checked: {summary.firms_selected}")
    typer.echo(f"Sources attempted: {summary.sources_attempted}")
    typer.echo(f"Raw jobs collected: {summary.raw_jobs_found}")
    typer.echo(f"Normalized jobs: {summary.normalized_jobs}")
    typer.echo(f"Duplicates merged: {summary.duplicates_merged}")
    typer.echo(f"Jobs saved: {summary.jobs_saved}")
    typer.echo(f"Open jobs: {summary.status_counts.get('open', 0)}")
    typer.echo(f"Likely open jobs: {summary.status_counts.get('likely_open', 0)}")
    typer.echo(f"Coming soon jobs: {summary.status_counts.get('coming_soon', 0)}")
    typer.echo(f"Closed jobs: {summary.status_counts.get('closed', 0)}")
    typer.echo(f"Unknown jobs: {summary.status_counts.get('unknown', 0)}")
    typer.echo(f"Collector errors: {len(summary.errors)}")
    if summary.new_jobs or summary.changed_jobs:
        typer.echo(f"New jobs: {summary.new_jobs}")
        typer.echo(f"Changed jobs: {summary.changed_jobs}")
    if summary.skipped_no_collector:
        typer.echo(f"Firms without collectors: {len(summary.skipped_no_collector)}")

    if summary.jobs_by_source:
        typer.echo("")
        typer.echo("By source:")
        for source_type, count in summary.jobs_by_source.items():
            typer.echo(f"- {source_type}: {count}")

    if summary.role_family_counts:
        typer.echo("")
        typer.echo("Top role families:")
        for role_family, count in summary.role_family_counts.items():
            typer.echo(f"- {role_family}: {count}")

    if summary.errors and verbose:
        typer.echo("")
        typer.echo("Errors:")
        for error in summary.errors:
            typer.echo(f"- {error.company_name or error.company_id} / {error.source_type}: {error.message}")
    elif summary.errors:
        typer.echo("")
        typer.echo("Rerun with --verbose to see collector error details.")

    if summary.persistence_warning:
        typer.echo("")
        typer.echo(f"Persistence: {summary.persistence_warning}")
    elif summary.persisted and summary.database_path is not None:
        typer.echo("")
        typer.echo(f"Persistence: saved jobs and scan history to {summary.database_path}")


__all__ = ["ScanCommandError", "ScanSummary", "build_registry", "run_scan", "scan"]
