from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from internradar.core.pack_loader import load_pack_source_queries


class TestSourceQueries(unittest.TestCase):
    def test_source_queries_yaml_loads(self) -> None:
        payload = load_pack_source_queries("quant_engineering")

        self.assertIn("source_queries", payload)
        queries = payload["source_queries"]
        self.assertIn("role_terms", queries)
        self.assertIn("season_terms", queries)
        self.assertIn("domain_terms", queries)
        self.assertIn("hidden_gem_terms", queries)
        self.assertIn("location_terms", queries)
        self.assertIn("query_templates", queries)
        self.assertTrue(queries["role_terms"])
        self.assertTrue(queries["season_terms"])

    def test_fixture_queries_file_can_be_loaded(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            pack_dir = root / "packs" / "fixture"
            pack_dir.mkdir(parents=True)
            (pack_dir / "source_queries.yaml").write_text(
                """
source_queries:
  role_terms:
    - Software Engineer Intern
  season_terms:
    - Summer 2027
  domain_terms:
    greenhouse: site:greenhouse.io
  hidden_gem_terms:
    - trading
  location_terms:
    - New York
  query_templates:
    default:
      - '"{season}" "{role}"'
""".strip(),
                encoding="utf-8",
            )

            payload = load_pack_source_queries("fixture", root=root)

        self.assertEqual(payload["source_queries"]["role_terms"], ["Software Engineer Intern"])
