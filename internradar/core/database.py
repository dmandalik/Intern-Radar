"""SQLite persistence helpers for Intern Radar."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from internradar.core.errors import DatabaseError
from internradar.core.models import ClassifiedRole, EligibilityInfo, Job, JobScores, JobStatusInfo
from internradar.core.paths import local_database_path

SCAN_RUN_COLUMNS: dict[str, str] = {
    "id": "INTEGER PRIMARY KEY",
    "started_at": "TEXT NOT NULL",
    "completed_at": "TEXT",
    "status": "TEXT NOT NULL",
    "trigger": "TEXT",
    "notes": "TEXT",
    "pack": "TEXT",
    "firms_checked": "INTEGER",
    "sources_attempted": "INTEGER",
    "raw_jobs_collected": "INTEGER",
    "normalized_jobs": "INTEGER",
    "duplicates_merged": "INTEGER",
    "jobs_saved": "INTEGER",
    "collector_errors": "INTEGER",
    "summary_json": "TEXT",
}
COMPANIES_COLUMNS: dict[str, str] = {
    "id": "TEXT PRIMARY KEY",
    "name": "TEXT NOT NULL",
    "website": "TEXT",
    "careers_url": "TEXT",
    "created_at": "TEXT NOT NULL",
    "updated_at": "TEXT NOT NULL",
}
JOBS_COLUMNS: dict[str, str] = {
    "id": "TEXT PRIMARY KEY",
    "company_id": "TEXT NOT NULL",
    "company_name": "TEXT NOT NULL",
    "title": "TEXT NOT NULL",
    "description": "TEXT",
    "apply_url": "TEXT NOT NULL",
    "source_url": "TEXT NOT NULL",
    "source_type": "TEXT NOT NULL",
    "role_family": "TEXT NOT NULL",
    "role_subtype": "TEXT",
    "role_confidence": "REAL NOT NULL DEFAULT 0.0",
    "role_evidence_json": "TEXT NOT NULL DEFAULT '[]'",
    "season": "TEXT",
    "year": "INTEGER",
    "locations_json": "TEXT NOT NULL DEFAULT '[]'",
    "remote_type": "TEXT",
    "status": "TEXT NOT NULL",
    "status_confidence": "REAL NOT NULL DEFAULT 0.0",
    "status_evidence_json": "TEXT NOT NULL DEFAULT '[]'",
    "eligibility_json": "TEXT NOT NULL DEFAULT '{}'",
    "scores_json": "TEXT NOT NULL DEFAULT '{}'",
    "prestige_tier": "TEXT",
    "tags_json": "TEXT NOT NULL DEFAULT '[]'",
    "first_seen": "TEXT NOT NULL",
    "last_seen": "TEXT NOT NULL",
    "last_verified": "TEXT NOT NULL",
    "content_hash": "TEXT",
    "raw_json": "TEXT",
    "created_at": "TEXT NOT NULL",
    "updated_at": "TEXT NOT NULL",
}
USER_ACTIONS_COLUMNS: dict[str, str] = {
    "id": "INTEGER PRIMARY KEY",
    "job_id": "TEXT NOT NULL",
    "action_type": "TEXT NOT NULL",
    "action_value": "TEXT",
    "notes": "TEXT",
    "created_at": "TEXT NOT NULL",
    "updated_at": "TEXT NOT NULL",
}
JOB_SNAPSHOTS_COLUMNS: dict[str, str] = {
    "id": "INTEGER PRIMARY KEY",
    "job_id": "TEXT NOT NULL",
    "scan_run_id": "INTEGER",
    "payload_json": "TEXT NOT NULL",
    "captured_at": "TEXT NOT NULL",
}

LEGACY_STATUS_VALUES = {
    "open",
    "likely_open",
    "coming_soon",
    "closed",
    "stale",
    "unknown",
    "requires_login",
}


@dataclass(slots=True)
class JobWriteSummary:
    inserted: int = 0
    updated: int = 0
    changed: int = 0
    snapshots: int = 0

    @property
    def jobs_saved(self) -> int:
        return self.inserted + self.updated


def database_exists(cwd: Path | None = None) -> bool:
    """Return whether the local SQLite database file exists."""
    return local_database_path(cwd).exists()


def initialize_database(cwd: Path | None = None) -> Path:
    """Create the local SQLite database file and required tables."""
    database_path = local_database_path(cwd)
    database_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(database_path)
    try:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        _ensure_schema(connection)
        connection.commit()
    finally:
        connection.close()

    return database_path


def create_scan_run(
    *,
    started_at: datetime,
    pack: str | None,
    trigger: str | None = None,
    cwd: Path | None = None,
) -> int:
    """Create a scan run row and return its identifier."""
    connection = _connect_existing_database(cwd)
    try:
        cursor = connection.execute(
            """
            INSERT INTO scan_runs (started_at, status, trigger, pack)
            VALUES (?, ?, ?, ?)
            """,
            (
                _isoformat(started_at),
                "running",
                trigger,
                pack,
            ),
        )
        connection.commit()
        return int(cursor.lastrowid)
    finally:
        connection.close()


def complete_scan_run(
    *,
    scan_run_id: int,
    completed_at: datetime,
    status: str,
    summary: Mapping[str, Any],
    cwd: Path | None = None,
) -> None:
    """Update a scan run row with completion metadata and summary counts."""
    connection = _connect_existing_database(cwd)
    try:
        connection.execute(
            """
            UPDATE scan_runs
            SET completed_at = ?,
                status = ?,
                notes = ?,
                pack = ?,
                firms_checked = ?,
                sources_attempted = ?,
                raw_jobs_collected = ?,
                normalized_jobs = ?,
                duplicates_merged = ?,
                jobs_saved = ?,
                collector_errors = ?,
                summary_json = ?
            WHERE id = ?
            """,
            (
                _isoformat(completed_at),
                status,
                _json_dumps(summary),
                summary.get("pack"),
                summary.get("firms_selected"),
                summary.get("sources_attempted"),
                summary.get("raw_jobs_found"),
                summary.get("normalized_jobs"),
                summary.get("duplicates_merged"),
                summary.get("jobs_saved"),
                summary.get("collector_errors"),
                _json_dumps(summary),
                scan_run_id,
            ),
        )
        connection.commit()
    finally:
        connection.close()


def record_scan_run(
    *,
    started_at: datetime,
    completed_at: datetime,
    status: str,
    trigger: str | None = None,
    notes: Mapping[str, Any] | None = None,
    cwd: Path | None = None,
) -> int:
    """Persist a completed scan run summary to the local SQLite database."""
    scan_run_id = create_scan_run(
        started_at=started_at,
        pack=_normalize_optional_str((notes or {}).get("pack")),
        trigger=trigger,
        cwd=cwd,
    )
    complete_scan_run(
        scan_run_id=scan_run_id,
        completed_at=completed_at,
        status=status,
        summary=notes or {},
        cwd=cwd,
    )
    return scan_run_id


def load_jobs_by_ids(
    job_ids: list[str],
    *,
    cwd: Path | None = None,
) -> dict[str, Job]:
    """Load existing normalized jobs from the local database by ID."""
    if not job_ids:
        return {}

    connection = _connect_existing_database(cwd)
    try:
        rows = _select_jobs_by_ids(connection, job_ids)
        return {row["id"]: _job_from_row(row) for row in rows}
    finally:
        connection.close()


def load_jobs(
    *,
    cwd: Path | None = None,
) -> list[Job]:
    """Load all normalized jobs from the local database."""
    connection = _connect_existing_database(cwd)
    try:
        rows = list(connection.execute("SELECT * FROM jobs ORDER BY company_name, title"))
        return [_job_from_row(row) for row in rows]
    finally:
        connection.close()


def load_user_actions(
    *,
    cwd: Path | None = None,
) -> dict[str, dict[str, str]]:
    """Load latest user action state keyed by job ID."""
    connection = _connect_existing_database(cwd)
    try:
        rows = list(
            connection.execute(
                """
                SELECT job_id, action_type, action_value, notes, created_at, updated_at
                FROM user_actions
                ORDER BY created_at ASC, id ASC
                """,
            ),
        )
    finally:
        connection.close()

    actions_by_job: dict[str, dict[str, str]] = {}
    for row in rows:
        job_id = str(row["job_id"])
        action_type = _normalize_optional_str(row["action_type"])
        action_value = _normalize_optional_str(row["action_value"])
        notes = _normalize_optional_str(row["notes"])
        created_at = _normalize_optional_str(row["created_at"])
        updated_at = _normalize_optional_str(row["updated_at"]) or created_at

        state = actions_by_job.setdefault(job_id, {})
        if created_at is not None and "created_at" not in state:
            state["created_at"] = created_at
        if action_type == "saved":
            state["saved"] = action_value or "true"
            state["application_status"] = "saved"
        elif action_type == "applied":
            state["applied"] = action_value or "true"
            state["application_status"] = "applied"
        elif action_type == "application_status":
            if action_value is not None:
                state["application_status"] = action_value
                if action_value in {"saved", "applied", "oa_received", "interviewing", "offer", "rejected"}:
                    state["saved"] = "true"
                else:
                    state.pop("saved", None)
                if action_value in {"applied", "oa_received", "interviewing", "offer", "rejected"}:
                    state["applied"] = "true"
                else:
                    state.pop("applied", None)
                if action_value == "ignored":
                    state["ignored"] = "true"
                else:
                    state.pop("ignored", None)
                if action_value == "not_interested":
                    state["not_interested"] = "true"
                else:
                    state.pop("not_interested", None)
        elif action_type == "notes":
            state["notes"] = action_value or notes or ""
        elif action_type is not None:
            state[action_type] = action_value or "true"
        if notes is not None:
            state["notes"] = notes
        if updated_at is not None:
            state["updated_at"] = updated_at
    return actions_by_job


def record_user_action(
    job_id: str,
    *,
    action_type: str,
    action_value: str | None = None,
    notes: str | None = None,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
    cwd: Path | None = None,
) -> None:
    """Persist a user action row for a job."""
    connection = _connect_existing_database(cwd)
    try:
        created = created_at or datetime.now(UTC)
        updated = updated_at or created
        connection.execute(
            """
            INSERT INTO user_actions (job_id, action_type, action_value, notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                action_type,
                action_value,
                notes,
                _isoformat(created),
                _isoformat(updated),
            ),
        )
        connection.commit()
    finally:
        connection.close()


