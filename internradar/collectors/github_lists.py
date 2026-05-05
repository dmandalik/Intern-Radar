"""Public GitHub internship-list markdown parsing helpers."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import urlopen

from internradar.core.models import Company, Job, RawJob

TABLE_SEPARATOR_PATTERN = re.compile(r"^\s*\|?(?:\s*:?-{3,}:?\s*\|)+\s*:?-{3,}:?\s*\|?\s*$")
LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


class GitHubListError(ValueError):
    """Raised when markdown internship-list import fails."""


@dataclass(slots=True)
class ImportedListComparison:
    unknown_companies: list[str] = field(default_factory=list)
    unknown_company_jobs: list[RawJob] = field(default_factory=list)
    known_company_count: int = 0
    unknown_company_count: int = 0
    missing_known_jobs: list[RawJob] = field(default_factory=list)


def import_github_list(
    source: str | Path,
    *,
    source_name: str = "GitHub List",
) -> list[RawJob]:
    """Import markdown internship-list rows from a local file path or URL."""
    source_text, source_reference = _load_source_text(source)
    rows = parse_markdown_tables(source_text)
    raw_jobs: list[RawJob] = []
    for row_index, row in enumerate(rows, start=1):
        company_name = _coalesce(row, "company", "company_name") or "Unknown Company"
        title = _coalesce(row, "title", "role", "position") or "Unknown Role"
        apply_url = _extract_url(_coalesce(row, "apply_url", "application", "link", "url"))
        location = _coalesce(row, "location")
        notes = _coalesce(row, "notes", "terms", "summary")
        posted = _coalesce(row, "date_posted", "posted")
        raw_jobs.append(
            RawJob(
                source_type="github_list",
                source_name=source_name,
                company_name=company_name,
                title=title,
                url=apply_url or f"{source_reference}#row-{row_index}",
                apply_url=apply_url,
                location_raw=location,
                description_raw=notes,
                raw_payload={
                    "source_reference": source_reference,
                    "row_index": row_index,
                    "row": row,
                    "date_posted": posted,
                },
            ),
        )
    return raw_jobs


def parse_markdown_tables(markdown_text: str) -> list[dict[str, str]]:
    """Parse likely internship markdown tables into normalized row mappings."""
    lines = markdown_text.splitlines()
    rows: list[dict[str, str]] = []
    index = 0
    while index < len(lines) - 1:
        header_line = lines[index]
        separator_line = lines[index + 1]
        if "|" not in header_line or not TABLE_SEPARATOR_PATTERN.match(separator_line):
            index += 1
            continue

        headers = [_normalize_header(cell) for cell in _split_row(header_line)]
        if not any(headers):
            index += 1
            continue

        index += 2
        while index < len(lines):
            line = lines[index]
            if "|" not in line or not line.strip():
                break
            cells = _split_row(line)
            if len(cells) < len(headers):
                cells.extend([""] * (len(headers) - len(cells)))
            row: dict[str, str] = {}
            for header, value in zip(headers, cells, strict=False):
                if not header:
                    continue
                row[header] = _clean_cell(value, header=header)
            if row:
                rows.append(row)
            index += 1
        index += 1
    return rows


def compare_imported_jobs_to_known_firms(
    raw_jobs: list[RawJob],
    firms: list[Company],
    *,
    known_jobs: list[Job] | None = None,
) -> ImportedListComparison:
    """Identify imported companies absent from the pack and roles absent from direct scans."""
    known_company_tokens = {
        token
        for firm in firms
        for token in {firm.id.casefold(), firm.name.casefold(), *(alias.casefold() for alias in firm.aliases)}
    }
    unknown_jobs: list[RawJob] = []
    unknown_companies: list[str] = []
    seen_companies: set[str] = set()
    for job in raw_jobs:
        normalized_company = job.company_name.casefold().strip()
        if normalized_company in known_company_tokens:
            continue
        unknown_jobs.append(job)
        if normalized_company not in seen_companies:
            unknown_companies.append(job.company_name)
            seen_companies.add(normalized_company)

    missing_known_jobs: list[RawJob] = []
    if known_jobs is not None:
        known_pairs = {
            (job.company_name.casefold().strip(), job.title.casefold().strip())
            for job in known_jobs
        }
        for job in raw_jobs:
            pair = (job.company_name.casefold().strip(), job.title.casefold().strip())
            if pair not in known_pairs:
                missing_known_jobs.append(job)

    return ImportedListComparison(
        unknown_companies=unknown_companies,
        unknown_company_jobs=unknown_jobs,
        known_company_count=len(raw_jobs) - len(unknown_jobs),
        unknown_company_count=len(unknown_companies),
        missing_known_jobs=missing_known_jobs,
    )


def source_visibility_counts(raw_jobs: list[RawJob]) -> dict[str, int]:
    """Count how many imported list rows surface each company/title pair."""
    counter = Counter(
        f"{job.company_name.casefold().strip()}::{job.title.casefold().strip()}"
        for job in raw_jobs
    )
    return dict(counter)


def _load_source_text(source: str | Path) -> tuple[str, str]:
    if isinstance(source, Path):
        return source.read_text(encoding="utf-8"), str(source)
    parsed = urlparse(str(source))
    if parsed.scheme in {"http", "https"}:
        with urlopen(str(source), timeout=10) as response:  # noqa: S310 - optional public URL support only
            return response.read().decode("utf-8"), str(source)
    path = Path(source)
    return path.read_text(encoding="utf-8"), str(path)


def _split_row(line: str) -> list[str]:
    stripped = line.strip().strip("|")
    return [cell.strip() for cell in stripped.split("|")]


def _normalize_header(header: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", header.casefold()).strip("_")
    aliases = {
        "company": "company",
        "company_name": "company",
        "employer": "company",
        "title": "title",
        "role": "title",
        "position": "title",
        "job_title": "title",
        "location": "location",
        "office": "location",
        "application": "apply_url",
        "apply": "apply_url",
        "apply_link": "apply_url",
        "link": "apply_url",
        "url": "apply_url",
        "date": "date_posted",
        "date_posted": "date_posted",
        "posted": "date_posted",
        "notes": "notes",
        "terms": "notes",
        "summary": "notes",
    }
    return aliases.get(normalized, normalized)


def _clean_cell(value: str, *, header: str) -> str:
    match = LINK_PATTERN.search(value)
    if match:
        text, url = match.groups()
        if header == "apply_url":
            return url.strip()
        return text.strip() if text.strip() else url.strip()
    return re.sub(r"\s+", " ", value).strip()


def _extract_url(value: str | None) -> str | None:
    if value is None:
        return None
    match = LINK_PATTERN.search(value)
    if match:
        return match.group(2).strip()
    if value.startswith("http://") or value.startswith("https://"):
        return value.strip()
    return None


def _coalesce(row: dict[str, str], *keys: str) -> str | None:
    for key in keys:
        value = row.get(key)
        if value:
            return value
    return None


__all__ = [
    "GitHubListError",
    "ImportedListComparison",
    "compare_imported_jobs_to_known_firms",
    "import_github_list",
    "parse_markdown_tables",
    "source_visibility_counts",
]
