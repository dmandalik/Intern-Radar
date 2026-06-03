"""Workday ATS collector.

Workday career sites expose a JSON ``cxs`` endpoint that returns paginated job
postings. The endpoint requires three coordinates that are not derivable from a
firm's marketing site:

* ``tenant`` - the Workday tenant id (e.g. ``gresearch``)
* ``datacenter`` - the regional subdomain (e.g. ``wd103``)
* ``site`` - the public career site id (e.g. ``G-Research``)

These are configured per firm via ``ats_tenant`` / ``ats_datacenter`` /
``ats_site`` and may also be parsed from a ``*.myworkdayjobs.com`` careers URL.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from typing import Any
from urllib.parse import urlparse

import httpx

from internradar.core.config import AppConfig
from internradar.core.errors import InvalidConfigError, NetworkError, ParseError, RateLimitedError
from internradar.core.models import Company, RawJob

WORKDAY_JOBS_URL = "https://{tenant}.{datacenter}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"
WORKDAY_DETAIL_BASE = "https://{tenant}.{datacenter}.myworkdayjobs.com/en-US/{site}"
DEFAULT_TIMEOUT_SECONDS = 20.0
DEFAULT_USER_AGENT = "InternRadar/0.1"
DEFAULT_POLITE_DELAY_SECONDS = 0.0
DEFAULT_PAGE_SIZE = 20
MAX_PAGES = 200  # Hard safety stop: 200 * 20 = 4000 postings.
WORKDAY_HOST_PATTERN = re.compile(
    r"^(?P<tenant>[^.]+)\.(?P<datacenter>wd\d+)\.myworkdayjobs\.com$",
    re.IGNORECASE,
)


class WorkdayCollector:
    source_type = "workday"

    def __init__(
        self,
        client: httpx.Client | None = None,
        sleeper: Callable[[float], None] | None = None,
    ) -> None:
        self._client = client
        self._sleeper = sleeper or time.sleep

    def can_collect(self, company: Company) -> bool:
        if (company.ats_type or "").casefold() == self.source_type:
            return True
        return self._coordinates_from_careers_url(company.careers_url) is not None

    def collect(self, company: Company, config: AppConfig) -> list[RawJob]:
        coordinates = self._resolve_coordinates(company)
        if coordinates is None:
            raise InvalidConfigError(
                f"No Workday tenant/datacenter/site is available for company '{company.name}'.",
            )
        tenant, datacenter, site = coordinates

        timeout_seconds = float(config.get("request_timeout_seconds", DEFAULT_TIMEOUT_SECONDS))
        user_agent = str(config.get("user_agent", DEFAULT_USER_AGENT))
        polite_delay_seconds = float(
            config.get("polite_delay_seconds", DEFAULT_POLITE_DELAY_SECONDS),
        )

        owns_client = self._client is None
        client = self._client or httpx.Client(
            headers={
                "User-Agent": user_agent,
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            timeout=timeout_seconds,
            follow_redirects=True,
        )

        jobs_url = WORKDAY_JOBS_URL.format(tenant=tenant, datacenter=datacenter, site=site)
        detail_base = WORKDAY_DETAIL_BASE.format(tenant=tenant, datacenter=datacenter, site=site)

        try:
            raw_jobs: list[RawJob] = []
            seen_paths: set[str] = set()
            offset = 0
            expected_total: int | None = None
            for page_index in range(MAX_PAGES):
                if page_index > 0 and polite_delay_seconds > 0:
                    self._sleeper(polite_delay_seconds)

                body = {
                    "appliedFacets": {},
                    "limit": DEFAULT_PAGE_SIZE,
                    "offset": offset,
                    "searchText": "",
                }
                try:
                    response = client.post(jobs_url, json=body)
                except httpx.TimeoutException as exc:
                    raise NetworkError(
                        f"Timed out while requesting Workday site '{tenant}/{site}'.",
                    ) from exc
                except httpx.HTTPError as exc:
                    raise NetworkError(
                        f"HTTP error while requesting Workday site '{tenant}/{site}': {exc}",
                    ) from exc

                if response.status_code == 429:
                    raise RateLimitedError(
                        f"Workday rate limited requests for site '{tenant}/{site}'.",
                    )
                if response.status_code == 404:
                    raise InvalidConfigError(
                        f"Workday site '{tenant}/{site}' was not found (HTTP 404).",
                    )
                if 400 <= response.status_code < 500:
                    raise InvalidConfigError(
                        f"Workday site '{tenant}/{site}' returned HTTP {response.status_code}.",
                    )
                if response.status_code >= 500:
                    raise NetworkError(
                        f"Workday site '{tenant}/{site}' returned HTTP {response.status_code}.",
                    )

                try:
                    payload = response.json()
                except ValueError as exc:
                    raise ParseError(
                        f"Workday site '{tenant}/{site}' returned invalid JSON.",
                    ) from exc

                if not isinstance(payload, dict):
                    raise ParseError(
                        f"Workday site '{tenant}/{site}' returned an unexpected response shape.",
                    )

                postings = payload.get("jobPostings")
                if not isinstance(postings, list):
                    raise ParseError(
                        f"Workday site '{tenant}/{site}' did not contain a valid jobPostings list.",
                    )

                if not postings:
                    break

                # Workday only reports a meaningful ``total`` on the first page;
                # later pages report ``total=0``. Capture the first positive
                # value as the authoritative target and never treat a later
                # ``0`` as "no more results".
                total = payload.get("total")
                if expected_total is None and isinstance(total, int) and total > 0:
                    expected_total = total

                new_in_page = 0
                for posting in postings:
                    if not isinstance(posting, dict):
                        continue
                    external_path = self._string_or_none(posting.get("externalPath"))
                    dedupe_key = external_path or self._string_or_none(posting.get("title")) or ""
                    if dedupe_key in seen_paths:
                        continue
                    seen_paths.add(dedupe_key)
                    new_in_page += 1
                    raw_jobs.append(self._build_raw_job(company, posting, detail_base))

                offset += DEFAULT_PAGE_SIZE
                # Stop when we have reached the known total, received a short
                # (final) page, or stopped making progress.
                if expected_total is not None and len(raw_jobs) >= expected_total:
                    break
                if len(postings) < DEFAULT_PAGE_SIZE:
                    break
                if new_in_page == 0:
                    break

            return raw_jobs
        finally:
            if owns_client:
                client.close()

    def _resolve_coordinates(self, company: Company) -> tuple[str, str, str] | None:
        tenant = self._string_or_none(company.ats_tenant)
        datacenter = self._string_or_none(company.ats_datacenter)
        site = self._string_or_none(company.ats_site)
        if tenant and datacenter and site:
            return tenant, datacenter, site

        return self._coordinates_from_careers_url(company.careers_url)

    def _coordinates_from_careers_url(self, careers_url: str | None) -> tuple[str, str, str] | None:
        if not careers_url:
            return None
        parsed = urlparse(careers_url)
        match = WORKDAY_HOST_PATTERN.match(parsed.netloc)
        if not match:
            return None
        path_parts = [part for part in parsed.path.split("/") if part]
        # URL shapes: /{site} or /en-US/{site} or /wday/cxs/{tenant}/{site}/jobs
        site: str | None = None
        if "cxs" in path_parts:
            cxs_index = path_parts.index("cxs")
            if len(path_parts) > cxs_index + 2:
                site = path_parts[cxs_index + 2]
        elif path_parts:
            site = path_parts[-1] if not path_parts[-1].lower().startswith("en") else (
                path_parts[-2] if len(path_parts) >= 2 else path_parts[-1]
            )
            if len(path_parts) == 1:
                site = path_parts[0]
            else:
                # Skip locale segments like en-US.
                non_locale = [part for part in path_parts if not re.fullmatch(r"[a-z]{2}-[A-Z]{2}", part)]
                site = non_locale[0] if non_locale else path_parts[-1]
        if not site:
            return None
        return match.group("tenant"), match.group("datacenter"), site

    def _build_raw_job(
        self,
        company: Company,
        posting: dict[str, Any],
        detail_base: str,
    ) -> RawJob:
        title = self._string_or_none(posting.get("title")) or "Unknown job"
        external_path = self._string_or_none(posting.get("externalPath")) or ""
        job_url = f"{detail_base}{external_path}" if external_path else detail_base
        location_raw = self._string_or_none(posting.get("locationsText"))

        return RawJob(
            source_type=self.source_type,
            source_name="Workday",
            company_id=company.id,
            company_name=company.name,
            title=title,
            url=job_url,
            apply_url=job_url,
            location_raw=location_raw,
            description_raw=None,
            department=None,
            posted_at=None,
            raw_payload=posting,
        )

    def _string_or_none(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None
