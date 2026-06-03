"""Best-effort ATS auto-resolver.

Given a :class:`Company`, probe the known JSON-API ATS platforms (Greenhouse,
Lever, Ashby, Workday) to discover which one actually hosts the firm's board and
which slug / coordinates address it. This powers the ``firms resolve-ats``
command so that ``ats_type: custom`` firms can be promoted to a robust API
collector instead of the brittle HTML scraper.

The resolver is intentionally read-only: it never mutates ``firms.yaml``. It
reports a suggested mapping that a human can apply.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field

import httpx

from internradar.collectors.ashby import ASHBY_API_URL, AshbyCollector
from internradar.collectors.greenhouse import GREENHOUSE_API_HOSTS, GreenhouseCollector
from internradar.collectors.lever import LEVER_API_URL, LeverCollector
from internradar.collectors.workday import WorkdayCollector
from internradar.core.config import AppConfig
from internradar.core.models import Company

DEFAULT_TIMEOUT_SECONDS = 20.0
DEFAULT_USER_AGENT = "InternRadar/0.1"
# Sources probed by slug inference, in priority order. Workday is handled
# separately because its coordinates are not guessable from a firm name.
SLUG_PROBE_ORDER = ("greenhouse", "lever", "ashby")


@dataclass(slots=True)
class ATSResolution:
    company_id: str
    company_name: str
    current_ats_type: str | None
    resolved_ats_type: str | None = None
    resolved_slug: str | None = None
    resolved_tenant: str | None = None
    resolved_datacenter: str | None = None
    resolved_site: str | None = None
    job_count: int | None = None
    candidates_tried: list[str] = field(default_factory=list)
    notes: str | None = None

    @property
    def is_resolved(self) -> bool:
        return self.resolved_ats_type is not None

    @property
    def changed(self) -> bool:
        """True when the resolved ATS differs from what the firm declares."""
        if not self.is_resolved:
            return False
        return (self.current_ats_type or "").casefold() != (
            self.resolved_ats_type or ""
        ).casefold()


class ATSResolver:
    """Probe live ATS endpoints to discover a firm's real board."""

    def __init__(
        self,
        client: httpx.Client | None = None,
        sleeper: Callable[[float], None] | None = None,
    ) -> None:
        self._client = client
        self._sleeper = sleeper or time.sleep
        self._greenhouse = GreenhouseCollector()
        self._lever = LeverCollector()
        self._ashby = AshbyCollector()
        self._workday = WorkdayCollector()

    def resolve(self, company: Company, config: AppConfig) -> ATSResolution:
        resolution = ATSResolution(
            company_id=company.id,
            company_name=company.name,
            current_ats_type=company.ats_type,
        )

        timeout_seconds = float(config.get("request_timeout_seconds", DEFAULT_TIMEOUT_SECONDS))
        user_agent = str(config.get("user_agent", DEFAULT_USER_AGENT))
        polite_delay_seconds = float(config.get("polite_delay_seconds", 0.0))

        owns_client = self._client is None
        client = self._client or httpx.Client(
            headers={"User-Agent": user_agent},
            timeout=timeout_seconds,
            follow_redirects=True,
        )

        try:
            # Workday can only be resolved from an explicit myworkdayjobs URL or
            # pre-set coordinates; never guessed from a firm name.
            if self._workday.can_collect(company):
                coordinates = self._workday._resolve_coordinates(company)  # noqa: SLF001
                if coordinates is not None:
                    tenant, datacenter, site = coordinates
                    resolution.resolved_ats_type = "workday"
                    resolution.resolved_tenant = tenant
                    resolution.resolved_datacenter = datacenter
                    resolution.resolved_site = site
                    resolution.candidates_tried.append(f"workday:{tenant}/{site}")
                    return resolution

            request_index = 0
            for source_type in SLUG_PROBE_ORDER:
                collector, slug_candidates = self._candidates_for_source(source_type, company)
                for slug in slug_candidates:
                    resolution.candidates_tried.append(f"{source_type}:{slug}")
                    if request_index > 0 and polite_delay_seconds > 0:
                        self._sleeper(polite_delay_seconds)
                    request_index += 1

                    job_count = self._probe(client, source_type, slug)
                    if job_count is not None:
                        resolution.resolved_ats_type = source_type
                        resolution.resolved_slug = slug
                        resolution.job_count = job_count
                        if job_count == 0:
                            resolution.notes = "Board exists but currently lists 0 jobs."
                        return resolution

            resolution.notes = "No ATS board matched; keep on custom collector."
            return resolution
        finally:
            if owns_client:
                client.close()

    def _candidates_for_source(
        self,
        source_type: str,
        company: Company,
    ) -> tuple[GreenhouseCollector | LeverCollector | AshbyCollector, list[str]]:
        # Clear any declared slug so inference is exercised, but keep the
        # careers_url so an embedded slug is still discovered.
        probe_company = company.model_copy(update={"ats_type": source_type, "ats_slug": None})
        if source_type == "greenhouse":
            return self._greenhouse, self._greenhouse.candidate_slugs(probe_company)
        if source_type == "lever":
            return self._lever, self._lever.candidate_slugs(probe_company)
        return self._ashby, self._ashby.candidate_slugs(probe_company)

    def _probe(self, client: httpx.Client, source_type: str, slug: str) -> int | None:
        """Return the job count if ``slug`` is a real board, else ``None``."""
        try:
            if source_type == "greenhouse":
                return self._probe_greenhouse(client, slug)
            if source_type == "lever":
                return self._probe_lever(client, slug)
            return self._probe_ashby(client, slug)
        except httpx.HTTPError:
            return None

    def _probe_greenhouse(self, client: httpx.Client, slug: str) -> int | None:
        for api_url in GREENHOUSE_API_HOSTS:
            response = client.get(api_url.format(slug=slug), params={"content": "true"})
            if response.status_code == 404:
                continue
            if response.status_code != 200:
                return None
            payload = self._json_or_none(response)
            jobs = payload.get("jobs") if isinstance(payload, dict) else None
            if isinstance(jobs, list):
                return len(jobs)
            return None
        return None

    def _probe_lever(self, client: httpx.Client, slug: str) -> int | None:
        response = client.get(LEVER_API_URL.format(slug=slug), params={"mode": "json"})
        if response.status_code != 200:
            return None
        payload = self._json_or_none(response)
        if isinstance(payload, list):
            return len(payload)
        return None

    def _probe_ashby(self, client: httpx.Client, slug: str) -> int | None:
        response = client.get(
            ASHBY_API_URL.format(slug=slug),
            params={"includeCompensation": "true"},
        )
        if response.status_code != 200:
            return None
        payload = self._json_or_none(response)
        jobs = payload.get("jobs") if isinstance(payload, dict) else None
        if isinstance(jobs, list):
            return len([job for job in jobs if isinstance(job, dict) and job.get("isListed", True)])
        return None

    def _json_or_none(self, response: httpx.Response) -> object | None:
        try:
            return response.json()
        except ValueError:
            return None


def resolve_ats_for_firms(
    companies: list[Company],
    config: AppConfig,
    resolver: ATSResolver | None = None,
) -> list[ATSResolution]:
    """Resolve the real ATS for each firm, in input order."""
    active_resolver = resolver or ATSResolver()
    return [active_resolver.resolve(company, config) for company in companies]


__all__ = ["ATSResolution", "ATSResolver", "resolve_ats_for_firms"]
