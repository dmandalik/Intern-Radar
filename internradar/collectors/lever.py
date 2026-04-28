"""Lever ATS collector."""

from __future__ import annotations

import re
import time
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

import httpx

from internradar.core.config import AppConfig
from internradar.core.errors import InvalidConfigError, NetworkError, ParseError, RateLimitedError
from internradar.core.models import Company, RawJob

LEVER_API_URL = "https://api.lever.co/v0/postings/{slug}"
DEFAULT_TIMEOUT_SECONDS = 20.0
DEFAULT_USER_AGENT = "InternRadar/0.1"
DEFAULT_POLITE_DELAY_SECONDS = 0.0
SAFE_SLUG_PATTERN = re.compile(r"[^a-z0-9]+")


class LeverCollector:
    source_type = "lever"

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
                f"No Lever slug is available for company '{company.name}'.",
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
                        LEVER_API_URL.format(slug=slug),
                        params={"mode": "json"},
                    )
                except httpx.TimeoutException as exc:
                    raise NetworkError(
                        f"Timed out while requesting Lever board '{slug}'.",
                    ) from exc
                except httpx.HTTPError as exc:
                    raise NetworkError(
                        f"HTTP error while requesting Lever board '{slug}': {exc}",
                    ) from exc

                if response.status_code == 404:
                    last_not_found_slug = slug
                    continue
                if response.status_code == 429:
                    raise RateLimitedError(
                        f"Lever rate limited requests for board '{slug}'.",
                    )
                if 400 <= response.status_code < 500:
                    raise InvalidConfigError(
                        f"Lever board '{slug}' returned HTTP {response.status_code}.",
                    )
                if response.status_code >= 500:
                    raise NetworkError(
                        f"Lever board '{slug}' returned HTTP {response.status_code}.",
                    )

                try:
                    payload = response.json()
                except ValueError as exc:
                    raise ParseError(
                        f"Lever board '{slug}' returned invalid JSON.",
                    ) from exc

                if not isinstance(payload, list):
                    raise ParseError(
                        f"Lever board '{slug}' returned an unexpected response shape.",
                    )

                return [self._build_raw_job(company, slug, posting) for posting in payload]

            raise InvalidConfigError(
                f"Lever board was not found for company '{company.name}'"
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
        if "lever.co" not in parsed.netloc.casefold():
            return None

        path_parts = [part for part in parsed.path.split("/") if part]
        if path_parts:
            return path_parts[0].strip() or None

        return None

    def _build_raw_job(self, company: Company, slug: str, posting: Any) -> RawJob:
        if not isinstance(posting, dict):
            raise ParseError("Lever posting entry must be an object.")

        title = str(posting.get("text") or f"Posting {posting.get('id') or ''}").strip() or "Unknown job"
        hosted_url = posting.get("hostedUrl")
        fallback_url = (
            f"https://jobs.lever.co/{slug}/{posting['id']}"
            if posting.get("id") is not None
            else LEVER_API_URL.format(slug=slug)
        )
        job_url = str(hosted_url or fallback_url)

        categories = posting.get("categories")
        if not isinstance(categories, dict):
            categories = {}

        location_raw = self._string_or_none(categories.get("location"))
        department = self._string_or_none(categories.get("team"))
        description_raw = self._build_description(posting)
        posted_at = self._parse_created_at(posting.get("createdAt"))

        apply_url = self._string_or_none(posting.get("applyUrl")) or job_url

        return RawJob(
            source_type=self.source_type,
            source_name="Lever",
            company_id=company.id,
            company_name=company.name,
            title=title,
            url=job_url,
            apply_url=apply_url,
            location_raw=location_raw,
            description_raw=description_raw,
            department=department,
            posted_at=posted_at,
            raw_payload=posting,
        )

    def _build_description(self, posting: dict[str, Any]) -> str | None:
        plain_sections = [
            self._string_or_none(posting.get("descriptionPlain")),
            self._string_or_none(posting.get("additionalPlain")),
        ]
        plain_sections.extend(self._extract_list_sections(posting.get("lists")))
        plain_sections = [section for section in plain_sections if section]
        if plain_sections:
            return "\n\n".join(plain_sections)

        fallback_sections = [
            self._string_or_none(posting.get("description")),
            self._string_or_none(posting.get("additional")),
        ]
        fallback_sections.extend(self._extract_list_sections(posting.get("lists")))
        fallback_sections = [section for section in fallback_sections if section]
        if fallback_sections:
            return "\n\n".join(fallback_sections)

        return None

    def _extract_list_sections(self, lists_value: Any) -> list[str]:
        if not isinstance(lists_value, list):
            return []

        sections: list[str] = []
        for item in lists_value:
            if not isinstance(item, dict):
                continue

            text = self._string_or_none(item.get("text"))
            content = item.get("content")
            content_parts: list[str] = []

            if isinstance(content, list):
                content_parts = [str(entry).strip() for entry in content if str(entry).strip()]
            elif self._string_or_none(content):
                content_parts = [self._string_or_none(content) or ""]

            pieces = [piece for piece in [text, "\n".join(content_parts) if content_parts else None] if piece]
            if pieces:
                sections.append("\n".join(pieces))

        return sections

    def _parse_created_at(self, value: Any) -> datetime | None:
        if value is None:
            return None

        try:
            timestamp_ms = int(value)
        except (TypeError, ValueError):
            return None

        try:
            return datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC)
        except (OverflowError, OSError, ValueError):
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
