from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from internradar.core.pack_loader import (
    PackLoaderError,
    PackValidationError,
    load_pack_firms,
    search_firms,
    validate_pack_firms,
)


class TestPackLoader(unittest.TestCase):
    def test_firms_can_be_loaded_from_temporary_pack(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_pack(
                root,
                "test_pack",
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
""",
            )

            firms = load_pack_firms("test_pack", root=root)

            self.assertEqual(len(firms), 2)
            self.assertEqual(firms[0].id, "hudson-river-trading")
            self.assertEqual(firms[0].aliases, ["HRT"])

    def test_missing_required_fields_are_caught(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_pack(
                root,
                "test_pack",
                """
firms:
  - id: missing-name
    aliases: []
""",
            )

            report = validate_pack_firms("test_pack", root=root)

            self.assertFalse(report.is_valid)
            self.assertTrue(report.errors)

    def test_duplicate_ids_are_caught(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_pack(
                root,
                "test_pack",
                """
firms:
  - id: duplicate-id
    name: Alpha
  - id: duplicate-id
    name: Beta
""",
            )

            report = validate_pack_firms("test_pack", root=root)

            self.assertEqual(report.duplicate_ids, ["duplicate-id"])
            self.assertFalse(report.is_valid)

    def test_duplicate_names_are_caught(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_pack(
                root,
                "test_pack",
                """
firms:
  - id: alpha
    name: Duplicate Name
  - id: beta
    name: Duplicate Name
""",
            )

            report = validate_pack_firms("test_pack", root=root)

            self.assertEqual(report.duplicate_names, ["Duplicate Name"])
            self.assertFalse(report.is_valid)

    def test_alias_search_works(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_pack(
                root,
                "test_pack",
                """
firms:
  - id: hudson-river-trading
    name: Hudson River Trading
    aliases: [HRT]
    categories: [trading_systems]
""",
            )

            firms = load_pack_firms("test_pack", root=root)
            matches = search_firms(firms, "HRT")

            self.assertEqual(len(matches), 1)
            self.assertEqual(matches[0].name, "Hudson River Trading")

    def test_category_search_works(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_pack(
                root,
                "test_pack",
                """
firms:
  - id: hudson-river-trading
    name: Hudson River Trading
    aliases: []
    categories: [low_latency]
""",
            )

            firms = load_pack_firms("test_pack", root=root)
            matches = search_firms(firms, "low_latency")

            self.assertEqual(len(matches), 1)
            self.assertEqual(matches[0].id, "hudson-river-trading")

    def test_missing_optional_fields_only_warn(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_pack(
                root,
                "test_pack",
                """
firms:
  - id: alpha
    name: Alpha
""",
            )

            report = validate_pack_firms("test_pack", root=root)

            self.assertTrue(report.is_valid)
            self.assertGreater(report.missing_optional_fields["careers_url"], 0)
            self.assertGreater(report.missing_optional_fields["ats_type"], 0)

    def test_invalid_yaml_raises_helpful_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            pack_dir = root / "packs" / "test_pack"
            pack_dir.mkdir(parents=True)
            (pack_dir / "firms.yaml").write_text("firms: [\n")

            with self.assertRaises(PackLoaderError):
                validate_pack_firms("test_pack", root=root)

    def test_loading_invalid_pack_raises_validation_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_pack(
                root,
                "test_pack",
                """
firms:
  - id: duplicate-id
    name: Alpha
  - id: duplicate-id
    name: Beta
""",
            )

            with self.assertRaises(PackValidationError):
                load_pack_firms("test_pack", root=root)

    def _write_pack(self, root: Path, pack_name: str, firms_yaml: str) -> None:
        pack_dir = root / "packs" / pack_name
        pack_dir.mkdir(parents=True)
        (pack_dir / "firms.yaml").write_text(firms_yaml.strip() + "\n")
