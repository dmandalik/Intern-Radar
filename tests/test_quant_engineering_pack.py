from __future__ import annotations

import unittest
from pathlib import Path

import yaml


class TestQuantEngineeringPack(unittest.TestCase):
    def setUp(self) -> None:
        self.pack_dir = Path("packs/quant_engineering")

    def test_pack_files_exist(self) -> None:
        for file_name in (
            "firms.yaml",
            "role_keywords.yaml",
            "prestige_tiers.yaml",
            "source_queries.yaml",
        ):
            with self.subTest(file_name=file_name):
                self.assertTrue((self.pack_dir / file_name).exists())

    def test_firm_list_has_minimum_coverage_and_unique_names(self) -> None:
        firms = yaml.safe_load((self.pack_dir / "firms.yaml").read_text())["firms"]

        self.assertGreaterEqual(len(firms), 50)

        ids = [firm["id"] for firm in firms]
        names = [firm["name"] for firm in firms]

        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(names), len(set(names)))

        for firm in firms:
            self.assertIn("website", firm)
            self.assertIn("careers_url", firm)
            self.assertIn("ats_type", firm)
            self.assertIn("default_prestige_tier", firm)
            self.assertTrue(firm["categories"])

    def test_prestige_tiers_reference_known_firms(self) -> None:
        firms = yaml.safe_load((self.pack_dir / "firms.yaml").read_text())["firms"]
        known_names = {firm["name"] for firm in firms}
        tiers = yaml.safe_load((self.pack_dir / "prestige_tiers.yaml").read_text())["prestige_tiers"]

        referenced = set()
        for names in tiers.values():
            referenced.update(names)

        self.assertTrue(referenced <= known_names)

    def test_role_keywords_and_queries_are_non_empty(self) -> None:
        role_keywords = yaml.safe_load((self.pack_dir / "role_keywords.yaml").read_text())["role_keywords"]
        source_queries = yaml.safe_load((self.pack_dir / "source_queries.yaml").read_text())["source_queries"]

        self.assertTrue(role_keywords)
        self.assertTrue(source_queries)

        for keywords in role_keywords.values():
            self.assertTrue(keywords)

        for queries in source_queries.values():
            self.assertTrue(queries)
