from __future__ import annotations

import unittest

import httpx

from internradar.collectors.base import collect_for_company
from internradar.collectors.custom_page import CustomPageCollector
from internradar.collectors.registry import CollectorRegistry
from internradar.core.models import Company, RawJob

CAREERS_HTML = """
<html>
  <body>
    <a href="/careers/software-engineer-intern">Software Engineer Intern</a>
    <a href="/careers/software-engineer-intern">Software Engineer Intern</a>
    <a href="/privacy">Privacy Policy</a>
    <a href="/blog">Blog</a>
    <a href="/login">Login</a>
  </body>
</html>
"""

JOB_HTML = """
<html>
  <head><title>Software Engineer Intern, Trading Systems</title></head>
  <body>
    <h1>Software Engineer Intern, Trading Systems</h1>
    <p>Work on low latency trading infrastructure in C++ and Python.</p>
    <p>Summer 2027 internship in New York.</p>
    <a href="/apply">Apply Now</a>
  </body>
</html>
"""


class TestCustomPageCollector(unittest.TestCase):
    def test_can_collect_returns_true_for_custom_ats_and_careers_url(self) -> None:
        collector = CustomPageCollector()
        company = Company(id="company-1", name="Example", ats_type="custom", careers_url="https://example.com/careers")

        self.assertTrue(collector.can_collect(company))

    def test_can_collect_returns_true_for_missing_ats_type_with_careers_url(self) -> None:
        collector = CustomPageCollector()
        company = Company(id="company-1", name="Example", careers_url="https://example.com/careers")

        self.assertTrue(collector.can_collect(company))

    def test_can_collect_returns_false_without_careers_url(self) -> None:
        collector = CustomPageCollector()
        company = Company(id="company-1", name="Example", ats_type="custom")

        self.assertFalse(collector.can_collect(company))

    def test_collector_extracts_candidate_links_and_resolves_relative_urls(self) -> None:
        client, calls = self._client_for_pages(
            {
                "https://example.com/careers": httpx.Response(
                    200,
                    text=CAREERS_HTML,
                    headers={"content-type": "text/html"},
                ),
                "https://example.com/careers/software-engineer-intern": httpx.Response(
                    200,
                    text=JOB_HTML,
                    headers={"content-type": "text/html"},
                ),
            },
        )
        collector = CustomPageCollector(client=client)
        company = Company(id="company-1", name="Example", ats_type="custom", careers_url="https://example.com/careers")

        jobs = collector.collect(company, config={})

        self.assertEqual(len(jobs), 1)
        self.assertEqual(
            calls,
            [
                "https://example.com/careers",
                "https://example.com/careers/software-engineer-intern",
            ],
        )

    def test_collector_creates_raw_job_for_plausible_internship_page(self) -> None:
        client, _ = self._client_for_pages(
            {
                "https://example.com/careers": httpx.Response(
                    200,
                    text=CAREERS_HTML,
                    headers={"content-type": "text/html"},
                ),
                "https://example.com/careers/software-engineer-intern": httpx.Response(
                    200,
                    text=JOB_HTML,
                    headers={"content-type": "text/html"},
                ),
            },
        )
        collector = CustomPageCollector(client=client)
        company = Company(id="company-1", name="Example", ats_type="custom", careers_url="https://example.com/careers")

        jobs = collector.collect(company, config={})

        self.assertEqual(len(jobs), 1)
        self.assertIsInstance(jobs[0], RawJob)
        self.assertEqual(jobs[0].title, "Software Engineer Intern, Trading Systems")
        self.assertEqual(jobs[0].apply_url, "https://example.com/apply")
        self.assertEqual(jobs[0].location_raw, "New York")
        self.assertIn("low latency trading infrastructure", jobs[0].description_raw or "")
        self.assertIn("intern", " ".join(jobs[0].raw_payload["matched_keywords"]))

    def test_collector_ignores_irrelevant_links(self) -> None:
        client, calls = self._client_for_pages(
            {
                "https://example.com/careers": httpx.Response(
                    200,
                    text=CAREERS_HTML,
                    headers={"content-type": "text/html"},
                ),
                "https://example.com/careers/software-engineer-intern": httpx.Response(
                    200,
                    text=JOB_HTML,
                    headers={"content-type": "text/html"},
                ),
            },
        )
        collector = CustomPageCollector(client=client)
        company = Company(id="company-1", name="Example", careers_url="https://example.com/careers")

        collector.collect(company, config={})

        self.assertNotIn("https://example.com/privacy", calls)
        self.assertNotIn("https://example.com/blog", calls)
        self.assertNotIn("https://example.com/login", calls)

    def test_collector_respects_max_pages_per_company(self) -> None:
        client, calls = self._client_for_pages(
            {
                "https://example.com/careers": httpx.Response(
                    200,
                    text=CAREERS_HTML,
                    headers={"content-type": "text/html"},
                ),
                "https://example.com/careers/software-engineer-intern": httpx.Response(
                    200,
                    text=JOB_HTML,
                    headers={"content-type": "text/html"},
                ),
            },
        )
        collector = CustomPageCollector(client=client)
        company = Company(id="company-1", name="Example", careers_url="https://example.com/careers")

        jobs = collector.collect(company, config={"max_pages_per_company": 1})

        self.assertEqual(jobs, [])
        self.assertEqual(calls, ["https://example.com/careers"])

    def test_collector_handles_404_gracefully(self) -> None:
        client, _ = self._client_for_pages(
            {
                "https://example.com/careers": httpx.Response(
                    404,
                    text="missing",
                    headers={"content-type": "text/html"},
                ),
            },
        )
        collector = CustomPageCollector(client=client)
        company = Company(id="company-1", name="Example", careers_url="https://example.com/careers")

        jobs, errors = collect_for_company(company, [collector], config={})

        self.assertEqual(jobs, [])
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].error_type, "invalid_config")

    def test_collector_handles_pages_with_no_jobs_gracefully(self) -> None:
        client, _ = self._client_for_pages(
            {
                "https://example.com/careers": httpx.Response(
                    200,
                    text="<html><body><h1>Careers</h1><p>Join us.</p></body></html>",
                    headers={"content-type": "text/html"},
                ),
            },
        )
        collector = CustomPageCollector(client=client)
        company = Company(id="company-1", name="Example", careers_url="https://example.com/careers")

        jobs = collector.collect(company, config={})

        self.assertEqual(jobs, [])

    def test_collector_avoids_duplicate_links(self) -> None:
        client, calls = self._client_for_pages(
            {
                "https://example.com/careers": httpx.Response(
                    200,
                    text=CAREERS_HTML,
                    headers={"content-type": "text/html"},
                ),
                "https://example.com/careers/software-engineer-intern": httpx.Response(
                    200,
                    text=JOB_HTML,
                    headers={"content-type": "text/html"},
                ),
            },
        )
        collector = CustomPageCollector(client=client)
        company = Company(id="company-1", name="Example", careers_url="https://example.com/careers")

        collector.collect(company, config={})

        self.assertEqual(calls.count("https://example.com/careers/software-engineer-intern"), 1)

    def test_collector_records_matched_keywords(self) -> None:
        client, _ = self._client_for_pages(
            {
                "https://example.com/careers": httpx.Response(
                    200,
                    text=CAREERS_HTML,
                    headers={"content-type": "text/html"},
                ),
                "https://example.com/careers/software-engineer-intern": httpx.Response(
                    200,
                    text=JOB_HTML,
                    headers={"content-type": "text/html"},
                ),
            },
        )
        collector = CustomPageCollector(client=client)
        company = Company(id="company-1", name="Example", careers_url="https://example.com/careers")

        jobs = collector.collect(company, config={})

        self.assertIn("software engineer", jobs[0].raw_payload["matched_keywords"])
        self.assertIn("intern", jobs[0].raw_payload["matched_keywords"])

    def test_registry_defaults_include_custom_page_collector(self) -> None:
        registry = CollectorRegistry.with_defaults()

        self.assertIn("custom_page", [collector.source_type for collector in registry.all_collectors()])

    def _client_for_pages(
        self,
        pages: dict[str, httpx.Response],
    ) -> tuple[httpx.Client, list[str]]:
        calls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            calls.append(url)
            response = pages.get(url)
            if response is None:
                return httpx.Response(
                    404,
                    text="missing",
                    headers={"content-type": "text/html"},
                )
            return response

        client = httpx.Client(transport=httpx.MockTransport(handler))
        return client, calls
