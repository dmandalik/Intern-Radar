"""Greenhouse ATS collector."""

from __future__ import annotations

import re
import time
from collections.abc import Callable, Iterable
from datetime import datetime
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx

from internradar.core.config import AppConfig
from internradar.core.errors import InvalidConfigError, NetworkError, ParseError, RateLimitedError
from internradar.core.models import Company, RawJob

GREENHOUSE_API_URL = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
DEFAULT_TIMEOUT_SECONDS = 20.0
DEFAULT_USER_AGENT = "InternRadar/0.1"
DEFAULT_POLITE_DELAY_SECONDS = 0.0
SAFE_SLUG_PATTERN = re.compile(r"[^a-z0-9]+")


class GreenhouseCollector:
    source_type = "greenhouse"

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
        return self._extract_slug_from_careers_url(company.careers_url) is not None

    def collect(self, company: Company, config: AppConfig) -> list[RawJob]:
        slug_candidates = self.candidate_slugs(company)
        if not slug_candidates:
            raise InvalidConfigError(
                f"No Greenhouse slug is available for company '{company.name}'.",
            )

        timeout_seconds = float(config.get("request_timeout_seconds", DEFAULT_TIMEOUT_SECONDS))
        user_agent = str(config.get("user_agent", DEFAULT_USER_AGENT))
        polite_delay_seconds = float(
            config.get("polite_delay_seconds", DEFAULT_POLITE_DELAY_SECONDS),
        )

        owns_client = self._client is None
        client = self._client or httpx.Client(
            headers={"User-Agent": user_agent},
            timeout=timeout_seconds,
            follow_redirects=True,
        )

        try:
            last_not_found_slug: str | None = None
            for index, slug in enumerate(slug_candidates):
                if index > 0 and polite_delay_seconds > 0:
                    self._sleeper(polite_delay_seconds)

                try:
                    response = client.get(
                        GREENHOUSE_API_URL.format(slug=slug),
                        params={"content": "true"},
                    )
                except httpx.TimeoutException as exc:
                    raise NetworkError(
                        f"Timed out while requesting Greenhouse board '{slug}'.",
                    ) from exc
                except httpx.HTTPError as exc:
                    raise NetworkError(
                        f"HTTP error while requesting Greenhouse board '{slug}': {exc}",
                    ) from exc

                if response.status_code == 404:
                    last_not_found_slug = slug
                    continue
                if response.status_code == 429:
                    raise RateLimitedError(
                        f"Greenhouse rate limited requests for board '{slug}'.",
                    )
                if 400 <= response.status_code < 500:
                    raise InvalidConfigError(
                        f"Greenhouse board '{slug}' returned HTTP {response.status_code}.",
                    )
                if response.status_code >= 500:
                    raise NetworkError(
                        f"Greenhouse board '{slug}' returned HTTP {response.status_code}.",
                    )

                try:
                    payload = response.json()
                except ValueError as exc:
                    raise ParseError(
                        f"Greenhouse board '{slug}' returned invalid JSON.",
                    ) from exc

                if not isinstance(payload, dict):
                    raise ParseError(
                        f"Greenhouse board '{slug}' returned an unexpected response shape.",
                    )

                jobs = payload.get("jobs")
                if not isinstance(jobs, list):
                    raise ParseError(
                        f"Greenhouse board '{slug}' did not contain a valid jobs list.",
                    )

                return [self._build_raw_job(company, slug, job) for job in jobs]

            raise InvalidConfigError(
                f"Greenhouse board was not found for company '{company.name}'"
                + (f" using slug '{last_not_found_slug}'." if last_not_found_slug else "."),
            )
        finally:
            if owns_client:
                client.close()

    def candidate_slugs(self, company: Company) -> list[str]:
        candidates: list[str] = []

        if company.ats_slug:
            candidates.append(company.ats_slug.strip())

        careers_slug = self._extract_slug_from_careers_url(company.careers_url)
        if careers_slug:
            candidates.append(careers_slug)

        if not candidates:
            candidates.extend(self._infer_candidate_slugs(company))

        return self._dedupe_non_empty(candidates)

    def _infer_candidate_slugs(self, company: Company) -> list[str]:
        candidates: list[str] = []
        candidates.extend(self._slug_forms(company.name))

        for alias in company.aliases:
            normalized = self._normalize_slug_piece(alias)
            compact = normalized.replace("-", "")
            if len(compact) < 3:
                continue
            candidates.append(compact)

        return candidates[:5]

    def _slug_forms(self, value: str) -> list[str]:
        normalized = self._normalize_slug_piece(value)
        if not normalized:
            return []

        compact = normalized.replace("-", "")
        forms = [compact]
        if "-" in normalized:
            forms.append(normalized)
        return forms

    def _normalize_slug_piece(self, value: str) -> str:
        normalized = SAFE_SLUG_PATTERN.sub("-", value.casefold()).strip("-")
        normalized = re.sub(r"-{2,}", "-", normalized)
        return normalized

    def _extract_slug_from_careers_url(self, careers_url: str | None) -> str | None:
        if not careers_url:
            return None

        parsed = urlparse(careers_url)
        if "greenhouse.io" not in parsed.netloc.casefold():
            return None

        query_values = parse_qs(parsed.query)
        if "for" in query_values and query_values["for"]:
            return query_values["for"][0].strip() or None

        path_parts = [part for part in parsed.path.split("/") if part]
        if path_parts:
            return path_parts[0].strip() or None

        return None

    def _build_raw_job(self, company: Company, slug: str, job: Any) -> RawJob:
        if not isinstance(job, dict):
            raise ParseError("Greenhouse job entry must be an object.")

        title = str(job.get("title") or f"Job {job.get('id') or ''}").strip() or "Unknown job"
        absolute_url = job.get("absolute_url")
        fallback_url = (
            f"https://boards.greenhouse.io/{slug}/jobs/{job['id']}"
            if job.get("id") is not None
            else GREENHOUSE_API_URL.format(slug=slug)
        )
        job_url = absolute_url or fallback_url

        location_name = None
        location = job.get("location")
        if isinstance(location, dict):
            raw_location = location.get("name")
            if raw_location:
                location_name = str(raw_location)

        departments = job.get("departments")
        department_name = self._department_name(departments)

        posted_at = self._parse_datetime(job.get("updated_at"))

        return RawJob(
            source_type=self.source_type,
            source_name="Greenhouse",
            company_id=company.id,
            company_name=company.name,
            title=title,
            url=str(job_url),
            apply_url=str(absolute_url or job_url),
            location_raw=location_name,
            description_raw=str(job["content"]) if job.get("content") is not None else None,
            department=department_name,
            posted_at=posted_at,
            raw_payload=job,
        )

    def _department_name(self, departments: Any) -> str | None:
        if not isinstance(departments, list):
            return None

        names = [
            str(item.get("name")).strip()
            for item in departments
            if isinstance(item, dict) and item.get("name")
        ]
        return ", ".join(names) if names else None

    def _parse_datetime(self, value: Any) -> datetime | None:
        if not value or not isinstance(value, str):
            return None

        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    def _dedupe_non_empty(self, values: Iterable[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()

        for value in values:
            cleaned = value.strip()
            if not cleaned:
                continue
            lowered = cleaned.casefold()
            if lowered in seen:
                continue
            seen.add(lowered)
            deduped.append(cleaned)

        return deduped
