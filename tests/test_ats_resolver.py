from __future__ import annotations

import unittest

import httpx

from internradar.collectors.ats_resolver import ATSResolver, resolve_ats_for_firms
from internradar.core.models import Company


class TestATSResolver(unittest.TestCase):
    def test_resolves_greenhouse_board_by_inferred_slug(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if "boards-api.greenhouse.io" in str(request.url) and "/examplefirm/" in str(request.url):
                return httpx.Response(200, json={"jobs": [{"id": 1, "title": "Intern"}]})
            return httpx.Response(404, json={"error": "not found"})

        resolver = ATSResolver(client=self._client(handler))
        company = Company(id="company-1", name="Example Firm", ats_type="custom")

        resolution = resolver.resolve(company, config={})

        self.assertTrue(resolution.is_resolved)
        self.assertTrue(resolution.changed)
        self.assertEqual(resolution.resolved_ats_type, "greenhouse")
        self.assertEqual(resolution.resolved_slug, "examplefirm")
        self.assertEqual(resolution.job_count, 1)

    def test_falls_back_to_lever_when_greenhouse_missing(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if "api.lever.co" in url and "/examplefirm" in url:
                return httpx.Response(200, json=[{"id": "a", "text": "Intern"}])
            return httpx.Response(404, json={"error": "not found"})

        resolver = ATSResolver(client=self._client(handler))
        company = Company(id="company-1", name="Example Firm", ats_type="custom")

        resolution = resolver.resolve(company, config={})

        self.assertEqual(resolution.resolved_ats_type, "lever")
        self.assertEqual(resolution.resolved_slug, "examplefirm")
        self.assertEqual(resolution.job_count, 1)

    def test_resolves_ashby_and_counts_only_listed_jobs(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if "api.ashbyhq.com" in url and "/examplefirm" in url:
                return httpx.Response(
                    200,
                    json={
                        "jobs": [
                            {"title": "Listed", "isListed": True},
                            {"title": "Hidden", "isListed": False},
                        ],
                    },
                )
            return httpx.Response(404, json={"error": "not found"})

        resolver = ATSResolver(client=self._client(handler))
        company = Company(id="company-1", name="Example Firm", ats_type="custom")

        resolution = resolver.resolve(company, config={})

        self.assertEqual(resolution.resolved_ats_type, "ashby")
        self.assertEqual(resolution.job_count, 1)

    def test_zero_job_board_is_resolved_with_note(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if "boards-api.greenhouse.io" in str(request.url):
                return httpx.Response(200, json={"jobs": []})
            return httpx.Response(404, json={"error": "not found"})

        resolver = ATSResolver(client=self._client(handler))
        company = Company(id="company-1", name="Example Firm", ats_type="custom")

        resolution = resolver.resolve(company, config={})

        self.assertTrue(resolution.is_resolved)
        self.assertEqual(resolution.job_count, 0)
        self.assertIsNotNone(resolution.notes)

    def test_unresolved_when_no_board_matches(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, json={"error": "not found"})

        resolver = ATSResolver(client=self._client(handler))
        company = Company(id="company-1", name="Example Firm", ats_type="custom")

        resolution = resolver.resolve(company, config={})

        self.assertFalse(resolution.is_resolved)
        self.assertFalse(resolution.changed)
        self.assertIsNotNone(resolution.notes)

    def test_workday_resolved_from_careers_url_without_probing(self) -> None:
        calls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(str(request.url))
            return httpx.Response(404)

        resolver = ATSResolver(client=self._client(handler))
        company = Company(
            id="company-1",
            name="Example Firm",
            ats_type="custom",
            careers_url="https://examplefirm.wd5.myworkdayjobs.com/en-US/External",
        )

        resolution = resolver.resolve(company, config={})

        self.assertEqual(resolution.resolved_ats_type, "workday")
        self.assertEqual(resolution.resolved_tenant, "examplefirm")
        self.assertEqual(resolution.resolved_datacenter, "wd5")
        self.assertEqual(resolution.resolved_site, "External")
        self.assertEqual(calls, [])

    def test_not_changed_when_resolution_matches_current_ats(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if "boards-api.greenhouse.io" in str(request.url):
                return httpx.Response(200, json={"jobs": [{"id": 1, "title": "Intern"}]})
            return httpx.Response(404)

        resolver = ATSResolver(client=self._client(handler))
        company = Company(id="company-1", name="Example Firm", ats_type="greenhouse")

        resolution = resolver.resolve(company, config={})

        self.assertTrue(resolution.is_resolved)
        self.assertFalse(resolution.changed)

    def test_resolve_ats_for_firms_preserves_order(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404)

        resolver = ATSResolver(client=self._client(handler))
        firms = [
            Company(id="a", name="Alpha", ats_type="custom"),
            Company(id="b", name="Beta", ats_type="custom"),
        ]

        resolutions = resolve_ats_for_firms(firms, config={}, resolver=resolver)

        self.assertEqual([r.company_id for r in resolutions], ["a", "b"])

    def _client(self, handler) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(handler))
