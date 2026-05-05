"""Dashboard command for Intern Radar."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from internradar.dashboard.server import DEFAULT_DASHBOARD_HOST, DEFAULT_DASHBOARD_PORT, dashboard_url, launch_dashboard


class DashboardCommandError(Exception):
    """Raised when the local dashboard cannot be started."""


def dashboard(
    host: str = typer.Option(
        DEFAULT_DASHBOARD_HOST,
        "--host",
        help="Host interface to bind the local dashboard server.",
    ),
    port: int = typer.Option(
        DEFAULT_DASHBOARD_PORT,
        "--port",
        min=1,
        max=65535,
        help="Port to bind the local dashboard server.",
    ),
    open_browser: bool = typer.Option(
        False,
        "--open-browser",
        help="Open the dashboard URL in the default browser.",
    ),
    cwd: Optional[Path] = typer.Option(
        None,
        "--cwd",
        hidden=True,
        help="Override the working directory for tests.",
    ),
) -> None:
    """Launch the local FastAPI and Svelte dashboard."""
    url = dashboard_url(host=host, port=port)
    typer.echo(f"Starting Intern Radar dashboard at {url}")
    try:
        launch_dashboard(host=host, port=port, cwd=cwd, open_browser=open_browser)
    except RuntimeError as exc:
        typer.echo(f"Error: {exc}")
        raise typer.Exit(1) from exc
