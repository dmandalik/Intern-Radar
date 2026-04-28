from __future__ import annotations

import unittest

from typer.testing import CliRunner

from internradar.cli import app

COMMAND_NAMES = ("init", "scan", "dashboard", "export", "review", "firms", "config")


class TestCli(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = CliRunner()

    def test_root_help_lists_expected_commands(self) -> None:
        result = self.runner.invoke(app, ["--help"])

        self.assertEqual(result.exit_code, 0)
        for command in COMMAND_NAMES:
            self.assertIn(command, result.stdout)

    def test_placeholder_commands_run(self) -> None:
        for command_name in COMMAND_NAMES:
            with self.subTest(command_name=command_name):
                result = self.runner.invoke(app, [command_name])

                self.assertEqual(result.exit_code, 0)
                self.assertIn(
                    f"`{command_name}` is not implemented yet.",
                    result.stdout,
                )
