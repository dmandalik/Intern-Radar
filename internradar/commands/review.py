"""Terminal manual review workflow for uncertain or high-signal jobs."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from internradar.core.errors import DatabaseError
from internradar.dashboard.backend import ensure_dashboard_database, load_dashboard_jobs
from internradar.review.manual_review import ReviewItem, build_review_queue
from internradar.review.user_actions import add_job_notes, set_job_action


def review(
    limit: Optional[int] = typer.Option(
        None,
        "--limit",
        min=1,
        help="Maximum number of review items to show.",
    ),
    status: Optional[str] = typer.Option(
        None,
        "--status",
        help="Restrict the review queue to one job status.",
    ),
    hidden_gems: bool = typer.Option(
        False,
        "--hidden-gems",
        help="Only show strong hidden-gem signals in the queue.",
    ),
    low_confidence: bool = typer.Option(
        False,
        "--low-confidence",
        help="Only show low-confidence jobs in the queue.",
    ),
    all_jobs: bool = typer.Option(
        False,
        "--all",
        help="Review all unreviewed jobs, not only flagged jobs.",
    ),
    project_root: Optional[Path] = typer.Option(
        None,
        "--project-root",
        hidden=True,
        help="Unused compatibility hook for tests.",
    ),
) -> None:
    """Review ambiguous or high-signal jobs one-by-one in the terminal."""
    del project_root
    try:
        ensure_dashboard_database()
        jobs = load_dashboard_jobs()
    except DatabaseError as exc:
        typer.echo(f"Error: {exc}")
        raise typer.Exit(1) from exc

    queue = build_review_queue(
        jobs,
        status=status,
        hidden_gems_only=hidden_gems,
        low_confidence_only=low_confidence,
        include_all=all_jobs,
        limit=limit,
    )
    if not queue:
        typer.echo("No jobs currently need review.")
        return

    typer.echo(f"Manual review queue: {len(queue)} job(s)")
    index = 0
    while index < len(queue):
        item = queue[index]
        _render_item(item, index=index + 1, total=len(queue))
        choice = input("[A]ccept  [E]dit notes  [I]gnore  [S]ave  [P]Applied  [O]pen/print URLs  [N]ext  [Q]uit: ")
        normalized = choice.strip().casefold()[:1] if choice.strip() else "n"

        if normalized == "q":
            typer.echo("Review stopped.")
            return
        if normalized == "o":
            typer.echo(f"Apply URL: {item.apply_url or 'N/A'}")
            typer.echo(f"Source URL: {item.source_url or 'N/A'}")
            continue
        if normalized == "e":
            notes = input("Notes: ").strip()
            add_job_notes(item.job_id, notes=notes)
            typer.echo("Saved notes.")
            index += 1
            continue
        if normalized == "a":
            set_job_action(item.job_id, action="reviewed")
            typer.echo("Marked reviewed.")
            index += 1
            continue
        if normalized == "i":
            set_job_action(item.job_id, action="ignored")
            typer.echo("Marked ignored.")
            index += 1
            continue
        if normalized == "s":
            set_job_action(item.job_id, action="saved")
            typer.echo("Marked saved.")
            index += 1
            continue
        if normalized == "p":
            set_job_action(item.job_id, action="applied")
            typer.echo("Marked applied.")
            index += 1
            continue

        index += 1

    typer.echo("Review complete.")


def _render_item(item: ReviewItem, *, index: int, total: int) -> None:
    typer.echo("")
    typer.echo(f"[{index}/{total}] {item.company} | {item.title}")
    typer.echo(f"Job ID: {item.job_id}")
    typer.echo("Reasons: " + "; ".join(item.reasons))
    typer.echo(
        "Current: "
        f"status={item.current_fields['status']}, "
        f"role={item.current_fields['role_family']} ({item.current_fields['role_confidence']:.2f}), "
        f"eligibility={item.current_fields['eligibility_confidence']:.2f}, "
        f"season={item.current_fields['season'] or 'unknown'}, "
        f"year={item.current_fields['year'] or 'unknown'}, "
        f"opportunity={item.current_fields['opportunity_score']:.0f}, "
        f"hidden_gem={item.current_fields['hidden_gem_score']:.0f}"
    )
    if item.evidence_snippets:
        typer.echo("Evidence:")
        for snippet in item.evidence_snippets:
            typer.echo(f"- {snippet}")
