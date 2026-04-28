from __future__ import annotations

import unittest

from internradar.collectors.base import collect_for_company
from internradar.collectors.registry import CollectorRegistry
from internradar.core.errors import CollectorError, UnsupportedATSError
from internradar.core.models import Company, RawJob


class GreenhouseCollector:
    source_type = "greenhouse"

    def can_collect(self, company: Company) -> bool:
        return company.ats_type == "greenhouse"

    def collect(self, company: Company, config: dict[str, object]) -> list[RawJob]:
        return [
            RawJob(
                source_type=self.source_type,
                source_name="greenhouse",
                company_id=company.id,
                company_name=company.name,
                title="Intern",
                url="https://example.com/jobs/1",
            ),
        ]


class LeverCollector:
    source_type = "lever"

    def can_collect(self, company: Company) -> bool:
        return company.ats_type == "lever"

    def collect(self, company: Company, config: dict[str, object]) -> list[RawJob]:
        return [
            RawJob(
                source_type=self.source_type,
                source_name="lever",
                company_id=company.id,
                company_name=company.name,
                title="Lever Role",
                url="https://example.com/jobs/lever",
            ),
        ]


class CategoryCollector:
    source_type = "custom"

    def can_collect(self, company: Company) -> bool:
        return "low_latency" in company.categories

    def collect(self, company: Company, config: dict[str, object]) -> list[RawJob]:
        return [
            RawJob(
                source_type=self.source_type,
                source_name="custom",
                company_id=company.id,
                company_name=company.name,
                title="Custom Role",
                url="https://example.com/jobs/custom",
            ),
        ]


class FailingCollector:
    source_type = "failing"

    def can_collect(self, company: Company) -> bool:
        return True

    def collect(self, company: Company, config: dict[str, object]) -> list[RawJob]:
        raise UnsupportedATSError("Collector is not supported for this company.")


class DuplicateSourceCollector:
    source_type = "greenhouse"

    def can_collect(self, company: Company) -> bool:
        return True

    def collect(self, company: Company, config: dict[str, object]) -> list[RawJob]:
        return []


class ExplodingCollector:
    source_type = "exploding"

    def can_collect(self, company: Company) -> bool:
        return True

    def collect(self, company: Company, config: dict[str, object]) -> list[RawJob]:
        raise RuntimeError("boom")


class TestCollectorRegistry(unittest.TestCase):
    def test_collector_can_be_registered(self) -> None:
        registry = CollectorRegistry()
        registry.register(GreenhouseCollector())

        self.assertEqual(len(registry.all_collectors()), 1)
        self.assertEqual(registry.all_collectors()[0].source_type, "greenhouse")

    def test_collector_class_can_be_registered(self) -> None:
        registry = CollectorRegistry()
        registry.register(GreenhouseCollector)

        self.assertEqual(len(registry.all_collectors()), 1)
        self.assertIsInstance(registry.all_collectors()[0], GreenhouseCollector)

    def test_registry_returns_matching_collectors_for_company(self) -> None:
        registry = CollectorRegistry([GreenhouseCollector(), CategoryCollector()])
        company = Company(
            id="company-1",
            name="Example",
            ats_type="greenhouse",
            categories=["low_latency"],
        )

        collectors = registry.get_collectors_for_company(company)

        self.assertEqual(
            [collector.source_type for collector in collectors],
            ["greenhouse", "custom"],
        )

    def test_matching_ats_collector_is_selected_for_company(self) -> None:
        registry = CollectorRegistry([CategoryCollector(), GreenhouseCollector()])
        company = Company(id="company-1", name="Example", ats_type="greenhouse")

        collectors = registry.get_collectors_for_company(company)

        self.assertEqual([collector.source_type for collector in collectors], ["greenhouse"])

    def test_nonmatching_collector_is_not_selected(self) -> None:
        registry = CollectorRegistry([LeverCollector()])
        company = Company(id="company-1", name="Example", ats_type="greenhouse")

        collectors = registry.get_collectors_for_company(company)

        self.assertEqual(collectors, [])

    def test_collection_continues_when_collector_raises(self) -> None:
        company = Company(id="company-1", name="Example", ats_type="greenhouse")
        collectors = [FailingCollector(), GreenhouseCollector()]

        jobs, errors = collect_for_company(company, collectors, config={})

        self.assertEqual(len(jobs), 1)
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], CollectorError)
        self.assertEqual(errors[0].error_type, "unsupported_ats")

    def test_multiple_collectors_can_run_for_one_company(self) -> None:
        registry = CollectorRegistry([GreenhouseCollector(), CategoryCollector()])
        company = Company(
            id="company-1",
            name="Example",
            ats_type="greenhouse",
            categories=["low_latency"],
        )

        jobs, errors = registry.collect_for_company(company, config={})

        self.assertEqual(len(jobs), 2)
        self.assertEqual(errors, [])
        self.assertEqual({job.source_type for job in jobs}, {"greenhouse", "custom"})

    def test_duplicate_registration_is_handled_reasonably(self) -> None:
        registry = CollectorRegistry()
        registry.register(GreenhouseCollector())
        registry.register(DuplicateSourceCollector())

        collectors = registry.all_collectors()

        self.assertEqual(len(collectors), 1)
        self.assertEqual(collectors[0].source_type, "greenhouse")

    def test_unknown_exception_becomes_structured_error(self) -> None:
        company = Company(id="company-1", name="Example")

        jobs, errors = collect_for_company(company, [ExplodingCollector()], config={})

        self.assertEqual(jobs, [])
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].error_type, "unknown_error")
        self.assertTrue(errors[0].recoverable)
