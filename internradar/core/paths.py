"""Filesystem path helpers for local Intern Radar state."""

from __future__ import annotations

from pathlib import Path

APP_DIR_NAME = ".internradar"
CONFIG_FILE_NAME = "config.yaml"
DATABASE_FILE_NAME = "internradar.sqlite3"
EXPORTS_DIR_NAME = "exports"
OVERRIDES_FILE_NAME = "overrides.yaml"


def project_root() -> Path:
    """Return the repository root for the current editable install."""
    return Path(__file__).resolve().parents[2]


def default_config_path(root: Path | None = None) -> Path:
    """Return the bundled default preferences file."""
    return (root or project_root()) / "configs" / "default_preferences.yaml"


def local_app_dir(cwd: Path | None = None) -> Path:
    """Return the local app directory inside the active workspace."""
    return (cwd or Path.cwd()) / APP_DIR_NAME


def local_config_path(cwd: Path | None = None) -> Path:
    """Return the workspace-local config file path."""
    return local_app_dir(cwd) / CONFIG_FILE_NAME


def home_app_dir(home: Path | None = None) -> Path:
    """Return the user-level Intern Radar directory."""
    return (home or Path.home()) / APP_DIR_NAME


def home_config_path(home: Path | None = None) -> Path:
    """Return the user-level config file path."""
    return home_app_dir(home) / CONFIG_FILE_NAME


def local_database_path(cwd: Path | None = None) -> Path:
    """Return the workspace-local database path."""
    return local_app_dir(cwd) / DATABASE_FILE_NAME


def local_exports_dir(cwd: Path | None = None) -> Path:
    """Return the workspace-local export directory."""
    return local_app_dir(cwd) / EXPORTS_DIR_NAME


def local_overrides_path(cwd: Path | None = None) -> Path:
    """Return the workspace-local manual overrides file path."""
    return local_app_dir(cwd) / OVERRIDES_FILE_NAME
