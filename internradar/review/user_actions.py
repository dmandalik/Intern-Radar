"""Persistent user action helpers built on top of the local database."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from internradar.core.database import load_user_actions, record_user_action

APPLICATION_STATUSES = {
    "saved",
    "ignored",
    "applied",
    "oa_received",
    "interviewing",
    "rejected",
    "offer",
    "not_interested",
}


def load_action_state(*, cwd: Path | None = None) -> dict[str, dict[str, str]]:
    """Load the latest collapsed user action state keyed by job ID."""
    return load_user_actions(cwd=cwd)


def set_job_action(
    job_id: str,
    *,
    action: str,
    notes: str | None = None,
    cwd: Path | None = None,
) -> dict[str, str]:
    """Persist a user action only when it changes current state."""
    normalized = _normalize_action(action)
    state = load_user_actions(cwd=cwd).get(job_id, {})
    now = datetime.now(UTC)
    wrote_action = False

    if normalized in APPLICATION_STATUSES:
        current = state.get("application_status", "")
        if current != normalized:
            record_user_action(
                job_id,
                action_type="application_status",
                action_value=normalized,
                notes=notes,
                created_at=now,
                updated_at=now,
                cwd=cwd,
            )
            wrote_action = True
    else:
        desired_value = "true"
        current = state.get(normalized, "")
        if current != desired_value:
            record_user_action(
                job_id,
                action_type=normalized,
                action_value=desired_value,
                notes=notes,
                created_at=now,
                updated_at=now,
                cwd=cwd,
            )
            wrote_action = True

    if notes is not None and notes != state.get("notes", "") and not wrote_action:
        record_user_action(
            job_id,
            action_type="notes",
            action_value=notes,
            notes=notes,
            created_at=now,
            updated_at=now,
            cwd=cwd,
        )

    return load_user_actions(cwd=cwd).get(job_id, {})


def add_job_notes(
    job_id: str,
    *,
    notes: str,
    cwd: Path | None = None,
) -> dict[str, str]:
    """Persist free-form notes when they change."""
    current = load_user_actions(cwd=cwd).get(job_id, {})
    if notes != current.get("notes", ""):
        now = datetime.now(UTC)
        record_user_action(
            job_id,
            action_type="notes",
            action_value=notes,
            notes=notes,
            created_at=now,
            updated_at=now,
            cwd=cwd,
        )
    return load_user_actions(cwd=cwd).get(job_id, {})


def _normalize_action(action: str) -> str:
    normalized = action.strip().casefold()
    aliases = {
        "save": "saved",
        "ignore": "ignored",
        "mark_applied": "applied",
        "accept": "reviewed",
        "accepted": "reviewed",
        "mark_reviewed": "reviewed",
    }
    return aliases.get(normalized, normalized)