def load_latest_scan_run(
    *,
    cwd: Path | None = None,
) -> dict[str, Any] | None:
    """Load the most recent scan run summary from the local database."""
    connection = _connect_existing_database(cwd)
    try:
        row = connection.execute(
            """
            SELECT id, started_at, completed_at, status, trigger, notes, pack, summary_json
            FROM scan_runs
            ORDER BY id DESC
            LIMIT 1
            """,
        ).fetchone()
    finally:
        connection.close()

    if row is None:
        return None

    summary = _parse_json_mapping(row["summary_json"])
    return {
        "id": int(row["id"]),
        "started_at": row["started_at"],
        "completed_at": row["completed_at"],
        "status": row["status"],
        "trigger": row["trigger"],
        "notes": _parse_json_mapping(row["notes"]),
        "pack": row["pack"],
        "summary": summary,
    }


def load_job_raw_payload(
    job_id: str,
    *,
    cwd: Path | None = None,
) -> dict[str, Any] | None:
    """Load the stored raw payload for a normalized job when available."""
    connection = _connect_existing_database(cwd)
    try:
        row = connection.execute(
            "SELECT raw_json FROM jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
    finally:
        connection.close()

    if row is None:
        return None
    return _parse_json_mapping(row["raw_json"]) or None


def upsert_jobs(
    jobs: list[Job],
    *,
    raw_records_by_id: Mapping[str, Any] | None = None,
    scan_run_id: int | None = None,
    existing_jobs: Mapping[str, Job] | None = None,
    cwd: Path | None = None,
) -> JobWriteSummary:
    """Insert or update normalized jobs and create per-scan snapshots."""
    if not jobs:
        return JobWriteSummary()

    connection = _connect_existing_database(cwd)
    try:
        known_jobs = dict(existing_jobs or {})
        if not known_jobs:
            known_jobs = {row["id"]: _job_from_row(row) for row in _select_jobs_by_ids(connection, [job.id for job in jobs])}

        summary = JobWriteSummary()
        for job in jobs:
            existing = known_jobs.get(job.id)
            raw_record = raw_records_by_id.get(job.id) if raw_records_by_id is not None else None
            if existing is None:
                _insert_job(connection, job, raw_record)
                summary.inserted += 1
            else:
                if _job_has_changed(existing, job):
                    summary.changed += 1
                _update_job(connection, job, raw_record)
                summary.updated += 1

            if scan_run_id is not None:
                _insert_job_snapshot(connection, job=job, scan_run_id=scan_run_id, raw_record=raw_record)
                summary.snapshots += 1

        connection.commit()
        return summary
    finally:
        connection.close()


def _connect_existing_database(cwd: Path | None) -> sqlite3.Connection:
    database_path = local_database_path(cwd)
    if not database_path.exists():
        raise DatabaseError(
            f"Local database was not found at {database_path}. Run `internradar init` first.",
        )

    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    _ensure_schema(connection)
    connection.commit()
    return connection


def _ensure_schema(connection: sqlite3.Connection) -> None:
    _ensure_scan_runs_table(connection)
    _ensure_companies_table(connection)
    _ensure_jobs_table(connection)
    _ensure_user_actions_table(connection)
    _ensure_job_snapshots_table(connection)


def _ensure_scan_runs_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS scan_runs (
            {", ".join(f"{name} {definition}" for name, definition in SCAN_RUN_COLUMNS.items())}
        )
        """,
    )
    _add_missing_columns(connection, "scan_runs", SCAN_RUN_COLUMNS)


def _ensure_companies_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS companies (
            {", ".join(f"{name} {definition}" for name, definition in COMPANIES_COLUMNS.items())}
        )
        """,
    )
    _add_missing_columns(connection, "companies", COMPANIES_COLUMNS)


