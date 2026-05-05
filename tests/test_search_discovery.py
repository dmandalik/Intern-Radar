from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from typer.testing import CliRunner

from internradar.cli import app
from internradar.collectors.search_discovery import export_search_queries, generate_search_queries


class TestSearchDiscovery(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = CliRunner()

    def test_query_generator_produces_expected_direct_queries(self) -> None:
        queries = generate_search_queries(
            pack_name="quant_engineering",
            season="Summer 2027",
            role="Software Engineer Intern",
            limit=40,
        )

        self.assertIn('"Summer 2027" "Software Engineer Intern"', queries)
        self.assertIn('"Summer 2027" "C++" "trading systems" "intern"', queries)

    def test_query_generator_produces_expected_site_queries(self) -> None:
        queries = generate_search_queries(
            pack_name="quant_engineering",
            season="Summer 2027",
            role="Quant Developer Intern",
            domain="greenhouse",
            limit=40,
        )

        self.assertIn('site:greenhouse.io "Summer 2027" "Quant Developer Intern"', queries)

    def test_query_generator_deduplicates(self) -> None:
        queries = generate_search_queries(
            pack_name="quant_engineering",
            season="Summer 2027",
            role="Trading Systems Intern",
            limit=100,
        )

        self.assertEqual(len(queries), len(set(queries)))

    def test_discover_queries_limit_behavior(self) -> None:
        result = self.runner.invoke(
            app,
            ["discover", "queries", "--pack", "quant_engineering", "--limit", "5"],
        )

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Generated 5 query(s)", result.stdout)

    def test_query_export_writes_text_json_and_csv(self) -> None:
        queries = ['"Summer 2027" "Software Engineer Intern"']
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            text_path = export_search_queries(
                queries,
                output=root / "queries.txt",
                format_name="text",
                pack_name="quant_engineering",
                filters={},
            )
            json_path = export_search_queries(
                queries,
                output=root / "queries.json",
                format_name="json",
                pack_name="quant_engineering",
                filters={"season": "Summer 2027"},
            )
            csv_path = export_search_queries(
                queries,
                output=root / "queries.csv",
                format_name="csv",
                pack_name="quant_engineering",
                filters={},
            )

            self.assertEqual(text_path.read_text(encoding="utf-8").strip(), queries[0])
            self.assertEqual(json.loads(json_path.read_text(encoding="utf-8"))["queries"], queries)
            with csv_path.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.reader(handle))

        self.assertEqual(rows[0], ["query"])
        self.assertEqual(rows[1], [queries[0]])

    def test_discover_queries_can_export_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "queries.json"
            result = self.runner.invoke(
                app,
                [
                    "discover",
                    "queries",
                    "--pack",
                    "quant_engineering",
                    "--season",
                    "Summer 2027",
                    "--role",
                    "Software Engineer Intern",
                    "--output",
                    str(output),
                    "--format",
                    "json",
                    "--limit",
                    "10",
                ],
            )
            payload = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(payload["count"], 10)
        self.assertIn("Saved queries:", result.stdout)
