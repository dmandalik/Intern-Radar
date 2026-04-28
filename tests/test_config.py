from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from internradar.core.config import ensure_local_config, load_config, resolve_user_config_path


class TestConfigLoading(unittest.TestCase):
    def test_loads_default_config_when_no_user_config_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cwd = Path(temp_dir) / "workspace"
            home = Path(temp_dir) / "home"
            cwd.mkdir()
            home.mkdir()

            config = load_config(cwd=cwd, home=home)

            self.assertEqual(config["scan"]["concurrency"], 4)
            self.assertEqual(
                config["storage"]["database_path"],
                ".internradar/internradar.sqlite3",
            )
            self.assertEqual(
                config["output"]["exports_dir"],
                ".internradar/exports",
            )
            self.assertEqual(
                config["review"]["overrides_path"],
                ".internradar/overrides.yaml",
            )

    def test_home_config_overrides_default_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cwd = Path(temp_dir) / "workspace"
            home = Path(temp_dir) / "home"
            cwd.mkdir()
            (home / ".internradar").mkdir(parents=True)
            (home / ".internradar" / "config.yaml").write_text(
                "scan:\n  concurrency: 9\n",
            )

            config = load_config(cwd=cwd, home=home)

            self.assertEqual(config["scan"]["concurrency"], 9)
            self.assertEqual(config["scan"]["timeout_seconds"], 20)

    def test_local_config_overrides_home_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cwd = Path(temp_dir) / "workspace"
            home = Path(temp_dir) / "home"
            cwd.mkdir()
            home.mkdir()
            (home / ".internradar").mkdir()
            (cwd / ".internradar").mkdir()
            (home / ".internradar" / "config.yaml").write_text(
                "scan:\n  concurrency: 9\noutput:\n  exports_dir: home-exports\n",
            )
            (cwd / ".internradar" / "config.yaml").write_text(
                "scan:\n  concurrency: 2\n",
            )

            config = load_config(cwd=cwd, home=home)

            self.assertEqual(config["scan"]["concurrency"], 2)
            self.assertEqual(config["output"]["exports_dir"], "home-exports")

    def test_resolve_user_config_path_prefers_local_then_home(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cwd = Path(temp_dir) / "workspace"
            home = Path(temp_dir) / "home"
            cwd.mkdir()
            home.mkdir()

            self.assertIsNone(resolve_user_config_path(cwd=cwd, home=home))

            (home / ".internradar").mkdir()
            home_config = home / ".internradar" / "config.yaml"
            home_config.write_text("scan:\n  concurrency: 5\n")

            self.assertEqual(resolve_user_config_path(cwd=cwd, home=home), home_config)

            (cwd / ".internradar").mkdir()
            local_config = cwd / ".internradar" / "config.yaml"
            local_config.write_text("scan:\n  concurrency: 3\n")

            self.assertEqual(resolve_user_config_path(cwd=cwd, home=home), local_config)

    def test_ensure_local_config_creates_default_local_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cwd = Path(temp_dir)

            config_path = ensure_local_config(cwd)

            self.assertEqual(config_path, cwd / ".internradar" / "config.yaml")
            self.assertTrue(config_path.exists())
            self.assertIn("concurrency: 4", config_path.read_text())