def _ensure_jobs_table(connection: sqlite3.Connection) -> None:
    if not _table_exists(connection, "jobs"):
        connection.execute(_create_jobs_table_sql())
        return

    existing_columns = _table_columns(connection, "jobs")
    expected_core = {
        "company_name",
        "apply_url",
        "source_type",
        "role_family",
        "locations_json",
        "eligibility_json",
        "raw_json",
    }
    if expected_core.issubset(existing_columns):
        _add_missing_columns(connection, "jobs", JOBS_COLUMNS)
        return

    legacy_rows = list(connection.execute("SELECT * FROM jobs"))
    connection.execute("ALTER TABLE jobs RENAME TO jobs_legacy")
    connection.execute(_create_jobs_table_sql())
    for row in legacy_rows:
        migrated = _migrate_legacy_job_row(row)
        connection.execute(
            f"""
            INSERT INTO jobs ({", ".join(migrated.keys())})
            VALUES ({", ".join("?" for _ in migrated)})
            """,
            tuple(migrated.values()),
        )
    connection.execute("DROP TABLE jobs_legacy")


def _ensure_user_actions_table(connection: sqlite3.Connection) -> None:
    if not _table_exists(connection, "user_actions"):
        connection.execute(
            f"""
            CREATE TABLE user_actions (
                {", ".join(f"{name} {definition}" for name, definition in USER_ACTIONS_COLUMNS.items())},
                FOREIGN KEY (job_id) REFERENCES jobs (id)
            )
            """,
        )
        return
    _add_missing_columns(connection, "user_actions", USER_ACTIONS_COLUMNS)


