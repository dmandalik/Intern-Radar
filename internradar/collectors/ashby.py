"""Ashby ATS collector."""

from __future__ import annotations

import re
import time
from collections.abc import Callable, Iterable
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

import httpx

from internradar.core.config import AppConfig
from internradar.core.errors import InvalidConfigError, NetworkError, ParseError, RateLimitedError
from internradar.core.models import Company, RawJob

ASHBY_API_URL = "https://api.ashbyhq.com/posting-api/job-board/{slug}"
DEFAULT_TIMEOUT_SECONDS = 20.0
DEFAULT_USER_AGENT = "InternRadar/0.1"
DEFAULT_POLITE_DELAY_SECONDS = 0.0
SAFE_SLUG_PATTERN = re.compile(r"[^a-z0-9]+")


class AshbyCollector:
    source_type = "ashby"

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
                f"No Ashby slug is available for company '{company.name}'.",
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
                        ASHBY_API_URL.format(slug=slug),
                        params={"includeCompensation": "true"},
                    )
                except httpx.TimeoutException as exc:
                    raise NetworkError(
                        f"Timed out while requesting Ashby board '{slug}'.",
                    ) from exc
                except httpx.HTTPError as exc:
                    raise NetworkError(
                        f"HTTP error while requesting Ashby board '{slug}': {exc}",
                    ) from exc

                if response.status_code == 404:
                    last_not_found_slug = slug
                    continue
                if response.status_code == 429:
                    raise RateLimitedError(
                        f"Ashby rate limited requests for board '{slug}'.",
                    )
                if 400 <= response.status_code < 500:
                    raise InvalidConfigError(
                        f"Ashby board '{slug}' returned HTTP {response.status_code}.",
                    )
                if response.status_code >= 500:
                    raise NetworkError(
                        f"Ashby board '{slug}' returned HTTP {response.status_code}.",
                    )

                try:
                    payload = response.json()
                except ValueError as exc:
                    raise ParseError(
                        f"Ashby board '{slug}' returned invalid JSON.",
                    ) from exc

                if not isinstance(payload, dict):
                    raise ParseError(
                        f"Ashby board '{slug}' returned an unexpected response shape.",
                    )

                jobs = payload.get("jobs")
                if not isinstance(jobs, list):
                    raise ParseError(
                        f"Ashby board '{slug}' did not contain a valid jobs list.",
                    )

                return [
                    self._build_raw_job(company, slug, job)
                    for job in jobs
                    if isinstance(job, dict) and job.get("isListed", True)
                ]

            raise InvalidConfigError(
                f"Ashby board was not found for company '{company.name}'"
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
        if "ashbyhq.com" not in parsed.netloc.casefold():
            return None

        path_parts = [part for part in parsed.path.split("/") if part]
        if path_parts:
            return path_parts[0].strip() or None

        return None

    def _build_raw_job(self, company: Company, slug: str, job: dict[str, Any]) -> RawJob:
        title = str(job.get("title") or "Unknown job").strip() or "Unknown job"
        job_url = self._string_or_none(job.get("jobUrl")) or ASHBY_API_URL.format(slug=slug)
        apply_url = self._string_or_none(job.get("applyUrl")) or job_url

        location_raw = self._build_location(job)
        department = self._string_or_none(job.get("department")) or self._string_or_none(job.get("team"))
        description_raw = self._string_or_none(job.get("descriptionPlain")) or self._string_or_none(
            job.get("descriptionHtml"),
        )
        posted_at = self._parse_datetime(job.get("publishedAt"))

        return RawJob(
            source_type=self.source_type,
            source_name="Ashby",
            company_id=company.id,
            company_name=company.name,
            title=title,
            url=job_url,
            apply_url=apply_url,
            location_raw=location_raw,
            description_raw=description_raw,
            department=department,
            posted_at=posted_at,
            raw_payload=job,
        )

    def _build_location(self, job: dict[str, Any]) -> str | None:
        names: list[str] = []
        primary = self._string_or_none(job.get("location"))
        if primary:
            names.append(primary)
        secondary = job.get("secondaryLocations")
        if isinstance(secondary, list):
            for item in secondary:
                if isinstance(item, dict):
                    value = self._string_or_none(item.get("location"))
                    if value and value not in names:
                        names.append(value)
        return ", ".join(names) if names else None

    def _parse_datetime(self, value: Any) -> datetime | None:
        if not value or not isinstance(value, str):
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    def _string_or_none(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

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
