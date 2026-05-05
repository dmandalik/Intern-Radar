"""Pack-driven manual search discovery query generation."""

from __future__ import annotations

import csv
import json
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from itertools import product
from pathlib import Path
from typing import Any

from internradar.core.pack_loader import load_pack_source_queries

DEFAULT_QUERY_LIMIT = 60
EXHAUSTIVE_QUERY_LIMIT = 250
PLACEHOLDER_PATTERN = re.compile(r"{([a-zA-Z_][a-zA-Z0-9_]*)}")


class SearchDiscoveryError(ValueError):
    """Raised when manual discovery query generation cannot proceed."""


def generate_search_queries(
    *,
    pack_name: str,
    root: Path | None = None,
    season: str | None = None,
    role: str | None = None,
    domain: str | None = None,
    limit: int | None = None,
    exhaustive: bool = False,
) -> list[str]:
    """Generate deduplicated manual search queries from pack configuration."""
    source_queries = load_pack_source_queries(pack_name, root=root)["source_queries"]
    terms = _build_term_lists(
        source_queries,
        season=season,
        role=role,
        domain=domain,
        exhaustive=exhaustive,
    )
    templates = _load_templates(source_queries, exhaustive=exhaustive)

    query_limit = limit if limit is not None else (EXHAUSTIVE_QUERY_LIMIT if exhaustive else DEFAULT_QUERY_LIMIT)
    queries: list[str] = []
    seen: set[str] = set()
    for template in templates:
        placeholders = PLACEHOLDER_PATTERN.findall(template)
        if not placeholders:
            _append_query(template, seen=seen, queries=queries, query_limit=query_limit)
            continue

        values = [terms.get(name, []) for name in placeholders]
        if any(not choices for choices in values):
            continue
        for combination in product(*values):
            rendered = template.format(**dict(zip(placeholders, combination, strict=True)))
            _append_query(rendered, seen=seen, queries=queries, query_limit=query_limit)
            if len(queries) >= query_limit:
                return queries

    return queries


def export_search_queries(
    queries: list[str],
    *,
    output: Path,
    format_name: str,
    pack_name: str,
    filters: Mapping[str, Any],
) -> Path:
    """Export generated queries to text, JSON, or CSV."""
    output.parent.mkdir(parents=True, exist_ok=True)
    normalized = format_name.strip().casefold()
    if normalized == "text":
        output.write_text("\n".join(queries) + ("\n" if queries else ""), encoding="utf-8")
        return output
    if normalized == "json":
        payload = {
            "generated_at": datetime.now(UTC).isoformat(),
            "pack": pack_name,
            "count": len(queries),
            "filters": dict(filters),
            "queries": queries,
        }
        output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return output
    if normalized == "csv":
        with output.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["query"])
            for query in queries:
                writer.writerow([query])
        return output
    raise SearchDiscoveryError(
        f"Unsupported query export format '{format_name}'. Use text, json, or csv.",
    )


def infer_query_export_format(
    *,
    output: Path | None,
    format_name: str | None,
) -> str:
    """Resolve the desired export format from explicit or path-based hints."""
    if format_name:
        return format_name.strip().casefold()
    if output is None:
        return "text"
    suffix = output.suffix.casefold()
    mapping = {
        ".txt": "text",
        ".text": "text",
        ".json": "json",
        ".csv": "csv",
    }
    return mapping.get(suffix, "text")


def _build_term_lists(
    source_queries: Mapping[str, Any],
    *,
    season: str | None,
    role: str | None,
    domain: str | None,
    exhaustive: bool,
) -> dict[str, list[str]]:
    role_terms = _term_list(source_queries, "role_terms")
    season_terms = _term_list(source_queries, "season_terms")
    hidden_terms = _term_list(source_queries, "hidden_gem_terms")
    location_terms = _term_list(source_queries, "location_terms")
    domain_terms = _domain_terms(source_queries)

    selected_roles = _select_terms(role_terms, explicit=role, default_count=(len(role_terms) if exhaustive else 8))
    selected_seasons = _select_terms(season_terms, explicit=season, default_count=(len(season_terms) if exhaustive else 4))
    selected_hidden_terms = hidden_terms if exhaustive else hidden_terms[:8]
    selected_locations = location_terms if exhaustive else location_terms[:5]
    selected_domains = _select_domains(domain_terms, explicit=domain, exhaustive=exhaustive)
    years = _year_terms(selected_seasons)

    return {
        "role": selected_roles,
        "season": selected_seasons,
        "domain_term": selected_domains,
        "hidden_gem_term": selected_hidden_terms,
        "location_term": selected_locations,
        "year": years,
    }