def _ensure_job_snapshots_table(connection: sqlite3.Connection) -> None:
    if not _table_exists(connection, "job_snapshots"):
        connection.execute(
            f"""
            CREATE TABLE job_snapshots (
                {", ".join(f"{name} {definition}" for name, definition in JOB_SNAPSHOTS_COLUMNS.items())},
                FOREIGN KEY (job_id) REFERENCES jobs (id),
                FOREIGN KEY (scan_run_id) REFERENCES scan_runs (id)
            )
            """,
        )


def _create_jobs_table_sql() -> str:
    return f"""
        CREATE TABLE jobs (
            {", ".join(f"{name} {definition}" for name, definition in JOBS_COLUMNS.items())}
        )
    """


def _add_missing_columns(
    connection: sqlite3.Connection,
    table_name: str,
    expected_columns: Mapping[str, str],
) -> None:
    existing_columns = _table_columns(connection, table_name)
    for column_name, definition in expected_columns.items():
        if column_name in existing_columns:
            continue
        connection.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}",
        )


def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _table_columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
    return {
        str(row["name"])
        for row in connection.execute(f"PRAGMA table_info({table_name})")
    }


def _migrate_legacy_job_row(row: sqlite3.Row) -> dict[str, Any]:
    now = _isoformat(datetime.now(UTC))
    legacy_identifier = _normalize_optional_str(row["external_id"]) or f"legacy-job-{row['id']}"
    status = _normalize_optional_str(row["status"]) or "unknown"
    status = status if status in LEGACY_STATUS_VALUES else "unknown"
    location = _normalize_optional_str(row["location"])
    created_at = _normalize_optional_str(row["created_at"]) or now
    updated_at = _normalize_optional_str(row["updated_at"]) or created_at
    return {
        "id": legacy_identifier,
        "company_id": str(row["company_id"]) if row["company_id"] is not None else "legacy-company",
        "company_name": "Legacy Company",
        "title": row["title"] or "Untitled Job",
        "description": None,
        "apply_url": row["source_url"] or "",
        "source_url": row["source_url"] or "",
        "source_type": "legacy",
        "role_family": "unknown",
        "role_subtype": None,
        "role_confidence": 0.0,
        "role_evidence_json": "[]",
        "season": None,
        "year": None,
        "locations_json": _json_dumps([location] if location else []),
        "remote_type": None,
        "status": status,
        "status_confidence": 0.0,
        "status_evidence_json": "[]",
        "eligibility_json": _json_dumps(EligibilityInfo().model_dump(mode="json")),
        "scores_json": _json_dumps(JobScores().model_dump(mode="json")),
        "prestige_tier": None,
        "tags_json": "[]",
        "first_seen": created_at,
        "last_seen": updated_at,
        "last_verified": updated_at,
        "content_hash": None,
        "raw_json": None,
        "created_at": created_at,
        "updated_at": updated_at,
    }


