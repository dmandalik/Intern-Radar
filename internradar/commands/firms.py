"""Firm inspection commands."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from internradar.collectors.ats_resolver import ATSResolution, resolve_ats_for_firms
from internradar.core.config import load_config
from internradar.core.models import Company
from internradar.core.pack_loader import (
    PackLoaderError,
    PackValidationError,
    load_pack_firms,
    search_firms,
    validate_pack_firms,
)

app = typer.Typer(
    help="Inspect, search, and validate domain-pack firms.",
    no_args_is_help=True,
    add_completion=False,
)


@app.command("list")
def list_firms(
    pack: str = typer.Option(..., "--pack", help="Pack name to load."),
    project_root: Optional[Path] = typer.Option(
        None,
        "--project-root",
        help="Override the project root when resolving packs.",
        hidden=True,
    ),
) -> None:
    """List firms for a pack."""
    try:
        firms = load_pack_firms(pack, root=project_root)
    except (PackLoaderError, PackValidationError) as exc:
        typer.echo(f"Error: {exc}")
        raise typer.Exit(1) from exc

    _render_firms_table(sorted(firms, key=lambda company: company.name.casefold()))


@app.command()
def search(
    query: str = typer.Argument(..., help="Search term for firm ID, name, alias, or category."),
    pack: str = typer.Option(..., "--pack", help="Pack name to load."),
    project_root: Optional[Path] = typer.Option(
        None,
        "--project-root",
        help="Override the project root when resolving packs.",
        hidden=True,
    ),
) -> None:
    """Search firms for a query."""
    try:
        firms = load_pack_firms(pack, root=project_root)
    except (PackLoaderError, PackValidationError) as exc:
        typer.echo(f"Error: {exc}")
        raise typer.Exit(1) from exc

    matches = search_firms(firms, query)
    if not matches:
        typer.echo(f"No firms matched '{query}'.")
        return

    typer.echo(f"Matches: {len(matches)}")
    _render_firms_table(sorted(matches, key=lambda company: company.name.casefold()))


@app.command()
def validate(
    pack: str = typer.Option(..., "--pack", help="Pack name to load."),
    project_root: Optional[Path] = typer.Option(
        None,
        "--project-root",
        help="Override the project root when resolving packs.",
        hidden=True,
    ),
) -> None:
    """Validate firms for a pack."""
    try:
        report = validate_pack_firms(pack, root=project_root)
    except PackLoaderError as exc:
        typer.echo(f"Validation: failed")
        typer.echo(f"Error: {exc}")
        raise typer.Exit(1) from exc

    typer.echo(f"Firms loaded: {len(report.firms)}")
    typer.echo(f"Duplicate IDs: {len(report.duplicate_ids)}")
    typer.echo(f"Duplicate names: {len(report.duplicate_names)}")
    typer.echo(f"Missing careers URLs: {report.missing_optional_fields.get('careers_url', 0)}")
    typer.echo(f"Missing ATS types: {report.missing_optional_fields.get('ats_type', 0)}")

    if report.errors:
        typer.echo("Errors:")
        for error in report.errors:
            typer.echo(f"- {error}")

    if report.duplicate_ids:
        typer.echo(f"Duplicate ID values: {', '.join(report.duplicate_ids)}")

    if report.duplicate_names:
        typer.echo(f"Duplicate name values: {', '.join(report.duplicate_names)}")

    if report.is_valid:
        typer.echo("Validation: passed")
        return

    typer.echo("Validation: failed")
    raise typer.Exit(1)


@app.command("resolve-ats")
def resolve_ats(
    pack: str = typer.Option(..., "--pack", help="Pack name to load."),
    company: Optional[str] = typer.Option(
        None,
        "--company",
        help="Restrict resolution to firms matching this ID, name, or alias.",
    ),
    only_custom: bool = typer.Option(
        False,
        "--only-custom",
        help="Only probe firms still marked ats_type: custom (or unset).",
    ),
    changed_only: bool = typer.Option(
        False,
        "--changed-only",
        help="Only show firms whose resolved ATS differs from their config.",
    ),
    project_root: Optional[Path] = typer.Option(
        None,
        "--project-root",
        help="Override the project root when resolving packs.",
        hidden=True,
    ),
) -> None:
    """Probe live ATS APIs to discover each firm's real board (read-only)."""
    try:
        firms = load_pack_firms(pack, root=project_root)
    except (PackLoaderError, PackValidationError) as exc:
        typer.echo(f"Error: {exc}")
        raise typer.Exit(1) from exc

    if company:
        firms = search_firms(firms, company)
        if not firms:
            typer.echo(f"No firms matched '{company}'.")
            raise typer.Exit(1)

    if only_custom:
        firms = [
            firm
            for firm in firms
            if not firm.ats_type or firm.ats_type.casefold() == "custom"
        ]

    if not firms:
        typer.echo("No firms to resolve after filtering.")
        return

    config = load_config()
    typer.echo(f"Probing {len(firms)} firm(s) across Greenhouse/Lever/Ashby/Workday...")
    resolutions = resolve_ats_for_firms(
        sorted(firms, key=lambda firm: firm.name.casefold()),
        config,
    )

    if changed_only:
        resolutions = [resolution for resolution in resolutions if resolution.changed]
        if not resolutions:
            typer.echo("No firms changed; configuration matches live ATS boards.")
            return

    _render_resolution_report(resolutions)


