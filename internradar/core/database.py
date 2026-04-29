"""SQLite database initialization for Intern Radar."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from internradar.core.errors import DatabaseError
from internradar.core.paths import local_database_path

SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS scan_runs (
        id INTEGER PRIMARY KEY,
        started_at TEXT NOT NULL,
        completed_at TEXT,
        status TEXT NOT NULL,
        trigger TEXT,
        notes TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS companies (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        website TEXT,
        careers_url TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY,
        company_id INTEGER NOT NULL,
        external_id TEXT,
        title TEXT NOT NULL,
        location TEXT,
        employment_type TEXT,
        source_url TEXT,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (company_id) REFERENCES companies (id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS user_actions (
        id INTEGER PRIMARY KEY,
        job_id INTEGER NOT NULL,
        action_type TEXT NOT NULL,
        action_value TEXT,
        notes TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (job_id) REFERENCES jobs (id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS job_snapshots (
        id INTEGER PRIMARY KEY,
        job_id INTEGER NOT NULL,
        scan_run_id INTEGER,
        payload_json TEXT NOT NULL,
        captured_at TEXT NOT NULL,
        FOREIGN KEY (job_id) REFERENCES jobs (id),
        FOREIGN KEY (scan_run_id) REFERENCES scan_runs (id)
    )
    """,
)


def initialize_database(cwd: Path | None = None) -> Path:
    """Create the local SQLite database file and required tables."""
    database_path = local_database_path(cwd)
    database_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(database_path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        for statement in SCHEMA_STATEMENTS:
            connection.execute(statement)
        connection.commit()
    finally:
        connection.close()

    return database_path


def record_scan_run(
    *,
    started_at: datetime,
    completed_at: datetime,
    status: str,
    trigger: str | None = None,
    notes: dict[str, Any] | None = None,
    cwd: Path | None = None,
) -> int:
    """Persist a scan run summary to the local SQLite database."""
    database_path = local_database_path(cwd)
    if not database_path.exists():
        raise DatabaseError(
            f"Local database was not found at {database_path}. Run `internradar init` first.",
        )

    connection = sqlite3.connect(database_path)
    try:
        cursor = connection.execute(
            """
            INSERT INTO scan_runs (started_at, completed_at, status, trigger, notes)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                started_at.isoformat(),
                completed_at.isoformat(),
                status,
                trigger,
                json.dumps(notes, sort_keys=True) if notes is not None else None,
            ),
        )
        connection.commit()
        return int(cursor.lastrowid)
    finally:
        connection.close()
