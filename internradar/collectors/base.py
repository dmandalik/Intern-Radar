"""Collector interfaces and collection helpers."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from internradar.core.config import AppConfig
from internradar.core.errors import CollectorError, collector_error_from_exception
from internradar.core.models import Company, RawJob


class BaseCollector(Protocol):
    source_type: str

    def can_collect(self, company: Company) -> bool:
        ...

    def collect(self, company: Company, config: AppConfig) -> list[RawJob]:
        ...


def collect_for_company(
    company: Company,
    collectors: Iterable[BaseCollector],
    config: AppConfig,
) -> tuple[list[RawJob], list[CollectorError]]:
    """Run collectors fault-tolerantly for a company."""
    jobs: list[RawJob] = []
    errors: list[CollectorError] = []
    seen_sources: set[str] = set()

    for collector in collectors:
        source_type = collector.source_type
        if source_type in seen_sources:
            continue
        seen_sources.add(source_type)

        if not collector.can_collect(company):
            continue

        try:
            raw_jobs = collector.collect(company, config)
            jobs.extend(_coerce_raw_jobs(raw_jobs))
        except Exception as exc:  # noqa: BLE001
            errors.append(collector_error_from_exception(company, source_type, exc))

    return jobs, errors


def _coerce_raw_jobs(raw_jobs: Iterable[RawJob]) -> list[RawJob]:
    return [
        raw_job if isinstance(raw_job, RawJob) else RawJob.model_validate(raw_job)
        for raw_job in raw_jobs
    ]


__all__ = ["BaseCollector", "collect_for_company"]
