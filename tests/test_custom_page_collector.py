from __future__ import annotations

from pathlib import Path
import unittest

import httpx

from internradar.collectors.base import collect_for_company
from internradar.collectors.custom_page import CustomPageCollector
from internradar.collectors.registry import CollectorRegistry
from internradar.core.models import Company, RawJob
from internradar.verification.status_checker import check_job_status

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "custom_page"

CAREERS_HTML = """
<html>
  <body>
    <a href="/careers/software-engineer-intern">Software Engineer Intern</a>
    <a href="/privacy">Privacy Policy</a>
    <a href="/blog">Blog</a>
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
    <a href="/apply/role-123">Apply Now</a>
  </body>
</html>
"""

GENERIC_PROGRAM_HTML = """
<html>
  <head><title>Students &amp; Graduates</title></head>
  <body>
    <h1>Students &amp; Graduates</h1>
    <p>Join a community guided by mathematical rigor, engineering excellence, and the belief that the best work can only be done together.</p>
    <a href="/careers">Explore opportunities</a>
  </body>
</html>
"""

STRUCTURED_DATA_DETAIL_HTML = """
<html>
  <head>
    <title>Careers</title>
    <script type="application/ld+json">
      {
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": "Platform Engineer Intern",
        "description": "<p>Build distributed systems for research infrastructure.</p>",
        "url": "https://example.com/jobs/platform-engineer-intern",
        "jobLocation": {
          "@type": "Place",
          "address": {
            "@type": "PostalAddress",
            "addressLocality": "Chicago",
            "addressRegion": "IL",
            "addressCountry": "US"
          }
        }
      }
    </script>
  </head>
  <body>
    <h1>Join our team</h1>
    <p>Generic marketing copy that should not override structured data.</p>
    <a href="/apply/platform-engineer-intern">Apply now</a>
  </body>
</html>
"""

SPECIFIC_JOB_WITH_HOMEPAGE_APPLY_HTML = """
<html>
  <head><title>Software Engineer Intern, Trading Infrastructure</title></head>
  <body>
    <h1>Software Engineer Intern, Trading Infrastructure</h1>
    <p>Build exchange connectivity systems in C++ and Python for Summer 2027.</p>
    <a href="https://www.imc.com/">Apply Now</a>
  </body>
</html>
"""


