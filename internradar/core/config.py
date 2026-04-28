"""Configuration loading for Intern Radar."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from internradar.core.paths import default_config_path, home_config_path, local_config_path


def load_config(cwd: Path | None = None, home: Path | None = None) -> dict[str, Any]:
    """Load default config plus optional home and local overrides."""
    config = _read_yaml_mapping(default_config_path())

    home_path = home_config_path(home)
    if home_path.exists():
        config = _deep_merge(config, _read_yaml_mapping(home_path))

    local_path = local_config_path(cwd)
    if local_path.exists():
        config = _deep_merge(config, _read_yaml_mapping(local_path))

    return config


def resolve_user_config_path(cwd: Path | None = None, home: Path | None = None) -> Path | None:
    """Return the highest-precedence user config file that exists."""
    local_path = local_config_path(cwd)
    if local_path.exists():
        return local_path

    home_path = home_config_path(home)
    if home_path.exists():
        return home_path

    return None


def ensure_local_config(cwd: Path | None = None) -> Path:
    """Create the workspace-local config file from defaults if needed."""
    target_path = local_config_path(cwd)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if not target_path.exists():
        target_path.write_text(default_config_path().read_text())
    return target_path


def _read_yaml_mapping(path: Path) -> dict[str, Any]:
    """Read a YAML mapping file from disk."""
    data = yaml.safe_load(path.read_text()) or {}
    if not isinstance(data, Mapping):
        raise ValueError(f"Expected a mapping in config file: {path}")
    return dict(data)


def _deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    """Recursively merge config mappings with override precedence."""
    merged: dict[str, Any] = dict(base)
    for key, value in override.items():
        base_value = merged.get(key)
        if isinstance(base_value, Mapping) and isinstance(value, Mapping):
            merged[key] = _deep_merge(base_value, value)
            continue
        merged[key] = value
    return merged
