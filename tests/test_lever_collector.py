from __future__ import annotations

import unittest
from datetime import UTC, datetime

import httpx

from internradar.collectors.base import collect_for_company
from internradar.collectors.lever import LeverCollector
from internradar.collectors.registry import CollectorRegistry
from internradar.core.models import Company, RawJob


class TestLeverCollector(unittest.TestCase):
    def test_can_collect_returns_true_for_lever_ats_type(self) -> None:
        collector = LeverCollector()
        company = Company(id="company-1", name="Example", ats_type="lever")

        self.assertTrue(collector.can_collect(company))

    def test_can_collect_returns_false_for_unrelated_ats_type(self) -> None:
        collector = LeverCollector()
        company = Company(id="company-1", name="Example", ats_type="greenhouse")

        self.assertFalse(collector.can_collect(company))

    def test_successful_response_returns_raw_jobs(self) -> None:
        client = self._mock_client(self._postings_response())
        collector = LeverCollector(client=client)
        company = Company(id="company-1", name="Example", ats_type="lever", ats_slug="example")

        jobs = collector.collect(company, config={})

        self.assertEqual(len(jobs), 1)
        self.assertIsInstance(jobs[0], RawJob)
        self.assertEqual(jobs[0].title, "Software Engineer Intern, Trading Platform")
        self.assertEqual(jobs[0].url, "https://jobs.lever.co/example/abc123")
        self.assertEqual(jobs[0].apply_url, "https://jobs.lever.co/example/abc123/apply")
        self.assertEqual(jobs[0].location_raw, "Chicago, IL")
        self.assertEqual(jobs[0].department, "Engineering")
        self.assertIn("Build high-performance trading systems.", jobs[0].description_raw or "")
        self.assertIn("Experience with C++ and Python is helpful.", jobs[0].description_raw or "")
        self.assertEqual(jobs[0].posted_at, datetime.fromtimestamp(1770000000000 / 1000, tz=UTC))
        self.assertEqual(jobs[0].raw_payload["id"], "abc123")

    def test_apply_url_falls_back_to_hosted_url(self) -> None:
        payload = self._posting()
        payload.pop("applyUrl")
        client = self._mock_client(httpx.Response(200, json=[payload]))
        collector = LeverCollector(client=client)
        company = Company(id="company-1", name="Example", ats_type="lever", ats_slug="example")

        jobs = collector.collect(company, config={})

        self.assertEqual(jobs[0].apply_url, "https://jobs.lever.co/example/abc123")

    def test_description_falls_back_to_html_fields(self) -> None:
        payload = self._posting()
        payload.pop("descriptionPlain")
        payload.pop("additionalPlain")
        payload["description"] = "<p>HTML description</p>"
        payload["additional"] = "<p>HTML additional</p>"
        client = self._mock_client(httpx.Response(200, json=[payload]))
        collector = LeverCollector(client=client)
        company = Company(id="company-1", name="Example", ats_type="lever", ats_slug="example")

        jobs = collector.collect(company, config={})

        self.assertIn("<p>HTML description</p>", jobs[0].description_raw or "")
        self.assertIn("<p>HTML additional</p>", jobs[0].description_raw or "")

    def test_empty_response_list_returns_empty_list(self) -> None:
        client = self._mock_client(httpx.Response(200, json=[]))
        collector = LeverCollector(client=client)
        company = Company(id="company-1", name="Example", ats_type="lever", ats_slug="example")

        jobs = collector.collect(company, config={})

        self.assertEqual(jobs, [])

    def test_board_not_found_is_returned_as_structured_error(self) -> None:
        client = self._mock_client(httpx.Response(404, json={"error": "not found"}))
        collector = LeverCollector(client=client)
        company = Company(id="company-1", name="Example", ats_type="lever", ats_slug="missing")

        jobs, errors = collect_for_company(company, [collector], config={})

        self.assertEqual(jobs, [])
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].error_type, "invalid_config")

    def test_invalid_json_is_returned_as_structured_error(self) -> None:
        response = httpx.Response(200, content=b"{not-json")
        client = self._mock_client(response)
        collector = LeverCollector(client=client)
        company = Company(id="company-1", name="Example", ats_type="lever", ats_slug="example")

        jobs, errors = collect_for_company(company, [collector], config={})

        self.assertEqual(jobs, [])
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].error_type, "parse_error")

    def test_missing_optional_fields_do_not_crash_parsing(self) -> None:
        client = self._mock_client(
            httpx.Response(
                200,
                json=[
                    {
                        "id": "def456",
                        "text": "Systems Intern",
                        "createdAt": 1770000000000,
                    },
                ],
            ),
        )
        collector = LeverCollector(client=client)
        company = Company(id="company-1", name="Example", ats_type="lever", ats_slug="example")

        jobs = collector.collect(company, config={})

        self.assertEqual(len(jobs), 1)
        self.assertIsNone(jobs[0].location_raw)
        self.assertIsNone(jobs[0].department)
        self.assertIsNone(jobs[0].description_raw)
        self.assertEqual(jobs[0].url, "https://jobs.lever.co/example/def456")
        self.assertEqual(jobs[0].apply_url, "https://jobs.lever.co/example/def456")

    def test_slug_inference_is_conservative(self) -> None:
        collector = LeverCollector()
        company = Company(
            id="company-1",
            name="Hudson River Trading",
            aliases=["HRT", "Hudson River Trading"],
            ats_type="lever",
        )

        self.assertEqual(
            collector.candidate_slugs(company),
            ["hudsonrivertrading", "hudson-river-trading", "hrt"],
        )

    def test_can_extract_slug_from_lever_careers_url(self) -> None:
        collector = LeverCollector()
        company = Company(
            id="company-1",
            name="Example",
            careers_url="https://jobs.lever.co/example",
        )

        self.assertTrue(collector.can_collect(company))
        self.assertEqual(collector.candidate_slugs(company), ["example"])

    def test_registry_defaults_include_lever_collector(self) -> None:
        registry = CollectorRegistry.with_defaults()

        self.assertIn("lever", [collector.source_type for collector in registry.all_collectors()])

    def test_no_live_network_calls_are_needed(self) -> None:
        calls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(str(request.url))
            return self._postings_response()

        client = httpx.Client(transport=httpx.MockTransport(handler))
        collector = LeverCollector(client=client)
        company = Company(id="company-1", name="Example", ats_type="lever", ats_slug="example")

        collector.collect(company, config={})

        self.assertEqual(len(calls), 1)
        self.assertIn("api.lever.co", calls[0])

    def _posting(self) -> dict[str, object]:
        return {
            "id": "abc123",
            "text": "Software Engineer Intern, Trading Platform",
            "hostedUrl": "https://jobs.lever.co/example/abc123",
            "applyUrl": "https://jobs.lever.co/example/abc123/apply",
            "categories": {
                "team": "Engineering",
                "location": "Chicago, IL",
                "commitment": "Internship",
            },
            "descriptionPlain": "Build high-performance trading systems.",
            "additionalPlain": "Experience with C++ and Python is helpful.",
            "createdAt": 1770000000000,
        }

    def _postings_response(self) -> httpx.Response:
        return httpx.Response(200, json=[self._posting()])

    def _mock_client(self, response: httpx.Response) -> httpx.Client:
        def handler(request: httpx.Request) -> httpx.Response:
            return response

        return httpx.Client(transport=httpx.MockTransport(handler))
