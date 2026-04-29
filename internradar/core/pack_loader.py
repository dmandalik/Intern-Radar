"""Domain-pack loading and firm validation."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from internradar.core.models import Company
from internradar.core.paths import project_root

OPTIONAL_WARNING_FIELDS = ("website", "careers_url", "ats_type")


class PackLoaderError(Exception):
    """Base error for pack loading failures."""


class PackValidationError(PackLoaderError):
    """Raised when a pack has structural validation errors."""


@dataclass(slots=True)
class PackDefinition:
    name: str
    root: Path
    path: Path


@dataclass(slots=True)
class FirmValidationReport:
    pack_name: str
    firms: list[Company] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    duplicate_ids: list[str] = field(default_factory=list)
    duplicate_names: list[str] = field(default_factory=list)
    missing_optional_fields: dict[str, int] = field(default_factory=dict)

    @property
    def warning_messages(self) -> list[str]:
        messages: list[str] = []
        for field_name, count in self.missing_optional_fields.items():
            if count:
                messages.append(f"Missing {field_name}: {count}")
        return messages

    @property
    def is_valid(self) -> bool:
        return not (self.errors or self.duplicate_ids or self.duplicate_names)


def load_pack(pack_name: str, root: Path | None = None) -> PackDefinition:
    """Resolve a pack by name from the project packs directory."""
    resolved_root = (root or project_root()).resolve()
    pack_path = resolved_root / "packs" / pack_name
    if not pack_path.is_dir():
        raise PackLoaderError(
            f"Pack '{pack_name}' was not found at {pack_path}.",
        )
    return PackDefinition(name=pack_name, root=resolved_root, path=pack_path)


def load_pack_firms(pack_name: str, root: Path | None = None) -> list[Company]:
    """Load validated firm records for a pack."""
    report = validate_pack_firms(pack_name, root=root)
    if not report.is_valid:
        details = report.errors[:]
        if report.duplicate_ids:
            details.append(f"Duplicate firm IDs: {', '.join(report.duplicate_ids)}")
        if report.duplicate_names:
            details.append(f"Duplicate firm names: {', '.join(report.duplicate_names)}")
        raise PackValidationError("; ".join(details))
    return report.firms


def load_pack_role_keywords(pack_name: str, root: Path | None = None) -> dict[str, Any]:
    """Load role keyword configuration for a pack."""
    pack = load_pack(pack_name, root=root)
    keywords_path = pack.path / "role_keywords.yaml"
    payload = _read_pack_mapping(keywords_path, expected_key="role_keywords")
    role_keywords = payload.get("role_keywords")
    if not isinstance(role_keywords, Mapping):
        raise PackLoaderError(
            f"{keywords_path} must contain a top-level 'role_keywords' mapping.",
        )
    return payload


def validate_pack_firms(pack_name: str, root: Path | None = None) -> FirmValidationReport:
    """Load and validate firm records for a pack."""
    pack = load_pack(pack_name, root=root)
    raw_records = _read_firm_records(pack)
    report = FirmValidationReport(pack_name=pack_name)

    for index, record in enumerate(raw_records, start=1):
        if not isinstance(record, Mapping):
            report.errors.append(
                f"Firm record #{index} in '{pack_name}' must be a mapping.",
            )
            continue

        try:
            company = Company.model_validate(record)
        except ValidationError as exc:
            report.errors.append(
                f"Firm record #{index} failed validation: {exc.errors(include_url=False)}",
            )
            continue

        report.firms.append(company)

    report.duplicate_ids = _find_duplicates(company.id for company in report.firms)
    report.duplicate_names = _find_duplicates(company.name for company in report.firms)
    report.missing_optional_fields = _count_missing_optional_fields(report.firms)
    return report


def search_firms(firms: Iterable[Company], query: str) -> list[Company]:
    """Search firms across ID, name, aliases, and categories."""
    needle = query.strip().casefold()
    if not needle:
        return []

    matches: list[Company] = []
    for company in firms:
        haystacks = [
            company.id,
            company.name,
            *company.aliases,
            *company.categories,
        ]
        if any(needle in value.casefold() for value in haystacks):
            matches.append(company)
    return matches


def _read_firm_records(pack: PackDefinition) -> list[dict[str, Any]]:
    firms_path = pack.path / "firms.yaml"
    payload = _read_pack_mapping(firms_path, expected_key="firms")

    firms = payload.get("firms")
    if not isinstance(firms, list):
        raise PackLoaderError(
            f"{firms_path} must contain a top-level 'firms' list.",
        )

    return firms


def _read_pack_mapping(path: Path, *, expected_key: str) -> Mapping[str, Any]:
    if not path.exists():
        raise PackLoaderError(
            f"Pack file is missing at {path}.",
        )

    try:
        payload = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as exc:
        raise PackLoaderError(
            f"Invalid YAML in {path}: {exc}",
        ) from exc

    if not isinstance(payload, Mapping):
        raise PackLoaderError(
            f"{path} must contain a top-level mapping with a '{expected_key}' key.",
        )

    return payload


def _find_duplicates(values: Iterable[str]) -> list[str]:
    items = list(values)
    counter = Counter(value.casefold() for value in items)
    duplicates = {key for key, count in counter.items() if count > 1}
    if not duplicates:
        return []

    ordered: list[str] = []
    seen: set[str] = set()
    for value in items:
        lowered = value.casefold()
        if lowered in duplicates and lowered not in seen:
            ordered.append(value)
            seen.add(lowered)
    return ordered


def _count_missing_optional_fields(firms: Iterable[Company]) -> dict[str, int]:
    counts = {field_name: 0 for field_name in OPTIONAL_WARNING_FIELDS}
    for company in firms:
        for field_name in OPTIONAL_WARNING_FIELDS:
            value = getattr(company, field_name)
            if value is None or (isinstance(value, str) and not value.strip()):
                counts[field_name] += 1
    return counts
