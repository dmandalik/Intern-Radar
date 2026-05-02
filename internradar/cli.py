"""Command-line interface for Intern Radar."""

from __future__ import annotations

import typer

from internradar.commands.export import export as export_command
from internradar.commands.firms import app as firms_app
from internradar.commands.scan import scan as scan_command
from internradar.core.bootstrap import initialize_local_state

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
    config_path, database_path = initialize_local_state()
    typer.echo(f"Created config: {config_path}")
    typer.echo(f"Created database: {database_path}")


app.command()(scan_command)
app.command()(export_command)


@app.command()
def dashboard() -> None:
    """Launch the local dashboard."""
    _placeholder("dashboard")


@app.command()
def review() -> None:
    """Review internships and manual decisions."""
    _placeholder("review")


@app.command()
def config() -> None:
    """Inspect or update local configuration."""
    _placeholder("config")


app.add_typer(firms_app, name="firms")


def main() -> None:
    """Run the Typer application."""
    app()
