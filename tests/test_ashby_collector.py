from __future__ import annotations

import unittest
from datetime import UTC, datetime

import httpx

from internradar.collectors.ashby import AshbyCollector
from internradar.collectors.base import collect_for_company
from internradar.collectors.registry import CollectorRegistry
from internradar.core.models import Company, RawJob


class TestAshbyCollector(unittest.TestCase):
    def test_can_collect_returns_true_for_ashby_ats_type(self) -> None:
        collector = AshbyCollector()
        company = Company(id="company-1", name="Example", ats_type="ashby")

        self.assertTrue(collector.can_collect(company))

    def test_can_collect_returns_false_for_unrelated_ats_type(self) -> None:
        collector = AshbyCollector()
        company = Company(id="company-1", name="Example", ats_type="greenhouse")

        self.assertFalse(collector.can_collect(company))

    def test_successful_response_returns_raw_jobs(self) -> None:
        client = self._mock_client(self._jobs_response())
        collector = AshbyCollector(client=client)
        company = Company(
            id="company-1",
            name="Example",
            ats_type="ashby",
            ats_slug="example",
        )

        jobs = collector.collect(company, config={})

        self.assertEqual(len(jobs), 1)
        self.assertIsInstance(jobs[0], RawJob)
        self.assertEqual(jobs[0].title, "Quantitative Research Intern")
        self.assertEqual(jobs[0].url, "https://jobs.ashbyhq.com/example/123")
        self.assertEqual(jobs[0].apply_url, "https://jobs.ashbyhq.com/example/123/application")
        self.assertEqual(jobs[0].location_raw, "New York, NY, Chicago, IL")
        self.assertEqual(jobs[0].description_raw, "Research intern role.")
        self.assertEqual(jobs[0].department, "Research")
        self.assertEqual(jobs[0].posted_at, datetime(2026, 4, 1, 12, 0, tzinfo=UTC))

    def test_unlisted_jobs_are_skipped(self) -> None:
        client = self._mock_client(
            httpx.Response(
                200,
                json={
                    "jobs": [
                        {"title": "Listed", "isListed": True},
                        {"title": "Hidden", "isListed": False},
                    ],
                },
            ),
        )
        collector = AshbyCollector(client=client)
        company = Company(id="company-1", name="Example", ats_type="ashby", ats_slug="example")

        jobs = collector.collect(company, config={})

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].title, "Listed")

    def test_empty_jobs_list_returns_empty_list(self) -> None:
        client = self._mock_client(httpx.Response(200, json={"jobs": []}))
        collector = AshbyCollector(client=client)
        company = Company(id="company-1", name="Example", ats_type="ashby", ats_slug="example")

        jobs = collector.collect(company, config={})

        self.assertEqual(jobs, [])

    def test_board_not_found_is_returned_as_structured_error(self) -> None:
        client = self._mock_client(httpx.Response(404, json={"error": "not found"}))
        collector = AshbyCollector(client=client)
        company = Company(id="company-1", name="Example", ats_type="ashby", ats_slug="missing")

        jobs, errors = collect_for_company(company, [collector], config={})

        self.assertEqual(jobs, [])
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].error_type, "invalid_config")

    def test_invalid_json_is_returned_as_structured_error(self) -> None:
        response = httpx.Response(200, content=b"{not-json")
        client = self._mock_client(response)
        collector = AshbyCollector(client=client)
        company = Company(id="company-1", name="Example", ats_type="ashby", ats_slug="example")

        jobs, errors = collect_for_company(company, [collector], config={})

        self.assertEqual(jobs, [])
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].error_type, "parse_error")

    def test_missing_optional_fields_do_not_crash_parsing(self) -> None:
        client = self._mock_client(
            httpx.Response(
                200,
                json={"jobs": [{"title": "Systems Intern"}]},
            ),
        )
        collector = AshbyCollector(client=client)
        company = Company(id="company-1", name="Example", ats_type="ashby", ats_slug="example")

        jobs = collector.collect(company, config={})

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].title, "Systems Intern")
        self.assertIsNone(jobs[0].location_raw)
        self.assertIsNone(jobs[0].description_raw)
        self.assertIsNone(jobs[0].department)
        self.assertIsNone(jobs[0].posted_at)

    def test_can_extract_slug_from_ashby_careers_url(self) -> None:
        collector = AshbyCollector()
        company = Company(
            id="company-1",
            name="Example",
            careers_url="https://jobs.ashbyhq.com/example",
        )

        self.assertTrue(collector.can_collect(company))
        self.assertEqual(collector.candidate_slugs(company), ["example"])

    def test_registry_defaults_include_ashby_collector(self) -> None:
        registry = CollectorRegistry.with_defaults()

        self.assertIn("ashby", [collector.source_type for collector in registry.all_collectors()])

    def test_no_live_network_calls_are_needed(self) -> None:
        calls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(str(request.url))
            return self._jobs_response()

        client = httpx.Client(transport=httpx.MockTransport(handler))
        collector = AshbyCollector(client=client)
        company = Company(id="company-1", name="Example", ats_type="ashby", ats_slug="example")

        collector.collect(company, config={})

        self.assertEqual(len(calls), 1)
        self.assertIn("api.ashbyhq.com", calls[0])

    def _jobs_response(self) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "jobs": [
                    {
                        "title": "Quantitative Research Intern",
                        "jobUrl": "https://jobs.ashbyhq.com/example/123",
                        "applyUrl": "https://jobs.ashbyhq.com/example/123/application",
                        "location": "New York, NY",
                        "secondaryLocations": [{"location": "Chicago, IL"}],
                        "department": "Research",
                        "descriptionPlain": "Research intern role.",
                        "publishedAt": "2026-04-01T12:00:00Z",
                        "isListed": True,
                    },
                ],
            },
        )

    def _mock_client(self, response: httpx.Response) -> httpx.Client:
        def handler(request: httpx.Request) -> httpx.Response:
            return response

        return httpx.Client(transport=httpx.MockTransport(handler))