class TestCustomPageCollector(unittest.TestCase):
    def test_can_collect_returns_true_for_custom_ats_and_careers_url(self) -> None:
        collector = CustomPageCollector()
        company = Company(id="company-1", name="Example", ats_type="custom", careers_url="https://example.com/careers")

        self.assertTrue(collector.can_collect(company))

    def test_can_collect_returns_false_without_careers_url(self) -> None:
        collector = CustomPageCollector()
        company = Company(id="company-1", name="Example", ats_type="custom")

        self.assertFalse(collector.can_collect(company))

    def test_generic_root_page_follows_specific_role_link(self) -> None:
        client, calls = self._client_for_pages(
            {
                "https://example.com/careers": httpx.Response(200, text=CAREERS_HTML, headers={"content-type": "text/html"}),
                "https://example.com/careers/software-engineer-intern": httpx.Response(200, text=JOB_HTML, headers={"content-type": "text/html"}),
            },
        )
        collector = CustomPageCollector(client=client)
        company = Company(id="company-1", name="Example", careers_url="https://example.com/careers")

        jobs = collector.collect(company, config={})

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].title, "Software Engineer Intern, Trading Systems")
        self.assertEqual(jobs[0].apply_url, "https://example.com/apply/role-123")
        self.assertEqual(
            calls,
            [
                "https://example.com/careers",
                "https://example.com/careers/software-engineer-intern",
            ],
        )

    def test_max_pages_prevents_unverified_anchor_only_candidate(self) -> None:
        client, _ = self._client_for_pages(
            {
                "https://example.com/careers": httpx.Response(200, text=CAREERS_HTML, headers={"content-type": "text/html"}),
                "https://example.com/careers/software-engineer-intern": httpx.Response(200, text=JOB_HTML, headers={"content-type": "text/html"}),
            },
        )
        collector = CustomPageCollector(client=client)
        company = Company(id="company-1", name="Example", careers_url="https://example.com/careers")

        jobs = collector.collect(company, config={"max_pages_per_company": 1})

        self.assertEqual(jobs, [])

    def test_generic_program_page_emits_no_jobs(self) -> None:
        client, _ = self._client_for_pages(
            {
                "https://example.com/students": httpx.Response(200, text=GENERIC_PROGRAM_HTML, headers={"content-type": "text/html"}),
            },
        )
        collector = CustomPageCollector(client=client)
        company = Company(id="company-1", name="Example", careers_url="https://example.com/students")

        jobs = collector.collect(company, config={})

        self.assertEqual(jobs, [])

    def test_structured_data_takes_precedence_over_generic_visual_copy(self) -> None:
        client, _ = self._client_for_pages(
            {
                "https://example.com/jobs/platform-engineer-intern": httpx.Response(
                    200,
                    text=STRUCTURED_DATA_DETAIL_HTML,
                    headers={"content-type": "text/html"},
                ),
            },
        )
        collector = CustomPageCollector(client=client)
        company = Company(id="company-1", name="Example", careers_url="https://example.com/jobs/platform-engineer-intern")

        jobs = collector.collect(company, config={})

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].title, "Platform Engineer Intern")
        self.assertEqual(jobs[0].location_raw, "Chicago")
        self.assertEqual(jobs[0].raw_payload["extracted_from"], "structured_data")

    def test_specific_role_page_drops_generic_homepage_apply_link(self) -> None:
        client, _ = self._client_for_pages(
            {
                "https://example.com/careers/software-engineer-internship-2027": httpx.Response(
                    200,
                    text=SPECIFIC_JOB_WITH_HOMEPAGE_APPLY_HTML,
                    headers={"content-type": "text/html"},
                ),
            },
        )
        collector = CustomPageCollector(client=client)
        company = Company(
            id="company-1",
            name="Example",
            careers_url="https://example.com/careers/software-engineer-internship-2027",
        )

        jobs = collector.collect(company, config={})

        self.assertEqual(len(jobs), 1)
        self.assertIsNone(jobs[0].apply_url)
        self.assertEqual(jobs[0].url, "https://example.com/careers/software-engineer-internship-2027")

    def test_hrt_listing_extracts_specific_roles_and_never_uses_hero_copy_as_title(self) -> None:
        listing_html = self._fixture_text("hrt_student_opportunities.html")
        detail_html = self._fixture_text("hrt_sophomore_detail.html")
        client, _ = self._client_for_pages(
            {
                "https://www.hudsonrivertrading.com/student-opportunities/": httpx.Response(200, text=listing_html, headers={"content-type": "text/html"}),
                "https://www.hudsonrivertrading.com/hrt-job/sophomore-internship-summer-2026/": httpx.Response(200, text=detail_html, headers={"content-type": "text/html"}),
                "https://www.hudsonrivertrading.com/hrt-job/software-engineering-intern-summer-2026/": httpx.Response(404, text="missing", headers={"content-type": "text/html"}),
                "https://www.hudsonrivertrading.com/hrt-job/trading-systems-intern-summer-2026/": httpx.Response(404, text="missing", headers={"content-type": "text/html"}),
            },
        )
        collector = CustomPageCollector(client=client)
        company = Company(
            id="hrt",
            name="Hudson River Trading",
            careers_url="https://www.hudsonrivertrading.com/student-opportunities/",
        )

        jobs = collector.collect(company, config={})
        titles = [job.title for job in jobs]

        self.assertIn("Sophomore Internship", titles)
        self.assertIn("Software Engineering Intern", titles)
        self.assertNotIn(
            "Join a community guided by mathematical rigor, engineering excellence, and the belief that the best work can only be done together.",
            titles,
        )

    def test_hrt_listing_uses_specific_detail_url_for_live_role_and_listing_page_for_closed_watchlist(self) -> None:
        listing_html = self._fixture_text("hrt_student_opportunities.html")
        detail_html = self._fixture_text("hrt_sophomore_detail.html")
        client, _ = self._client_for_pages(
            {
                "https://www.hudsonrivertrading.com/student-opportunities/": httpx.Response(200, text=listing_html, headers={"content-type": "text/html"}),
                "https://www.hudsonrivertrading.com/hrt-job/sophomore-internship-summer-2026/": httpx.Response(200, text=detail_html, headers={"content-type": "text/html"}),
                "https://www.hudsonrivertrading.com/hrt-job/software-engineering-intern-summer-2026/": httpx.Response(404, text="missing", headers={"content-type": "text/html"}),
                "https://www.hudsonrivertrading.com/hrt-job/trading-systems-intern-summer-2026/": httpx.Response(404, text="missing", headers={"content-type": "text/html"}),
            },
        )
        collector = CustomPageCollector(client=client)
        company = Company(
            id="hrt",
            name="Hudson River Trading",
            careers_url="https://www.hudsonrivertrading.com/student-opportunities/",
        )

        jobs = collector.collect(company, config={})
        by_title = {job.title: job for job in jobs}

        self.assertEqual(
            by_title["Sophomore Internship"].url,
            "https://www.hudsonrivertrading.com/hrt-job/sophomore-internship-summer-2026/",
        )
        self.assertEqual(
            by_title["Sophomore Internship"].apply_url,
            "https://boards.greenhouse.io/hrt/jobs/123456",
        )
        self.assertEqual(
            by_title["Software Engineering Intern"].url,
            "https://www.hudsonrivertrading.com/student-opportunities/",
        )
        self.assertEqual(by_title["Software Engineering Intern"].raw_payload["status_hint"], "coming_soon")

    def test_hrt_stale_role_detail_404_without_reopening_signal_is_dropped(self) -> None:
        listing_html = self._fixture_text("hrt_student_opportunities.html")
        detail_html = self._fixture_text("hrt_sophomore_detail.html")
        client, _ = self._client_for_pages(
            {
                "https://www.hudsonrivertrading.com/student-opportunities/": httpx.Response(200, text=listing_html, headers={"content-type": "text/html"}),
                "https://www.hudsonrivertrading.com/hrt-job/sophomore-internship-summer-2026/": httpx.Response(200, text=detail_html, headers={"content-type": "text/html"}),
                "https://www.hudsonrivertrading.com/hrt-job/software-engineering-intern-summer-2026/": httpx.Response(404, text="missing", headers={"content-type": "text/html"}),
                "https://www.hudsonrivertrading.com/hrt-job/trading-systems-intern-summer-2026/": httpx.Response(404, text="missing", headers={"content-type": "text/html"}),
            },
        )
        collector = CustomPageCollector(client=client)
        company = Company(
            id="hrt",
            name="Hudson River Trading",
            careers_url="https://www.hudsonrivertrading.com/student-opportunities/",
        )

        jobs = collector.collect(company, config={})

        self.assertNotIn("Trading Systems Intern", [job.title for job in jobs])

    def test_hrt_watchlist_role_is_classified_as_coming_soon_downstream(self) -> None:
        listing_html = self._fixture_text("hrt_student_opportunities.html")
        detail_html = self._fixture_text("hrt_sophomore_detail.html")
        client, _ = self._client_for_pages(
            {
                "https://www.hudsonrivertrading.com/student-opportunities/": httpx.Response(200, text=listing_html, headers={"content-type": "text/html"}),
                "https://www.hudsonrivertrading.com/hrt-job/sophomore-internship-summer-2026/": httpx.Response(200, text=detail_html, headers={"content-type": "text/html"}),
                "https://www.hudsonrivertrading.com/hrt-job/software-engineering-intern-summer-2026/": httpx.Response(404, text="missing", headers={"content-type": "text/html"}),
                "https://www.hudsonrivertrading.com/hrt-job/trading-systems-intern-summer-2026/": httpx.Response(404, text="missing", headers={"content-type": "text/html"}),
            },
        )
        collector = CustomPageCollector(client=client)
        company = Company(
            id="hrt",
            name="Hudson River Trading",
            careers_url="https://www.hudsonrivertrading.com/student-opportunities/",
        )

        jobs = collector.collect(company, config={})
        software_intern = next(job for job in jobs if job.title == "Software Engineering Intern")
        status = check_job_status(software_intern, page_text=software_intern.description_raw, source_type=software_intern.source_type)

        self.assertEqual(status.status, "coming_soon")

    def test_gresearch_engineering_page_is_not_emitted_as_a_job(self) -> None:
        engineering_html = self._fixture_text("gresearch_engineering.html")
        client, _ = self._client_for_pages(
            {
                "https://www.gresearch.com/teams/engineering/": httpx.Response(200, text=engineering_html, headers={"content-type": "text/html"}),
                "https://www.gresearch.com/vacancies/data-analyst/": httpx.Response(404, text="missing", headers={"content-type": "text/html"}),
                "https://www.gresearch.com/vacancies/ai-engineering-intern/": httpx.Response(404, text="missing", headers={"content-type": "text/html"}),
            },
        )
        collector = CustomPageCollector(client=client)
        company = Company(
            id="gresearch",
            name="G-Research",
            careers_url="https://www.gresearch.com/teams/engineering/",
        )

        jobs = collector.collect(company, config={})

        self.assertEqual(jobs, [])

    def test_gresearch_live_vacancy_extracts_specific_role_with_explicit_cross_domain_apply_link(self) -> None:
        engineering_html = self._fixture_text("gresearch_engineering.html")
        detail_html = self._fixture_text("gresearch_data_analyst.html")
        future_html = self._fixture_text("gresearch_future_opportunities.html")
        client, _ = self._client_for_pages(
            {
                "https://www.gresearch.com/teams/engineering/": httpx.Response(200, text=engineering_html, headers={"content-type": "text/html"}),
                "https://www.gresearch.com/vacancies/data-analyst/": httpx.Response(200, text=detail_html, headers={"content-type": "text/html"}),
                "https://www.gresearch.com/vacancies/ai-engineering-intern/": httpx.Response(
                    302,
                    text="redirect",
                    headers={"location": "https://www.gresearch.com/future-opportunities/", "content-type": "text/html"},
                ),
                "https://www.gresearch.com/future-opportunities/": httpx.Response(200, text=future_html, headers={"content-type": "text/html"}),
            },
        )
        collector = CustomPageCollector(client=client)
        company = Company(
            id="gresearch",
            name="G-Research",
            careers_url="https://www.gresearch.com/teams/engineering/",
        )

        jobs = collector.collect(company, config={})
        by_title = {job.title: job for job in jobs}

        self.assertIn("Data Analyst", by_title)
        self.assertEqual(
            by_title["Data Analyst"].apply_url,
            "https://grg.wd3.myworkdayjobs.com/en-US/GResearch/job/London/Data-Analyst_R123",
        )
        self.assertNotEqual(by_title["Data Analyst"].url, "https://www.gresearch.com/teams/engineering/")

    def test_gresearch_expired_vacancy_redirect_is_never_treated_as_open(self) -> None:
        engineering_html = self._fixture_text("gresearch_engineering.html")
        detail_html = self._fixture_text("gresearch_data_analyst.html")
        future_html = self._fixture_text("gresearch_future_opportunities.html")
        client, _ = self._client_for_pages(
            {
                "https://www.gresearch.com/teams/engineering/": httpx.Response(200, text=engineering_html, headers={"content-type": "text/html"}),
                "https://www.gresearch.com/vacancies/data-analyst/": httpx.Response(200, text=detail_html, headers={"content-type": "text/html"}),
                "https://www.gresearch.com/vacancies/ai-engineering-intern/": httpx.Response(
                    302,
                    text="redirect",
                    headers={"location": "https://www.gresearch.com/future-opportunities/", "content-type": "text/html"},
                ),
                "https://www.gresearch.com/future-opportunities/": httpx.Response(200, text=future_html, headers={"content-type": "text/html"}),
            },
        )
        collector = CustomPageCollector(client=client)
        company = Company(
            id="gresearch",
            name="G-Research",
            careers_url="https://www.gresearch.com/teams/engineering/",
        )

        jobs = collector.collect(company, config={})
        ai_intern = next(job for job in jobs if job.title == "AI Engineering Intern")
        status = check_job_status(ai_intern, page_text=ai_intern.description_raw, source_type=ai_intern.source_type)

        self.assertIn(ai_intern.raw_payload["status_hint"], {"closed", "coming_soon"})
        self.assertNotEqual(status.status, "open")
        self.assertNotEqual(status.status, "likely_open")

    def test_collector_handles_root_404_gracefully(self) -> None:
        client, _ = self._client_for_pages(
            {
                "https://example.com/careers": httpx.Response(404, text="missing", headers={"content-type": "text/html"}),
            },
        )
        collector = CustomPageCollector(client=client)
        company = Company(id="company-1", name="Example", careers_url="https://example.com/careers")

        jobs, errors = collect_for_company(company, [collector], config={})

        self.assertEqual(jobs, [])
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].error_type, "invalid_config")

    def test_registry_defaults_include_custom_page_collector(self) -> None:
        registry = CollectorRegistry.with_defaults()

        self.assertIn("custom_page", [collector.source_type for collector in registry.all_collectors()])

    def _fixture_text(self, name: str) -> str:
        return (FIXTURES_DIR / name).read_text(encoding="utf-8")

    def _client_for_pages(self, pages: dict[str, httpx.Response]) -> tuple[httpx.Client, list[str]]:
        calls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            calls.append(url)
            response = pages.get(url)
            if response is None:
                return httpx.Response(404, text="missing", headers={"content-type": "text/html"})
            return response

        client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
        return client, calls