def _select_jobs_by_ids(connection: sqlite3.Connection, job_ids: list[str]) -> list[sqlite3.Row]:
    placeholders = ", ".join("?" for _ in job_ids)
    return list(
        connection.execute(
            f"SELECT * FROM jobs WHERE id IN ({placeholders})",
            tuple(job_ids),
        ),
    )


def _job_from_row(row: sqlite3.Row) -> Job:
    return Job(
        id=row["id"],
        company_id=row["company_id"],
        company_name=row["company_name"],
        title=row["title"],
        description=row["description"],
        apply_url=row["apply_url"],
        source_url=row["source_url"],
        source_type=row["source_type"],
        role=ClassifiedRole(
            role_family=row["role_family"] or "unknown",
            role_subtype=row["role_subtype"],
            confidence=float(row["role_confidence"] or 0.0),
            evidence=_parse_json_list(row["role_evidence_json"]),
        ),
        season=row["season"],
        year=row["year"],
        locations=_parse_json_list(row["locations_json"]),
        remote_type=row["remote_type"],
        status=JobStatusInfo(
            status=row["status"] or "unknown",
            confidence=float(row["status_confidence"] or 0.0),
            evidence=_parse_json_list(row["status_evidence_json"]),
            checked_at=_parse_datetime(row["last_verified"]),
        ),
        eligibility=EligibilityInfo.model_validate(_parse_json_mapping(row["eligibility_json"])),
        scores=JobScores.model_validate(_parse_json_mapping(row["scores_json"])),
        prestige_tier=row["prestige_tier"],
        tags=_parse_json_list(row["tags_json"]),
        first_seen=_parse_datetime(row["first_seen"]),
        last_seen=_parse_datetime(row["last_seen"]),
        last_verified=_parse_datetime(row["last_verified"]),
        content_hash=row["content_hash"],
    )