def _render_resolution_report(resolutions: list[ATSResolution]) -> None:
    resolved = [resolution for resolution in resolutions if resolution.is_resolved]
    unresolved = [resolution for resolution in resolutions if not resolution.is_resolved]
    changed = [resolution for resolution in resolutions if resolution.changed]

    typer.echo("")
    typer.echo(f"Resolved: {len(resolved)}  Unresolved: {len(unresolved)}  Changed: {len(changed)}")
    typer.echo("")

    for resolution in resolutions:
        if resolution.is_resolved:
            target = _format_resolution_target(resolution)
            marker = "*" if resolution.changed else " "
            count = "" if resolution.job_count is None else f" ({resolution.job_count} jobs)"
            current = resolution.current_ats_type or "custom"
            typer.echo(
                f"{marker} {resolution.company_name}: {current} -> {target}{count}",
            )
        else:
            typer.echo(f"  {resolution.company_name}: unresolved")
        if resolution.notes:
            typer.echo(f"      note: {resolution.notes}")

    if changed:
        typer.echo("")
        typer.echo("Suggested firms.yaml edits (* rows above):")
        for resolution in changed:
            typer.echo(f"- id: {resolution.company_id}")
            typer.echo(f"  ats_type: {resolution.resolved_ats_type}")
            if resolution.resolved_ats_type == "workday":
                typer.echo("  ats_slug: null")
                typer.echo(f"  ats_tenant: {resolution.resolved_tenant}")
                typer.echo(f"  ats_datacenter: {resolution.resolved_datacenter}")
                typer.echo(f"  ats_site: {resolution.resolved_site}")
            else:
                typer.echo(f"  ats_slug: {resolution.resolved_slug}")


def _format_resolution_target(resolution: ATSResolution) -> str:
    if resolution.resolved_ats_type == "workday":
        return (
            f"workday[{resolution.resolved_tenant}/"
            f"{resolution.resolved_datacenter}/{resolution.resolved_site}]"
        )
    return f"{resolution.resolved_ats_type}[{resolution.resolved_slug}]"


def _render_firms_table(firms: list[Company]) -> None:
    headers = ["ID", "Name", "ATS Type", "ATS Slug", "Prestige Tier", "Careers URL"]
    rows = [
        [
            company.id,
            company.name,
            company.ats_type or "",
            company.ats_slug or "",
            company.default_prestige_tier or "",
            company.careers_url or "",
        ]
        for company in firms
    ]

    widths = [
        max(len(header), *(len(row[index]) for row in rows)) if rows else len(header)
        for index, header in enumerate(headers)
    ]

    header_line = "  ".join(header.ljust(widths[index]) for index, header in enumerate(headers))
    separator = "  ".join("-" * width for width in widths)
    typer.echo(header_line)
    typer.echo(separator)
    for row in rows:
        typer.echo("  ".join(value.ljust(widths[index]) for index, value in enumerate(row)))
