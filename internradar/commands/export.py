"""Export command for Intern Radar job reports."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Optional

import typer

from internradar.core.config import load_config
from internradar.core.database import database_exists, load_job_raw_payload, load_jobs, load_user_actions
from internradar.core.errors import DatabaseError
from internradar.core.models import Job
from internradar.core.paths import local_exports_dir
from internradar.export import ExportJobView, FORMAT_EXTENSIONS, default_output_path
from internradar.export.csv_exporter import export_csv
from internradar.export.excel_exporter import export_xlsx
from internradar.export.html_exporter import export_html
from internradar.export.json_exporter import export_json
from internradar.export.markdown_exporter import export_markdown

SUPPORTED_FORMATS = ("csv", "json", "xlsx", "html", "markdown")
DEFAULT_HIDDEN_GEM_THRESHOLD = 70.0


class ExportCommandError(Exception):
    """Raised when export cannot proceed."""


def export(
    format: Optional[str] = typer.Option(
        None,
        "--format",
        help="Export format: csv, json, xlsx, html, or markdown.",
    ),
    all_formats: bool = typer.Option(
        False,
        "--all",
        help="Export all supported formats.",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        help="Output file path, or output directory when used with --all.",
    ),
    status: Optional[str] = typer.Option(
        None,
        "--status",
        help="Restrict export to a status such as open or coming_soon.",
    ),
    hidden_gems: bool = typer.Option(
        False,
        "--hidden-gems",
        help="Only export high hidden-gem opportunities.",
    ),
    saved: bool = typer.Option(
        False,
        "--saved",
        help="Only export jobs marked saved.",
    ),
    applied: bool = typer.Option(
        False,
        "--applied",
        help="Only export jobs marked applied.",
    ),
    limit: Optional[int] = typer.Option(
        None,
        "--limit",
        min=1,
        help="Maximum number of jobs to export after filtering.",
    ),
    sort: str = typer.Option(
        "opportunity_score",
        "--sort",
        help="Sort key such as opportunity_score, hidden_gem_score, freshness_score, or company.",
    ),
    pack: Optional[str] = typer.Option(
        None,
        "--pack",
        help="Pack label to include in the export metadata.",
    ),
    include_closed: bool = typer.Option(
        False,
        "--include-closed",
        help="Include closed jobs in the export set.",
    ),
) -> None:
    """Export filtered job data to one or more report formats."""
    try:
        paths = run_export(
            format_name=format,
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
        )
    except (ExportCommandError, DatabaseError) as exc:
        typer.echo(f"Error: {exc}")
        raise typer.Exit(1) from exc

    for path in paths:
        typer.echo(f"Created export: {path}")


def run_export(
    *,
    format_name: str | None,
    all_formats: bool,
    output: Path | None,
    status: str | None,
    hidden_gems: bool,
    saved: bool,
    applied: bool,
    limit: int | None,
    sort_key: str,
    pack: str | None,
    include_closed: bool,
    cwd: Path | None = None,
) -> list[Path]:
    """Run export pipeline and return created files."""
    if not all_formats and format_name is None:
        raise ExportCommandError("Choose --format or use --all.")

    if all_formats and format_name is not None:
        raise ExportCommandError("Use either --format or --all, not both.")

    if not database_exists(cwd):
        raise ExportCommandError("No local database found. Run `internradar init` and `internradar scan` first.")

    jobs = load_jobs(cwd=cwd)
    if not jobs:
        raise ExportCommandError("No jobs found in the local database. Run `internradar scan` first.")
    jobs = [job for job in jobs if not _is_demo_job(job.id, cwd=cwd)]
    if not jobs:
        raise ExportCommandError("No real jobs found in the local database. Run `internradar scan` first.")

    user_actions = load_user_actions(cwd=cwd)
    records = _build_records(jobs, user_actions)
    filtered_records = _filter_records(
        records,
        status=status,
        hidden_gems=hidden_gems,
        saved=saved,
        applied=applied,
        include_closed=include_closed,
    )
    sorted_records = _sort_records(filtered_records, sort_key=sort_key)
    if limit is not None:
        sorted_records = sorted_records[:limit]
    ranked_records = [
        ExportJobView(
            rank=index,
            job=record.job,
            application_status=record.application_status,
            notes=record.notes,
            saved=record.saved,
            applied=record.applied,
        )
        for index, record in enumerate(sorted_records, start=1)
    ]

    config = load_config(cwd=cwd)
    metadata = _build_metadata(
        ranked_records,
        filters={
            "status": status,
            "hidden_gems": hidden_gems,
            "saved": saved,
            "applied": applied,
            "limit": limit,
            "sort": sort_key,
            "include_closed": include_closed,
        },
        pack=pack,
        config=config,
    )
    target_formats = _resolve_target_formats(format_name=format_name, all_formats=all_formats)
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d_%H-%M-%S")
    output_dir = _resolve_output_dir(output=output, all_formats=all_formats, cwd=cwd)

    created_paths: list[Path] = []
    for target_format in target_formats:
        export_path = _resolve_output_path(
            output=output,
            output_dir=output_dir,
            format_name=target_format,
            timestamp=timestamp,
            all_formats=all_formats,
        )
        _dispatch_export(
            format_name=target_format,
            records=ranked_records,
            output_path=export_path,
            metadata=metadata,
        )
        created_paths.append(export_path)
    return created_paths


def _build_records(
    jobs: list[Job],
    user_actions: dict[str, dict[str, str]],
) -> list[ExportJobView]:
    records: list[ExportJobView] = []
    for job in jobs:
        action_state = user_actions.get(job.id, {})
        application_status = action_state.get("application_status", "")
        saved = _boolish(action_state.get("saved")) or application_status == "saved"
        applied = _boolish(action_state.get("applied")) or application_status == "applied"
        records.append(
            ExportJobView(
                rank=0,
                job=job,
                application_status=application_status,
                notes=action_state.get("notes", ""),
                saved=saved,
                applied=applied,
            ),
        )
    return records


def _is_demo_job(job_id: str, *, cwd: Path | None = None) -> bool:
    raw_payload = load_job_raw_payload(job_id, cwd=cwd)
    return bool(isinstance(raw_payload, dict) and raw_payload.get("artificial_demo_data"))


def _filter_records(
    records: list[ExportJobView],
    *,
    status: str | None,
    hidden_gems: bool,
    saved: bool,
    applied: bool,
    include_closed: bool,
) -> list[ExportJobView]:
    filtered = records
    if not include_closed and status is None and not applied:
        filtered = [record for record in filtered if record.status != "closed"]
    if status is not None:
        needle = status.strip().casefold()
        filtered = [record for record in filtered if record.status.casefold() == needle]
    if hidden_gems:
        filtered = [record for record in filtered if record.job.scores.hidden_gem_score >= DEFAULT_HIDDEN_GEM_THRESHOLD]
    if saved:
        filtered = [record for record in filtered if record.saved]
    if applied:
        filtered = [record for record in filtered if record.applied]
    return filtered


def _sort_records(records: list[ExportJobView], *, sort_key: str) -> list[ExportJobView]:
    normalized = sort_key.strip().casefold()
    if normalized == "company":
        return sorted(records, key=lambda record: (record.company.casefold(), record.title.casefold()))
    if normalized == "title":
        return sorted(records, key=lambda record: (record.title.casefold(), record.company.casefold()))
    if normalized == "last_verified":
        return sorted(records, key=lambda record: record.job.last_verified, reverse=True)

    score_mapping = {
        "opportunity_score": lambda record: record.job.scores.opportunity_score,
        "role_fit_score": lambda record: record.job.scores.role_fit_score,
        "technical_depth_score": lambda record: record.job.scores.technical_depth_score,
        "eligibility_score": lambda record: record.job.scores.eligibility_score,
        "hidden_gem_score": lambda record: record.job.scores.hidden_gem_score,
        "freshness_score": lambda record: record.job.scores.freshness_score,
        "prestige_score": lambda record: record.job.scores.prestige_score,
    }
    sort_func = score_mapping.get(normalized)
    if sort_func is None:
        raise ExportCommandError(f"Unsupported sort key '{sort_key}'.")
    return sorted(
        records,
        key=lambda record: (sort_func(record), record.company.casefold(), record.title.casefold()),
        reverse=True,
    )


def _build_metadata(
    records: list[ExportJobView],
    *,
    filters: dict[str, Any],
    pack: str | None,
    config: dict[str, Any],
) -> dict[str, Any]:
    status_counts = Counter(record.status for record in records)
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "count": len(records),
        "filters": filters,
        "pack": pack or _configured_pack(config),
        "version": "0.1.0",
        "summary": {
            "open": status_counts.get("open", 0),
            "likely_open": status_counts.get("likely_open", 0),
            "coming_soon": status_counts.get("coming_soon", 0),
            "closed": status_counts.get("closed", 0),
            "hidden_gems": sum(1 for record in records if record.job.scores.hidden_gem_score >= DEFAULT_HIDDEN_GEM_THRESHOLD),
            "saved": sum(1 for record in records if record.saved),
            "applied": sum(1 for record in records if record.applied),
            "review_needed": sum(
                1
                for record in records
                if record.status in {"unknown", "requires_login"} or record.job.eligibility.confidence == 0.0
            ),
        },
    }


def _configured_pack(config: dict[str, Any]) -> str | None:
    scan = config.get("scan")
    if isinstance(scan, dict):
        value = scan.get("default_pack")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _resolve_target_formats(*, format_name: str | None, all_formats: bool) -> list[str]:
    if all_formats:
        return list(SUPPORTED_FORMATS)
    assert format_name is not None
    normalized = format_name.strip().casefold()
    for supported in SUPPORTED_FORMATS:
        if supported.casefold() == normalized:
            return [supported]
    raise ExportCommandError(f"Unsupported export format '{format_name}'.")


def _resolve_output_dir(*, output: Path | None, all_formats: bool, cwd: Path | None) -> Path:
    if output is not None and all_formats:
        return output if output.suffix == "" else output.parent
    if output is None:
        base_dir = local_exports_dir(cwd)
        base_dir.mkdir(parents=True, exist_ok=True)
        return base_dir
    return output.parent


def _resolve_output_path(
    *,
    output: Path | None,
    output_dir: Path,
    format_name: str,
    timestamp: str,
    all_formats: bool,
) -> Path:
    if output is None or all_formats:
        output_dir.mkdir(parents=True, exist_ok=True)
        return default_output_path(base_dir=output_dir, format_name=format_name, timestamp=timestamp)

    if output.suffix:
        return output
    output.mkdir(parents=True, exist_ok=True)
    return default_output_path(base_dir=output, format_name=format_name, timestamp=timestamp)


def _dispatch_export(
    *,
    format_name: str,
    records: list[ExportJobView],
    output_path: Path,
    metadata: dict[str, Any],
) -> None:
    if format_name == "csv":
        export_csv(records, output_path)
        return
    if format_name == "json":
        export_json(records, output_path, metadata=metadata)
        return
    if format_name == "xlsx":
        export_xlsx(records, output_path, metadata=metadata)
        return
    if format_name == "html":
        export_html(records, output_path, metadata=metadata)
        return
    if format_name == "markdown":
        export_markdown(records, output_path, metadata=metadata)
        return
    raise ExportCommandError(f"Unsupported export format '{format_name}'.")


def _boolish(value: str | None) -> bool:
    if value is None:
        return False
    return value.casefold() in {"1", "true", "yes", "saved", "applied"}


__all__ = ["ExportCommandError", "run_export", "export"]