def _job_has_changed(existing: Job, updated: Job) -> bool:
    return any(
        (
            existing.content_hash != updated.content_hash,
            existing.status.status != updated.status.status,
            existing.status.confidence != updated.status.confidence,
            existing.role.role_family != updated.role.role_family,
            existing.role.confidence != updated.role.confidence,
            existing.eligibility.model_dump(mode="json") != updated.eligibility.model_dump(mode="json"),
        ),
    )


def _insert_job(
    connection: sqlite3.Connection,
    job: Job,
    raw_record: Any,
) -> None:
    row = _job_row(job, raw_record)
    connection.execute(
        f"""
        INSERT INTO jobs ({", ".join(row.keys())})
        VALUES ({", ".join("?" for _ in row)})
        """,
        tuple(row.values()),
    )


def _update_job(
    connection: sqlite3.Connection,
    job: Job,
    raw_record: Any,
) -> None:
    row = _job_row(job, raw_record)
    assignments = ", ".join(f"{column} = ?" for column in row if column != "id")
    values = [row[column] for column in row if column != "id"]
    values.append(job.id)
    connection.execute(
        f"UPDATE jobs SET {assignments} WHERE id = ?",
        tuple(values),
    )


def _job_row(job: Job, raw_record: Any) -> dict[str, Any]:
    return {
        "id": job.id,
        "company_id": job.company_id,
        "company_name": job.company_name,
        "title": job.title,
        "description": job.description,
        "apply_url": job.apply_url,
        "source_url": job.source_url,
        "source_type": job.source_type,
        "role_family": job.role.role_family,
        "role_subtype": job.role.role_subtype,
        "role_confidence": job.role.confidence,
        "role_evidence_json": _json_dumps(job.role.evidence),
        "season": job.season,
        "year": job.year,
        "locations_json": _json_dumps(job.locations),
        "remote_type": job.remote_type,
        "status": job.status.status,
        "status_confidence": job.status.confidence,
        "status_evidence_json": _json_dumps(job.status.evidence),
        "eligibility_json": _json_dumps(job.eligibility.model_dump(mode="json")),
        "scores_json": _json_dumps(job.scores.model_dump(mode="json")),
        "prestige_tier": job.prestige_tier,
        "tags_json": _json_dumps(job.tags),
        "first_seen": _isoformat(job.first_seen),
        "last_seen": _isoformat(job.last_seen),
        "last_verified": _isoformat(job.last_verified),
        "content_hash": job.content_hash,
        "raw_json": _json_dumps(raw_record) if raw_record is not None else None,
        "created_at": _isoformat(job.first_seen),
        "updated_at": _isoformat(job.last_seen),
    }


def _insert_job_snapshot(
    connection: sqlite3.Connection,
    *,
    job: Job,
    scan_run_id: int,
    raw_record: Any,
) -> None:
    payload = {
        "job": job.model_dump(mode="json"),
        "raw": raw_record,
    }
    connection.execute(
        """
        INSERT INTO job_snapshots (job_id, scan_run_id, payload_json, captured_at)
        VALUES (?, ?, ?, ?)
        """,
        (
            job.id,
            scan_run_id,
            _json_dumps(payload),
            _isoformat(job.last_verified),
        ),
    )


def _json_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True)


def _parse_json_list(raw: Any) -> list[Any]:
    if raw in (None, ""):
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return payload if isinstance(payload, list) else []


def _parse_json_mapping(raw: Any) -> dict[str, Any]:
    if raw in (None, ""):
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _parse_datetime(raw: Any) -> datetime:
    if isinstance(raw, datetime):
        return raw
    if isinstance(raw, str) and raw:
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            pass
    return datetime.now(UTC)


def _isoformat(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat()


def _normalize_optional_str(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


__all__ = [
    "JobWriteSummary",
    "complete_scan_run",
    "create_scan_run",
    "database_exists",
    "initialize_database",
    "load_job_raw_payload",
    "load_jobs",
    "load_jobs_by_ids",
    "load_latest_scan_run",
    "load_user_actions",
    "record_user_action",
    "record_scan_run",
    "upsert_jobs",
]
