from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from internradar.core.database import initialize_database


class TestDatabaseInitialization(unittest.TestCase):
    def test_initialize_database_creates_file_and_tables(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cwd = Path(temp_dir)

            database_path = initialize_database(cwd)

            self.assertEqual(database_path, cwd / ".internradar" / "internradar.sqlite3")
            self.assertTrue(database_path.exists())

            with sqlite3.connect(database_path) as connection:
                table_names = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'",
                    )
                }

            self.assertEqual(
                table_names & {
                    "scan_runs",
                    "companies",
                    "jobs",
                    "user_actions",
                    "job_snapshots",
                },
                {"scan_runs", "companies", "jobs", "user_actions", "job_snapshots"},
            )

    def test_initialize_database_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cwd = Path(temp_dir)

            first_path = initialize_database(cwd)
            second_path = initialize_database(cwd)

            self.assertEqual(first_path, second_path)
            self.assertTrue(second_path.exists())
