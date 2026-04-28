"""Local initialization helpers for Intern Radar."""

from __future__ import annotations

from pathlib import Path

from internradar.core.config import ensure_local_config
from internradar.core.database import initialize_database
from internradar.core.paths import local_app_dir


def initialize_local_state(cwd: Path | None = None) -> tuple[Path, Path]:
    """Create the local application directory, config, and database."""
    app_dir = local_app_dir(cwd)
    app_dir.mkdir(parents=True, exist_ok=True)
    config_path = ensure_local_config(cwd)
    database_path = initialize_database(cwd)
    return config_path, database_path
