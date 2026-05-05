from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path

from typer.testing import CliRunner

from internradar.cli import app
from internradar.core.database import initialize_database

PLACEHOLDER_COMMAND_NAMES = ("config",)


class TestCli(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = CliRunner()

    def test_root_help_lists_expected_commands(self) -> None:
        result = self.runner.invoke(app, ["--help"])

        self.assertEqual(result.exit_code, 0)
        for command in ("init", "firms", "export", "dashboard", *PLACEHOLDER_COMMAND_NAMES):
            self.assertIn(command, result.stdout)

    def test_placeholder_commands_run(self) -> None:
        for command_name in PLACEHOLDER_COMMAND_NAMES:
            with self.subTest(command_name=command_name):
                result = self.runner.invoke(app, [command_name])

                self.assertEqual(result.exit_code, 0)
                self.assertIn(
                    f"`{command_name}` is not implemented yet.",
                    result.stdout,
                )

    def test_review_command_runs_with_empty_queue(self) -> None:
        with self.runner.isolated_filesystem():
            initialize_database()
            result = self.runner.invoke(app, ["review"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("No jobs currently need review.", result.stdout)

    def test_init_creates_local_config_and_database(self) -> None:
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(app, ["init"])

            self.assertEqual(result.exit_code, 0)

            app_dir = Path(".internradar")
            config_path = app_dir / "config.yaml"
            database_path = app_dir / "internradar.sqlite3"

            self.assertTrue(config_path.exists())
            self.assertTrue(database_path.exists())
            self.assertIn("Created config:", result.stdout)
            self.assertIn("Created database:", result.stdout)

            with sqlite3.connect(database_path) as connection:
                table_names = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'",
                    )
                }

            self.assertTrue(
                {"scan_runs", "companies", "jobs", "user_actions", "job_snapshots"}
                <= table_names,
            )
