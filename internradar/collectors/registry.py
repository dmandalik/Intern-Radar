"""Collector registration and selection."""

from __future__ import annotations

from collections.abc import Iterable

from internradar.collectors.base import BaseCollector, collect_for_company
from internradar.core.config import AppConfig
from internradar.core.errors import CollectorError
from internradar.core.models import Company, RawJob


class CollectorRegistry:
    """Registry for collector instances keyed by source type."""

    def __init__(self, collectors: Iterable[BaseCollector] | None = None) -> None:
        self._collectors: dict[str, BaseCollector] = {}
        for collector in collectors or []:
            self.register(collector)

    @classmethod
    def with_defaults(cls) -> CollectorRegistry:
        """Build a registry with the collectors shipped by default."""
        from internradar.collectors.ashby import AshbyCollector
        from internradar.collectors.custom_page import CustomPageCollector
        from internradar.collectors.greenhouse import GreenhouseCollector
        from internradar.collectors.lever import LeverCollector
        from internradar.collectors.workday import WorkdayCollector

        return cls(
            [
                GreenhouseCollector(),
                LeverCollector(),
                AshbyCollector(),
                WorkdayCollector(),
                CustomPageCollector(),
            ],
        )

    def register(self, collector: BaseCollector | type[BaseCollector]) -> BaseCollector:
        """Register a collector instance or zero-argument class."""
        instance = collector() if isinstance(collector, type) else collector
        self._collectors[instance.source_type] = instance
        return instance

    def all_collectors(self) -> list[BaseCollector]:
        return list(self._collectors.values())

    def get_collectors_for_company(self, company: Company) -> list[BaseCollector]:
        """Return matching collectors, preferring the declared ATS collector first."""
        matching = [
            collector
            for collector in self._collectors.values()
            if collector.can_collect(company)
        ]
        if not company.ats_type:
            return matching

        preferred: list[BaseCollector] = []
        fallback: list[BaseCollector] = []
        ats_type = company.ats_type.casefold()

        for collector in matching:
            if collector.source_type.casefold() == ats_type:
                preferred.append(collector)
            else:
                fallback.append(collector)

        return preferred + fallback

    def collect_for_company(
        self,
        company: Company,
        config: AppConfig,
    ) -> tuple[list[RawJob], list[CollectorError]]:
        """Run all eligible collectors for a company with fault tolerance."""
        return collect_for_company(
            company=company,
            collectors=self.get_collectors_for_company(company),
            config=config,
        )


__all__ = ["CollectorRegistry"]
