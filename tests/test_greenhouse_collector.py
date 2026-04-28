from __future__ import annotations

import unittest
from datetime import UTC, datetime

import httpx

from internradar.collectors.base import collect_for_company
from internradar.collectors.greenhouse import GreenhouseCollector
from internradar.collectors.registry import CollectorRegistry
from internradar.core.models import Company, RawJob


class TestGreenhouseCollector(unittest.TestCase):
    def test_can_collect_returns_true_for_greenhouse_ats_type(self) -> None:
        collector = GreenhouseCollector()
        company = Company(id="company-1", name="Example", ats_type="greenhouse")

        self.assertTrue(collector.can_collect(company))

    def test_can_collect_returns_false_for_unrelated_ats_type(self) -> None:
        collector = GreenhouseCollector()
        company = Company(id="company-1", name="Example", ats_type="lever")

        self.assertFalse(collector.can_collect(company))

    def test_successful_response_returns_raw_jobs(self) -> None:
        client = self._mock_client(self._jobs_response())
        collector = GreenhouseCollector(client=client)
        company = Company(
            id="company-1",
            name="Example",
            ats_type="greenhouse",
            ats_slug="example",
        )

        jobs = collector.collect(company, config={})

        self.assertEqual(len(jobs), 1)
        self.assertIsInstance(jobs[0], RawJob)
        self.assertEqual(jobs[0].title, "Software Engineer Intern, Trading Systems")
        self.assertEqual(
            jobs[0].url,
            "https://boards.greenhouse.io/example/jobs/123",
        )
        self.assertEqual(jobs[0].location_raw, "New York, NY")
        self.assertEqual(
            jobs[0].description_raw,
            "<p>Work on low latency trading systems in C++.</p>",
        )
        self.assertEqual(jobs[0].department, "Engineering")
        self.assertEqual(jobs[0].posted_at, datetime(2026, 4, 1, 12, 0, tzinfo=UTC))
        self.assertEqual(jobs[0].raw_payload["id"], 123)

    def test_empty_jobs_list_returns_empty_list(self) -> None:
        client = self._mock_client(httpx.Response(200, json={"jobs": []}))
        collector = GreenhouseCollector(client=client)
        company = Company(id="company-1", name="Example", ats_type="greenhouse", ats_slug="example")

        jobs = collector.collect(company, config={})

        self.assertEqual(jobs, [])

    def test_board_not_found_is_returned_as_structured_error(self) -> None:
        client = self._mock_client(httpx.Response(404, json={"error": "not found"}))
        collector = GreenhouseCollector(client=client)
        company = Company(id="company-1", name="Example", ats_type="greenhouse", ats_slug="missing")

        jobs, errors = collect_for_company(company, [collector], config={})

        self.assertEqual(jobs, [])
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].error_type, "invalid_config")

    def test_invalid_json_is_returned_as_structured_error(self) -> None:
        response = httpx.Response(200, content=b"{not-json")
        client = self._mock_client(response)
        collector = GreenhouseCollector(client=client)
        company = Company(id="company-1", name="Example", ats_type="greenhouse", ats_slug="example")

        jobs, errors = collect_for_company(company, [collector], config={})

        self.assertEqual(jobs, [])
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].error_type, "parse_error")

    def test_missing_optional_fields_do_not_crash_parsing(self) -> None:
        client = self._mock_client(
            httpx.Response(
                200,
                json={
                    "jobs": [
                        {
                            "id": 456,
                            "title": "Systems Intern",
                            "updated_at": "2026-04-01T12:00:00Z",
                        },
                    ],
                },
            ),
        )
        collector = GreenhouseCollector(client=client)
        company = Company(id="company-1", name="Example", ats_type="greenhouse", ats_slug="example")

        jobs = collector.collect(company, config={})

        self.assertEqual(len(jobs), 1)
        self.assertIsNone(jobs[0].location_raw)
        self.assertIsNone(jobs[0].description_raw)
        self.assertIsNone(jobs[0].department)
        self.assertEqual(jobs[0].url, "https://boards.greenhouse.io/example/jobs/456")

    def test_slug_inference_is_conservative(self) -> None:
        collector = GreenhouseCollector()
        company = Company(
            id="company-1",
            name="Hudson River Trading",
            aliases=["HRT", "Hudson River Trading"],
            ats_type="greenhouse",
        )

        slugs = collector.candidate_slugs(company)

        self.assertEqual(
            slugs,
            ["hudsonrivertrading", "hudson-river-trading", "hrt"],
        )

    def test_can_extract_slug_from_greenhouse_careers_url(self) -> None:
        collector = GreenhouseCollector()
        company = Company(
            id="company-1",
            name="Example",
            careers_url="https://boards.greenhouse.io/embed/job_board?for=example",
        )

        self.assertTrue(collector.can_collect(company))
        self.assertEqual(collector.candidate_slugs(company), ["example"])

    def test_registry_defaults_include_greenhouse_collector(self) -> None:
        registry = CollectorRegistry.with_defaults()

        self.assertIn("greenhouse", [collector.source_type for collector in registry.all_collectors()])

    def test_no_live_network_calls_are_needed(self) -> None:
        calls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(str(request.url))
            return self._jobs_response()

        client = httpx.Client(transport=httpx.MockTransport(handler))
        collector = GreenhouseCollector(client=client)
        company = Company(id="company-1", name="Example", ats_type="greenhouse", ats_slug="example")

        collector.collect(company, config={})

        self.assertEqual(len(calls), 1)
        self.assertIn("boards-api.greenhouse.io", calls[0])

    def _jobs_response(self) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "jobs": [
                    {
                        "id": 123,
                        "title": "Software Engineer Intern, Trading Systems",
                        "absolute_url": "https://boards.greenhouse.io/example/jobs/123",
                        "location": {"name": "New York, NY"},
                        "content": "<p>Work on low latency trading systems in C++.</p>",
                        "departments": [{"name": "Engineering"}],
                        "updated_at": "2026-04-01T12:00:00Z",
                    },
                ],
            },
        )

    def _mock_client(self, response: httpx.Response) -> httpx.Client:
        def handler(request: httpx.Request) -> httpx.Response:
            return response

        return httpx.Client(transport=httpx.MockTransport(handler))
