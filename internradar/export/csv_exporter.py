"""CSV export support."""

from __future__ import annotations

import csv
from pathlib import Path

from internradar.export import ExportJobView


def export_csv(records: list[ExportJobView], output_path: Path) -> Path:
    """Write UTF-8 CSV export."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = [record.as_flat_row() for record in records]
    headers = list(rows[0].keys()) if rows else _default_headers()
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return output_path


def _default_headers() -> list[str]:
    return [
        "Rank",
        "Company",
        "Title",
        "Role Family",
        "Role Subtype",
        "Status",
        "Season",
        "Year",
        "Location",
        "Remote Type",
        "Apply URL",
        "Source URL",
        "Prestige Tier",
        "Opportunity Score",
        "Role Fit Score",
        "Technical Depth Score",
        "Eligibility Score",
        "Hidden Gem Score",
        "Freshness Score",
        "First Seen",
        "Last Seen",
        "Last Verified",
        "Application Status",
        "Eligibility Summary",
        "Why Ranked",
        "Notes",
    ]


__all__ = ["export_csv"]
