"""Raw collection scan command and pipeline wiring."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import typer

from internradar.collectors.base import BaseCollector, collect_for_company
from internradar.collectors.registry import CollectorRegistry
from internradar.core.config import AppConfig, load_config
from internradar.core.database import record_scan_run
from internradar.core.errors import CollectorError, DatabaseError
from internradar.core.models import Company
from internradar.core.pack_loader import (
    PackLoaderError,
    PackValidationError,
    load_pack_firms,
)
from internradar.core.paths import local_database_path

DEFAULT_PACK_NAME = "quant_engineering"


class ScanCommandError(Exception):
    """Raised when a scan cannot be planned or started."""


@dataclass(slots=True)
class CompanyScanPlan:
    company: Company
    collectors: list[str] = field(default_factory=list)


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
    jobs_by_source: dict[str, int] = field(default_factory=dict)
    errors: list[CollectorError] = field(default_factory=list)
    skipped_no_collector: list[str] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    persisted: bool = False
    database_path: Path | None = None
    persistence_warning: str | None = None


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
    """Run the raw collection scan pipeline."""
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
    except (PackLoaderError, PackValidationError, ScanCommandError) as exc:
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
    """Plan and optionally execute a raw collection scan."""
    del verbose  # Rendering decides how much to print; the pipeline always records details.

    config = load_config()
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
        summary.completed_at = datetime.now(timezone.utc)
        return summary

    job_counter: Counter[str] = Counter()
    for plan in plans:
        if not plan.collectors:
            summary.skipped_no_collector.append(plan.company.name)
            continue

        summary.sources_attempted += len(plan.collectors)
        jobs, errors = collect_for_company(
            company=plan.company,
            collectors=_collectors_for_plan(plan, registry),
            config=config,
        )
        summary.raw_jobs_found += len(jobs)
        summary.errors.extend(errors)
        for raw_job in jobs:
            job_counter[raw_job.source_type] += 1

    summary.jobs_by_source = dict(sorted(job_counter.items(), key=lambda item: item[0].casefold()))
    summary.completed_at = datetime.now(timezone.utc)
    _persist_scan_summary(summary)
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


def _persist_scan_summary(summary: ScanSummary) -> None:
    database_path = local_database_path()
    if not database_path.exists():
        summary.persistence_warning = (
            "Local database not initialized; run `internradar init` to persist scan summaries."
        )
        return

    record_scan_run(
        started_at=summary.started_at,
        completed_at=summary.completed_at or datetime.now(timezone.utc),
        status="completed_with_errors" if summary.errors else "completed",
        trigger=f"scan:{summary.pack_name}",
        notes={
            "pack": summary.pack_name,
            "firms_loaded": summary.firms_loaded,
            "firms_selected": summary.firms_selected,
            "sources_attempted": summary.sources_attempted,
            "raw_jobs_found": summary.raw_jobs_found,
            "collector_errors": len(summary.errors),
            "jobs_by_source": summary.jobs_by_source,
        },
    )
    summary.persisted = True
    summary.database_path = database_path


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
    typer.echo(f"Raw jobs found: {summary.raw_jobs_found}")
    typer.echo(f"Collector errors: {len(summary.errors)}")
    if summary.skipped_no_collector:
        typer.echo(f"Firms without collectors: {len(summary.skipped_no_collector)}")

    if summary.jobs_by_source:
        typer.echo("")
        typer.echo("By source:")
        for source_type, count in summary.jobs_by_source.items():
            typer.echo(f"- {source_type}: {count}")

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
        typer.echo(f"Persistence: saved scan summary to {summary.database_path}")

    typer.echo("")
    typer.echo("Next steps:")
    typer.echo("- Normalization/classification will be added in later issues.")


__all__ = ["ScanCommandError", "ScanSummary", "build_registry", "run_scan", "scan"]
