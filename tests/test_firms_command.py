from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from typer.testing import CliRunner

from internradar.cli import app


class TestFirmsCommand(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = CliRunner()

    def test_validate_command_succeeds_for_valid_pack(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_pack(root)

            result = self.runner.invoke(
                app,
                [
                    "firms",
                    "validate",
                    "--pack",
                    "test_pack",
                    "--project-root",
                    str(root),
                ],
            )

            self.assertEqual(result.exit_code, 0)
            self.assertIn("Firms loaded: 2", result.stdout)
            self.assertIn("Validation: passed", result.stdout)

    def test_list_command_runs_without_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_pack(root)

            result = self.runner.invoke(
                app,
                [
                    "firms",
                    "list",
                    "--pack",
                    "test_pack",
                    "--project-root",
                    str(root),
                ],
            )

            self.assertEqual(result.exit_code, 0)
            self.assertIn("Hudson River Trading", result.stdout)
            self.assertIn("Citadel", result.stdout)

    def test_search_command_supports_alias_and_category_queries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_pack(root)

            alias_result = self.runner.invoke(
                app,
                [
                    "firms",
                    "search",
                    "HRT",
                    "--pack",
                    "test_pack",
                    "--project-root",
                    str(root),
                ],
            )
            category_result = self.runner.invoke(
                app,
                [
                    "firms",
                    "search",
                    "low_latency",
                    "--pack",
                    "test_pack",
                    "--project-root",
                    str(root),
                ],
            )

            self.assertEqual(alias_result.exit_code, 0)
            self.assertIn("Hudson River Trading", alias_result.stdout)
            self.assertEqual(category_result.exit_code, 0)
            self.assertIn("Hudson River Trading", category_result.stdout)

    def _write_pack(self, root: Path) -> None:
        pack_dir = root / "packs" / "test_pack"
        pack_dir.mkdir(parents=True)
        (pack_dir / "firms.yaml").write_text(
            """
firms:
  - id: hudson-river-trading
    name: Hudson River Trading
    aliases: [HRT]
    website: https://www.hudsonrivertrading.com
    careers_url: https://www.hudsonrivertrading.com/careers/
    ats_type: custom
    ats_slug: null
    categories: [trading_systems, low_latency]
    default_prestige_tier: S+
    locations: [New York]
  - id: citadel
    name: Citadel
    aliases: []
    website: https://www.citadel.com
    careers_url: https://www.citadel.com/careers/
    ats_type: greenhouse
    ats_slug: citadel
    categories: [hedge_fund]
    default_prestige_tier: S
    locations: [Chicago]
""".strip()
            + "\n",
        )
