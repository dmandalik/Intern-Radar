from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from internradar.core.paths import (
    default_config_path,
    home_app_dir,
    home_config_path,
    local_app_dir,
    local_config_path,
    local_database_path,
    local_exports_dir,
    local_overrides_path,
)


class TestPaths(unittest.TestCase):
    def test_default_config_path_points_to_repo_config(self) -> None:
        path = default_config_path()

        self.assertEqual(path.name, "default_preferences.yaml")
        self.assertEqual(path.parent.name, "configs")
        self.assertTrue(path.exists())

    def test_local_paths_use_workspace_scoped_app_dir(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cwd = Path(temp_dir)

            self.assertEqual(local_app_dir(cwd), cwd / ".internradar")
            self.assertEqual(local_config_path(cwd), cwd / ".internradar" / "config.yaml")
            self.assertEqual(
                local_database_path(cwd),
                cwd / ".internradar" / "internradar.sqlite3",
            )
            self.assertEqual(local_exports_dir(cwd), cwd / ".internradar" / "exports")
            self.assertEqual(
                local_overrides_path(cwd),
                cwd / ".internradar" / "overrides.yaml",
            )

    def test_home_paths_use_user_home_app_dir(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home = Path(temp_dir)

            self.assertEqual(home_app_dir(home), home / ".internradar")
            self.assertEqual(home_config_path(home), home / ".internradar" / "config.yaml")
