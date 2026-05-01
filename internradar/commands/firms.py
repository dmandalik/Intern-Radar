"""Firm inspection commands."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

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
