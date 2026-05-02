"""JSON export support."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from internradar.export import ExportJobView


def export_json(
    records: list[ExportJobView],
    output_path: Path,
    *,
    metadata: dict[str, Any],
) -> Path:
    """Write JSON export with metadata and full job payloads."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": metadata.get("generated_at"),
        "count": len(records),
        "filters": metadata.get("filters", {}),
        "pack": metadata.get("pack"),
        "version": metadata.get("version", "0.1.0"),
        "jobs": [record.as_json() for record in records],
    }
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return output_path


__all__ = ["export_json"]