def _load_templates(source_queries: Mapping[str, Any], *, exhaustive: bool) -> list[str]:
    query_templates = source_queries.get("query_templates")
    if isinstance(query_templates, list):
        templates = [item for item in query_templates if isinstance(item, str) and item.strip()]
    elif isinstance(query_templates, Mapping):
        templates = []
        default_templates = query_templates.get("default", [])
        if isinstance(default_templates, list):
            templates.extend(item for item in default_templates if isinstance(item, str) and item.strip())
        if exhaustive:
            extra_templates = query_templates.get("exhaustive", [])
            if isinstance(extra_templates, list):
                templates.extend(item for item in extra_templates if isinstance(item, str) and item.strip())
    else:
        raise SearchDiscoveryError("source_queries.yaml must define query_templates.")

    if not templates:
        raise SearchDiscoveryError("No query templates were configured for manual search discovery.")
    return templates


def _append_query(
    query: str,
    *,
    seen: set[str],
    queries: list[str],
    query_limit: int,
) -> None:
    normalized = " ".join(query.split())
    if not normalized:
        return
    if normalized.casefold() in seen:
        return
    seen.add(normalized.casefold())
    queries.append(normalized)
    if len(queries) > query_limit:
        queries.pop()


def _term_list(source_queries: Mapping[str, Any], key: str) -> list[str]:
    value = source_queries.get(key, [])
    if not isinstance(value, list):
        raise SearchDiscoveryError(f"source_queries.{key} must be a list.")
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _domain_terms(source_queries: Mapping[str, Any]) -> dict[str, str]:
    value = source_queries.get("domain_terms", {})
    if isinstance(value, Mapping):
        return {
            str(key).strip().casefold(): str(item).strip()
            for key, item in value.items()
            if str(key).strip() and isinstance(item, str) and item.strip()
        }
    if isinstance(value, list):
        parsed: dict[str, str] = {}
        for item in value:
            if not isinstance(item, str) or not item.strip():
                continue
            parsed[_domain_key(item)] = item.strip()
        return parsed
    raise SearchDiscoveryError("source_queries.domain_terms must be a mapping or list.")


def _select_terms(terms: list[str], *, explicit: str | None, default_count: int) -> list[str]:
    if explicit and explicit.strip():
        normalized = explicit.strip().casefold()
        matching = [term for term in terms if term.casefold() == normalized]
        if matching:
            return matching
        return [explicit.strip()]
    return terms[:default_count]


def _select_domains(
    domain_terms: Mapping[str, str],
    *,
    explicit: str | None,
    exhaustive: bool,
) -> list[str]:
    if explicit and explicit.strip():
        normalized = explicit.strip().casefold()
        if normalized in domain_terms:
            return [domain_terms[normalized]]
        for key, value in domain_terms.items():
            if value.casefold() == normalized:
                return [value]
            if key.startswith(normalized):
                return [value]
        raise SearchDiscoveryError(
            f"Unknown domain filter '{explicit}'. Available domains: {', '.join(sorted(domain_terms))}.",
        )
    values = list(domain_terms.values())
    return values if exhaustive else values[:5]


def _year_terms(seasons: list[str]) -> list[str]:
    years: list[str] = []
    seen: set[str] = set()
    for season in seasons:
        for year in re.findall(r"\b20\d{2}\b", season):
            if year not in seen:
                seen.add(year)
                years.append(year)
    return years


def _domain_key(value: str) -> str:
    stripped = value.strip().removeprefix("site:")
    host = stripped.split("/", 1)[0]
    host = host.removeprefix("www.")
    return host.split(".", 1)[0].casefold()


__all__ = [
    "DEFAULT_QUERY_LIMIT",
    "EXHAUSTIVE_QUERY_LIMIT",
    "SearchDiscoveryError",
    "export_search_queries",
    "generate_search_queries",
    "infer_query_export_format",
]
