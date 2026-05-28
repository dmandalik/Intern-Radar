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

IMC_SEARCH_CAREERS_FALLBACK_HTML = """
<html>
  <body>
    <section>
      <h2>Principal Machine Learning Engineer</h2>
      <p>Experienced Technology Amsterdam, Chicago, Hong Kong, London, New York, Sydney</p>
    </section>
    <section>
      <h2>Software Engineer – AI Powered Engineering</h2>
      <p>Experienced Technology Chicago</p>
    </section>
    <div class="hidden-links">
      <a href="/us/careers/jobs/4721116101">Principal Machine Learning Engineer Experienced Technology Amsterdam, Chicago, Hong Kong, London, New York, Sydney</a>
      <a href="/us/careers/jobs/4682071101">Software Engineer – AI Powered Engineering Experienced Technology Chicago</a>
    </div>
  </body>
</html>
"""

GENERIC_LISTING_ONLY_HTML = """
<html>
  <body>
    <section>
      <h2>Principal Machine Learning Engineer</h2>
      <p>Experienced Technology Amsterdam, Chicago, Hong Kong, London, New York, Sydney</p>
    </section>
    <section>
      <h2>Software Engineer – AI Powered Engineering</h2>
      <p>Experienced Technology Chicago</p>
    </section>
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

    def test_imc_root_discovers_search_careers_and_emits_specific_role_pages(self) -> None:
        root_html = self._fixture_text("imc_careers_root.html")
        search_html = self._fixture_text("imc_search_careers.html")
        software_detail_html = self._fixture_text("imc_software_engineer_intern.html")
        quant_detail_html = self._fixture_text("imc_quantitative_developer_intern.html")
        client, calls = self._client_for_pages(
            {
                "https://www.imc.com/us/careers/": httpx.Response(200, text=root_html, headers={"content-type": "text/html"}),
                "https://www.imc.com/us/search-careers": httpx.Response(200, text=search_html, headers={"content-type": "text/html"}),
                "https://www.imc.com/us/careers/jobs/1234567890": httpx.Response(200, text=software_detail_html, headers={"content-type": "text/html"}),
                "https://www.imc.com/us/careers/jobs/2234567890": httpx.Response(200, text=quant_detail_html, headers={"content-type": "text/html"}),
            },
        )
        collector = CustomPageCollector(client=client)
        company = Company(id="imc", name="IMC Trading", careers_url="https://www.imc.com/us/careers/")

        jobs = collector.collect(company, config={})
        by_title = {job.title: job for job in jobs}

        self.assertEqual(
            calls,
            [
                "https://www.imc.com/us/careers/",
                "https://www.imc.com/us/search-careers",
                "https://www.imc.com/us/careers/jobs/1234567890",
                "https://www.imc.com/us/careers/jobs/2234567890",
            ],
        )
        self.assertIn("Software Engineer Intern", by_title)
        self.assertIn("Quantitative Developer Intern", by_title)
        self.assertNotIn("HOW WE HIRE", by_title)
        self.assertTrue(all(job.url.startswith("https://www.imc.com/us/careers/jobs/") for job in jobs))
        self.assertEqual(
            by_title["Software Engineer Intern"].apply_url,
            "https://careers.imc.com/apply/software-engineer-intern-123",
        )
        self.assertEqual(by_title["Software Engineer Intern"].location_raw, "Amsterdam")

    def test_imc_recruitment_process_page_never_emits_how_we_hire_and_recovers_to_specific_jobs(self) -> None:
        recruitment_html = self._fixture_text("imc_recruitment_process.html")
        search_html = self._fixture_text("imc_search_careers.html")
        software_detail_html = self._fixture_text("imc_software_engineer_intern.html")
        quant_detail_html = self._fixture_text("imc_quantitative_developer_intern.html")
        client, _ = self._client_for_pages(
            {
                "https://www.imc.com/us/careers/recruitment-process/": httpx.Response(
                    200,
                    text=recruitment_html,
                    headers={"content-type": "text/html"},
                ),
                "https://www.imc.com/us/search-careers": httpx.Response(200, text=search_html, headers={"content-type": "text/html"}),
                "https://www.imc.com/us/careers/jobs/1234567890": httpx.Response(200, text=software_detail_html, headers={"content-type": "text/html"}),
                "https://www.imc.com/us/careers/jobs/2234567890": httpx.Response(200, text=quant_detail_html, headers={"content-type": "text/html"}),
            },
        )
        collector = CustomPageCollector(client=client)
        company = Company(
            id="imc",
            name="IMC Trading",
            careers_url="https://www.imc.com/us/careers/recruitment-process/",
        )

        jobs = collector.collect(company, config={})
        titles = [job.title for job in jobs]

        self.assertNotIn("HOW WE HIRE", titles)
        self.assertNotIn("Recruitment process", titles)
        self.assertIn("Software Engineer Intern", titles)
        self.assertTrue(all("/careers/jobs/" in job.url for job in jobs))

    def test_imc_listing_can_recover_specific_detail_links_when_role_cards_only_have_local_metadata(self) -> None:
        software_detail_html = self._fixture_text("imc_software_engineer_intern.html")
        client, _ = self._client_for_pages(
            {
                "https://www.imc.com/us/search-careers": httpx.Response(
                    200,
                    text=IMC_SEARCH_CAREERS_FALLBACK_HTML,
                    headers={"content-type": "text/html"},
                ),
                "https://www.imc.com/us/careers/jobs/4721116101": httpx.Response(
                    200,
                    text=software_detail_html.replace(
                        "Software Engineer Intern",
                        "Principal Machine Learning Engineer",
                    ).replace(
                        "https://careers.imc.com/apply/software-engineer-intern-123",
                        "https://careers.imc.com/apply/principal-machine-learning-engineer-472",
                    ),
                    headers={"content-type": "text/html"},
                ),
                "https://www.imc.com/us/careers/jobs/4682071101": httpx.Response(
                    200,
                    text="""<html><body><h1>Software Engineer – AI Powered Engineering</h1><div>Experienced</div><div>Technology</div><div>Chicago</div><p>Build agentic AI systems for developers.</p><a href="https://careers.imc.com/apply/software-engineer-ai-468">Apply Now</a></body></html>""",
                    headers={"content-type": "text/html"},
                ),
            },
        )
        collector = CustomPageCollector(client=client)
        company = Company(id="imc", name="IMC Trading", careers_url="https://www.imc.com/us/search-careers")

        jobs = collector.collect(company, config={})
        by_title = {job.title: job for job in jobs}

        self.assertEqual(
            by_title["Principal Machine Learning Engineer"].url,
            "https://www.imc.com/us/careers/jobs/4721116101",
        )
        self.assertEqual(
            by_title["Principal Machine Learning Engineer"].apply_url,
            "https://careers.imc.com/apply/principal-machine-learning-engineer-472",
        )

    def test_generic_listing_without_specific_urls_is_dropped(self) -> None:
        client, _ = self._client_for_pages(
            {
                "https://www.imc.com/us/search-careers": httpx.Response(
                    200,
                    text=GENERIC_LISTING_ONLY_HTML,
                    headers={"content-type": "text/html"},
                ),
            },
        )
        collector = CustomPageCollector(client=client)
        company = Company(id="imc", name="IMC Trading", careers_url="https://www.imc.com/us/search-careers")

        jobs = collector.collect(company, config={})

        self.assertEqual(jobs, [])

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

    def test_imc_seed_discovery_falls_back_when_root_has_no_search_careers_anchor(self) -> None:
        """Root page without a /search-careers anchor still locates the seed.

        Regression test for the IMC "generic careers link" symptom: when the
        root marketing HTML does not link to the search-careers endpoint, the
        collector must still try region-aware fallback paths before giving up.
        """

        rootless_root_html = """
        <html><body>
          <h1>IMC Careers</h1>
          <p>Marketing copy with no search-careers link.</p>
        </body></html>
        """
        search_html = self._fixture_text("imc_search_careers.html")
        software_detail_html = self._fixture_text("imc_software_engineer_intern.html")
        quant_detail_html = self._fixture_text("imc_quantitative_developer_intern.html")
        client, calls = self._client_for_pages(
            {
                "https://www.imc.com/us/careers/": httpx.Response(200, text=rootless_root_html, headers={"content-type": "text/html"}),
                "https://www.imc.com/us/search-careers": httpx.Response(200, text=search_html, headers={"content-type": "text/html"}),
                "https://www.imc.com/us/careers/jobs/1234567890": httpx.Response(200, text=software_detail_html, headers={"content-type": "text/html"}),
                "https://www.imc.com/us/careers/jobs/2234567890": httpx.Response(200, text=quant_detail_html, headers={"content-type": "text/html"}),
            },
        )
        collector = CustomPageCollector(client=client)
        company = Company(id="imc", name="IMC Trading", careers_url="https://www.imc.com/us/careers/")

        jobs = collector.collect(company, config={})

        self.assertIn("https://www.imc.com/us/search-careers", calls)
        self.assertTrue(
            all(job.url.startswith("https://www.imc.com/us/careers/jobs/") for job in jobs),
            f"Every IMC job must link to a specific posting, got: {[j.url for j in jobs]}",
        )
        self.assertGreaterEqual(len(jobs), 1)

    def test_imc_seed_discovery_skips_candidates_without_specific_anchors(self) -> None:
        """A search-careers candidate that lacks /careers/jobs/ anchors is rejected.

        This prevents the collector from accepting a non-listing page (e.g. a
        marketing landing) just because the URL pattern happened to resolve.
        """

        rootless_root_html = """
        <html><body>
          <p>Marketing copy with no search-careers link.</p>
        </body></html>
        """
        empty_search_html = "<html><body><h1>No roles here</h1></body></html>"
        client, calls = self._client_for_pages(
            {
                "https://www.imc.com/us/careers/": httpx.Response(200, text=rootless_root_html, headers={"content-type": "text/html"}),
                "https://www.imc.com/us/search-careers": httpx.Response(200, text=empty_search_html, headers={"content-type": "text/html"}),
            },
        )
        collector = CustomPageCollector(client=client)
        company = Company(id="imc", name="IMC Trading", careers_url="https://www.imc.com/us/careers/")

        jobs = collector.collect(company, config={})

        # Should not emit any job since no specific anchors are discoverable.
        self.assertEqual(jobs, [])

    def test_url_specificity_guard_blocks_generic_root_url(self) -> None:
        """A candidate whose source URL is the careers root must not slip through."""

        listing_html = """
        <html><body>
          <section>
            <h2>Software Engineer Intern</h2>
            <p>Summer 2026 Chicago</p>
          </section>
        </body></html>
        """
        client, _ = self._client_for_pages(
            {
                "https://example.com/careers": httpx.Response(200, text=listing_html, headers={"content-type": "text/html"}),
            },
        )
        collector = CustomPageCollector(client=client)
        company = Company(
            id="company-1",
            name="Example",
            careers_url="https://example.com/careers",
            website="https://example.com",
        )

        jobs = collector.collect(company, config={})

        # No specific role anchor present, so no job should leak with the
        # generic careers URL.
        self.assertEqual([job for job in jobs if job.url == "https://example.com/careers"], [])

    def test_generic_listing_pairs_with_sibling_detail_anchors(self) -> None:
        """Listing pages that render anchors apart from the role card still pair."""

        # Simulates the IMC SPA-style layout but on a non-adapter domain.
        page_html = """
        <html><body>
          <section>
            <h2>Software Engineer Intern</h2>
            <p>Chicago Summer 2026</p>
          </section>
          <section>
            <h2>Quantitative Researcher Intern</h2>
            <p>New York Summer 2026</p>
          </section>
          <div class="hidden-links">
            <a href="/jobs/software-engineer-intern-9001">Software Engineer Intern Chicago Summer 2026</a>
            <a href="/jobs/quant-researcher-intern-9002">Quantitative Researcher Intern New York Summer 2026</a>
          </div>
        </body></html>
        """
        detail_html = """
        <html><body>
          <h1>Software Engineer Intern</h1>
          <p>Summer 2026 internship in Chicago.</p>
          <a href="https://apply.example.com/se-intern-9001">Apply Now</a>
        </body></html>
        """
        quant_detail_html = """
        <html><body>
          <h1>Quantitative Researcher Intern</h1>
          <p>Summer 2026 internship in New York.</p>
          <a href="https://apply.example.com/quant-intern-9002">Apply Now</a>
        </body></html>
        """
        client, _ = self._client_for_pages(
            {
                "https://example.com/careers": httpx.Response(200, text=page_html, headers={"content-type": "text/html"}),
                "https://example.com/jobs/software-engineer-intern-9001": httpx.Response(200, text=detail_html, headers={"content-type": "text/html"}),
                "https://example.com/jobs/quant-researcher-intern-9002": httpx.Response(200, text=quant_detail_html, headers={"content-type": "text/html"}),
            },
        )
        collector = CustomPageCollector(client=client)
        company = Company(
            id="example",
            name="Example",
            careers_url="https://example.com/careers",
        )

        jobs = collector.collect(company, config={})
        by_title = {job.title: job for job in jobs}

        self.assertIn("Software Engineer Intern", by_title)
        self.assertIn("Quantitative Researcher Intern", by_title)
        # Critical assertion: each emitted job has a specific posting URL.
        self.assertEqual(
            by_title["Software Engineer Intern"].url,
            "https://example.com/jobs/software-engineer-intern-9001",
        )
        self.assertEqual(
            by_title["Quantitative Researcher Intern"].url,
            "https://example.com/jobs/quant-researcher-intern-9002",
        )

    def test_imc_detail_pairing_refuses_to_assign_arbitrary_anchor_on_no_match(self) -> None:
        """The IMC pairing must NEVER fall back to the first available anchor.

        Before the fix this caused mismatched URLs to be silently attached
        when the anchor text and role card heading diverged.
        """

        search_html = """
        <html><body>
          <section>
            <h2>Brand New Mystery Role</h2>
            <p>Chicago Summer 2026</p>
          </section>
          <div class="hidden-links">
            <a href="/us/careers/jobs/1111111111">Totally Unrelated Anchor Text</a>
          </div>
        </body></html>
        """
        client, _ = self._client_for_pages(
            {
                "https://www.imc.com/us/search-careers": httpx.Response(200, text=search_html, headers={"content-type": "text/html"}),
                "https://www.imc.com/us/careers/jobs/1111111111": httpx.Response(
                    200,
                    text="<html><body><h1>Other Role</h1></body></html>",
                    headers={"content-type": "text/html"},
                ),
            },
        )
        collector = CustomPageCollector(client=client)
        company = Company(id="imc", name="IMC Trading", careers_url="https://www.imc.com/us/search-careers")

        jobs = collector.collect(company, config={})

        # The candidate cannot be confidently paired, so nothing should be
        # emitted with the unrelated anchor.
        self.assertEqual(
            [job for job in jobs if job.url == "https://www.imc.com/us/careers/jobs/1111111111" and "Mystery" in job.title],
            [],
        )

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
