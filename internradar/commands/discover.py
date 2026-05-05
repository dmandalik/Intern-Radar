"""Manual discovery helpers for search-query generation and public-list imports."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from internradar.collectors.github_lists import compare_imported_jobs_to_known_firms, import_github_list
from internradar.collectors.search_discovery import (
    SearchDiscoveryError,
    export_search_queries,
    generate_search_queries,
    infer_query_export_format,
)
from internradar.core.pack_loader import PackLoaderError, load_pack_firms

app = typer.Typer(
    help="Discovery helpers for manual search generation and public-list imports.",
    no_args_is_help=True,
)


@app.command("queries")
def queries(
    pack: str = typer.Option("quant_engineering", "--pack", help="Pack name for query generation."),
    season: Optional[str] = typer.Option(None, "--season", help="Restrict queries to one season term."),
    role: Optional[str] = typer.Option(None, "--role", help="Restrict queries to one role term."),
    domain: Optional[str] = typer.Option(None, "--domain", help="Restrict queries to one site domain key."),
    limit: Optional[int] = typer.Option(None, "--limit", min=1, help="Cap the number of generated queries."),
    output: Optional[Path] = typer.Option(None, "--output", help="Optional output path for exported queries."),
    format_name: Optional[str] = typer.Option(None, "--format", help="Export format: text, json, or csv."),
    exhaustive: bool = typer.Option(False, "--exhaustive", help="Generate a broader set of queries."),
    project_root: Optional[Path] = typer.Option(None, "--project-root", hidden=True, help="Override pack root."),
) -> None:
    """Generate pack-driven manual search queries."""
    try:
        generated = generate_search_queries(
            pack_name=pack,
            root=project_root,
            season=season,
            role=role,
            domain=domain,
            limit=limit,
            exhaustive=exhaustive,
        )
    except (PackLoaderError, SearchDiscoveryError) as exc:
        typer.echo(f"Error: {exc}")
        raise typer.Exit(1) from exc

    typer.echo(f"Generated {len(generated)} query(s) for pack '{pack}'.")
    for query in generated[: min(10, len(generated))]:
        typer.echo(query)

    if output is not None:
        resolved_format = infer_query_export_format(output=output, format_name=format_name)
        export_search_queries(
            generated,
            output=output,
            format_name=resolved_format,
            pack_name=pack,
            filters={
                "season": season,
                "role": role,
                "domain": domain,
                "limit": limit,
                "exhaustive": exhaustive,
            },
        )
        typer.echo(f"Saved queries: {output}")


@app.command("import-github")
def import_github(
    path: Path = typer.Option(..., "--path", exists=True, dir_okay=False, help="Local markdown internship list."),
    pack: Optional[str] = typer.Option(None, "--pack", help="Optional pack to compare unknown companies against."),
    project_root: Optional[Path] = typer.Option(None, "--project-root", hidden=True, help="Override pack root."),
) -> None:
    """Parse a local GitHub internship-list markdown file and summarize discoveries."""
    try:
        raw_jobs = import_github_list(path)
        typer.echo(f"Imported {len(raw_jobs)} job row(s) from {path}.")
        if pack:
            firms = load_pack_firms(pack, root=project_root)
            comparison = compare_imported_jobs_to_known_firms(raw_jobs, firms)
            typer.echo(f"Unknown companies: {comparison.unknown_company_count}")
            for company_name in comparison.unknown_companies[:10]:
                typer.echo(f"- {company_name}")
    except (OSError, PackLoaderError, SearchDiscoveryError) as exc:
        typer.echo(f"Error: {exc}")
        raise typer.Exit(1) from exc
