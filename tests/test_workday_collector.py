from __future__ import annotations

import unittest

import httpx

from internradar.collectors.base import collect_for_company
from internradar.collectors.registry import CollectorRegistry
from internradar.collectors.workday import WorkdayCollector
from internradar.core.models import Company, RawJob


class TestWorkdayCollector(unittest.TestCase):
    def test_can_collect_returns_true_for_workday_ats_type(self) -> None:
        collector = WorkdayCollector()
        company = Company(id="company-1", name="Example", ats_type="workday")

        self.assertTrue(collector.can_collect(company))

    def test_can_collect_returns_false_for_unrelated_ats_type(self) -> None:
        collector = WorkdayCollector()
        company = Company(id="company-1", name="Example", ats_type="greenhouse")

        self.assertFalse(collector.can_collect(company))

    def test_can_collect_from_myworkdayjobs_careers_url(self) -> None:
        collector = WorkdayCollector()
        company = Company(
            id="company-1",
            name="Example",
            careers_url="https://gresearch.wd103.myworkdayjobs.com/en-US/G-Research",
        )

        self.assertTrue(collector.can_collect(company))

    def test_successful_response_returns_raw_jobs(self) -> None:
        client = self._mock_client(self._page_response(self._postings(0, 1), total=1))
        collector = WorkdayCollector(client=client)
        company = self._workday_company()

        jobs = collector.collect(company, config={})

        self.assertEqual(len(jobs), 1)
        self.assertIsInstance(jobs[0], RawJob)
        self.assertEqual(jobs[0].title, "Intern 0")
        self.assertEqual(
            jobs[0].url,
            "https://gresearch.wd103.myworkdayjobs.com/en-US/G-Research/job/intern-0",
        )
        self.assertEqual(jobs[0].location_raw, "New York")

    def test_coordinates_resolved_from_careers_url(self) -> None:
        client = self._mock_client(self._page_response(self._postings(0, 1), total=1))
        collector = WorkdayCollector(client=client)
        company = Company(
            id="company-1",
            name="Example",
            ats_type="workday",
            careers_url="https://gresearch.wd103.myworkdayjobs.com/en-US/G-Research",
        )

        jobs = collector.collect(company, config={})

        self.assertEqual(len(jobs), 1)

    def test_missing_coordinates_is_structured_error(self) -> None:
        collector = WorkdayCollector()
        company = Company(id="company-1", name="Example", ats_type="workday")

        jobs, errors = collect_for_company(company, [collector], config={})

        self.assertEqual(jobs, [])
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].error_type, "invalid_config")

    def test_pagination_collects_all_jobs_despite_zero_total_on_later_pages(self) -> None:
        # Workday only reports a meaningful ``total`` on the first page; later
        # pages report ``total=0``. The collector must not treat that as the end.
        pages = [
            self._page_response(self._postings(0, 20), total=61),
            self._page_response(self._postings(20, 20), total=0),
            self._page_response(self._postings(40, 20), total=0),
            self._page_response(self._postings(60, 1), total=0),
        ]
        client = self._sequenced_client(pages)
        collector = WorkdayCollector(client=client)
        company = self._workday_company()

        jobs = collector.collect(company, config={})

        self.assertEqual(len(jobs), 61)
        titles = {job.title for job in jobs}
        self.assertEqual(len(titles), 61)

    def test_duplicate_postings_are_deduped(self) -> None:
        duplicated = self._postings(0, 1) + self._postings(0, 1)
        client = self._mock_client(self._page_response(duplicated, total=1))
        collector = WorkdayCollector(client=client)
        company = self._workday_company()

        jobs = collector.collect(company, config={})

        self.assertEqual(len(jobs), 1)

    def test_board_not_found_is_returned_as_structured_error(self) -> None:
        client = self._mock_client(httpx.Response(404, json={"error": "not found"}))
        collector = WorkdayCollector(client=client)
        company = self._workday_company()

        jobs, errors = collect_for_company(company, [collector], config={})

        self.assertEqual(jobs, [])
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].error_type, "invalid_config")

    def test_invalid_json_is_returned_as_structured_error(self) -> None:
        client = self._mock_client(httpx.Response(200, content=b"{not-json"))
        collector = WorkdayCollector(client=client)
        company = self._workday_company()

        jobs, errors = collect_for_company(company, [collector], config={})

        self.assertEqual(jobs, [])
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].error_type, "parse_error")

    def test_rate_limited_is_returned_as_structured_error(self) -> None:
        client = self._mock_client(httpx.Response(429, json={"error": "slow down"}))
        collector = WorkdayCollector(client=client)
        company = self._workday_company()

        jobs, errors = collect_for_company(company, [collector], config={})

        self.assertEqual(jobs, [])
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].error_type, "rate_limited")

    def test_registry_defaults_include_workday_collector(self) -> None:
        registry = CollectorRegistry.with_defaults()

        self.assertIn("workday", [collector.source_type for collector in registry.all_collectors()])

    def test_uses_post_to_cxs_jobs_endpoint(self) -> None:
        calls: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request)
            return self._page_response(self._postings(0, 1), total=1)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        collector = WorkdayCollector(client=client)
        company = self._workday_company()

        collector.collect(company, config={})

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].method, "POST")
        self.assertIn(
            "gresearch.wd103.myworkdayjobs.com/wday/cxs/gresearch/G-Research/jobs",
            str(calls[0].url),
        )

    def _workday_company(self) -> Company:
        return Company(
            id="company-1",
            name="G-Research",
            ats_type="workday",
            ats_tenant="gresearch",
            ats_datacenter="wd103",
            ats_site="G-Research",
        )

    def _postings(self, start: int, count: int) -> list[dict[str, object]]:
        return [
            {
                "title": f"Intern {index}",
                "externalPath": f"/job/intern-{index}",
                "locationsText": "New York",
            }
            for index in range(start, start + count)
        ]

    def _page_response(self, postings: list[dict[str, object]], total: int) -> httpx.Response:
        return httpx.Response(200, json={"jobPostings": postings, "total": total})

    def _mock_client(self, response: httpx.Response) -> httpx.Client:
        def handler(request: httpx.Request) -> httpx.Response:
            return response

        return httpx.Client(transport=httpx.MockTransport(handler))

    def _sequenced_client(self, responses: list[httpx.Response]) -> httpx.Client:
        index = {"value": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            current = index["value"]
            index["value"] += 1
            if current < len(responses):
                return responses[current]
            return httpx.Response(200, json={"jobPostings": [], "total": 0})

        return httpx.Client(transport=httpx.MockTransport(handler))
