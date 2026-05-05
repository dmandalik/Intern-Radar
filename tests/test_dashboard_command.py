from __future__ import annotations

import unittest
from unittest.mock import patch

from typer.testing import CliRunner

from internradar.cli import app


class TestDashboardCommand(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = CliRunner()

    def test_dashboard_command_exists_and_can_be_smoke_tested(self) -> None:
        with patch("internradar.commands.dashboard.launch_dashboard") as launch_dashboard:
            result = self.runner.invoke(app, ["dashboard", "--port", "8765"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Starting Intern Radar dashboard at http://127.0.0.1:8765", result.stdout)
        launch_dashboard.assert_called_once()
