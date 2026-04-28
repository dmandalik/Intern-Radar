"""Command-line interface for Intern Radar."""

from __future__ import annotations

import typer

app = typer.Typer(
    help="Intern Radar command-line interface.",
    no_args_is_help=True,
    add_completion=False,
)


def _placeholder(command_name: str) -> None:
    """Emit a consistent placeholder message for unimplemented commands."""
    typer.echo(f"`{command_name}` is not implemented yet.")


@app.command()
def init() -> None:
    """Initialize local Intern Radar state."""
    _placeholder("init")


@app.command()
def scan() -> None:
    """Scan configured internship sources."""
    _placeholder("scan")


@app.command()
def dashboard() -> None:
    """Launch the local dashboard."""
    _placeholder("dashboard")


@app.command()
def export() -> None:
    """Export collected internship data."""
    _placeholder("export")


@app.command()
def review() -> None:
    """Review internships and manual decisions."""
    _placeholder("review")


@app.command()
def firms() -> None:
    """Inspect firm configuration and coverage."""
    _placeholder("firms")


@app.command()
def config() -> None:
    """Inspect or update local configuration."""
    _placeholder("config")


def main() -> None:
    """Run the Typer application."""
    app()
