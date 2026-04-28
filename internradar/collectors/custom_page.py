"""Conservative fallback collector for public career pages."""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from internradar.core.config import AppConfig
from internradar.core.errors import InvalidConfigError, NetworkError, ParseError, RateLimitedError
from internradar.core.models import Company, RawJob

DEFAULT_TIMEOUT_SECONDS = 20.0
DEFAULT_USER_AGENT = "InternRadar/0.1"
DEFAULT_POLITE_DELAY_SECONDS = 0.0
DEFAULT_MAX_DEPTH = 1
DEFAULT_MAX_PAGES_PER_COMPANY = 20

POSITIVE_KEYWORDS = (
    "job",
    "jobs",
    "career",
    "careers",
    "intern",
    "internship",
    "student",
    "students",
    "university",
    "campus",
    "early-career",
    "earlycareers",
    "graduate",
    "grads",
    "open-roles",
    "positions",
    "software",
    "engineering",
    "trading",
    "quant",
    "research",
)
NEGATIVE_KEYWORDS = (
    "login",
    "signin",
    "sign-in",
    "account",
    "privacy",
    "terms",
    "cookie",
    "cookies",
    "blog",
    "news",
    "press",
    "about",
    "contact",
    "linkedin",
    "facebook",
    "twitter",
    "instagram",
)
JOB_SIGNALS = (
    "intern",
    "internship",
    "software engineer",
    "engineer intern",
    "trading systems",
    "quant developer",
    "quantitative developer",
    "low latency",
    "fpga",
    "market data",
    "infrastructure",
    "research engineer",
    "summer",
    "winter",
    "fall",
    "2026",
    "2027",
    "2028",
    "new york",
    "chicago",
    "london",
)
APPLY_SIGNALS = ("apply", "apply now", "submit application")
LOCATION_PATTERNS = (
    "New York, NY",
    "New York",
    "Chicago, IL",
    "Chicago",
    "London",
    "Remote",
    "Austin",
    "Boston",
    "Singapore",
    "Amsterdam",
)


@dataclass(slots=True)
class CandidateLink:
    url: str
    anchor_text: str | None
    matched_keywords: list[str]
    score: int
    depth: int
    source_url: str


class CustomPageCollector:
    source_type = "custom_page"

    def __init__(
        self,
        client: httpx.Client | None = None,
        sleeper: Callable[[float], None] | None = None,
    ) -> None:
        self._client = client
        self._sleeper = sleeper or time.sleep

    def can_collect(self, company: Company) -> bool:
        if not company.careers_url:
            return False

        ats_type = (company.ats_type or "").casefold()
        return ats_type in ("", "custom", "unknown")

    def collect(self, company: Company, config: AppConfig) -> list[RawJob]:
        careers_url = company.careers_url
        if not careers_url:
            raise InvalidConfigError(
                f"No careers URL is available for company '{company.name}'.",
            )

        timeout_seconds = float(config.get("request_timeout_seconds", DEFAULT_TIMEOUT_SECONDS))
        user_agent = str(config.get("user_agent", DEFAULT_USER_AGENT))
        polite_delay_seconds = float(
            config.get("polite_delay_seconds", DEFAULT_POLITE_DELAY_SECONDS),
        )
        max_depth = int(config.get("max_depth", DEFAULT_MAX_DEPTH))
        max_pages = int(config.get("max_pages_per_company", DEFAULT_MAX_PAGES_PER_COMPANY))

        if max_pages < 1:
            raise InvalidConfigError("max_pages_per_company must be at least 1.")

        owns_client = self._client is None
        client = self._client or httpx.Client(
            headers={"User-Agent": user_agent},
            timeout=timeout_seconds,
            follow_redirects=True,
        )

        try:
            visited: set[str] = set()
            pages_fetched = 0
            jobs: list[RawJob] = []

            root_html = self._fetch_html(client, careers_url)
            visited.add(careers_url)
            pages_fetched += 1

            root_page = self._parse_page(root_html, careers_url)
            root_job = self._page_to_job(
                company=company,
                page=root_page,
                depth=0,
                source_url=careers_url,
                anchor_text=None,
                candidate_score=0,
                matched_keywords=[],
            )
            if root_job:
                jobs.append(root_job)

            if max_depth < 1 or pages_fetched >= max_pages:
                return jobs

            candidates = self._extract_candidate_links(root_page.soup, careers_url)
            for candidate in candidates:
                if pages_fetched >= max_pages:
                    break
                if candidate.url in visited:
                    continue

                if polite_delay_seconds > 0:
                    self._sleeper(polite_delay_seconds)

                try:
                    html = self._fetch_html(client, candidate.url)
                except InvalidConfigError:
                    continue

                visited.add(candidate.url)
                pages_fetched += 1

                page = self._parse_page(html, candidate.url)
                job = self._page_to_job(
                    company=company,
                    page=page,
                    depth=candidate.depth,
                    source_url=candidate.source_url,
                    anchor_text=candidate.anchor_text,
                    candidate_score=candidate.score,
                    matched_keywords=candidate.matched_keywords,
                )
                if job:
                    jobs.append(job)

            return jobs
        finally:
            if owns_client:
                client.close()

    def _fetch_html(self, client: httpx.Client, url: str) -> str:
        try:
            response = client.get(url)
        except httpx.TimeoutException as exc:
            raise NetworkError(f"Timed out while requesting custom careers page '{url}'.") from exc
        except httpx.HTTPError as exc:
            raise NetworkError(f"HTTP error while requesting custom careers page '{url}': {exc}") from exc

        if response.status_code == 404:
            raise InvalidConfigError(f"Custom careers page '{url}' returned HTTP 404.")
        if response.status_code == 429:
            raise RateLimitedError(f"Custom careers page '{url}' returned HTTP 429.")
        if 400 <= response.status_code < 500:
            raise InvalidConfigError(f"Custom careers page '{url}' returned HTTP {response.status_code}.")
        if response.status_code >= 500:
            raise NetworkError(f"Custom careers page '{url}' returned HTTP {response.status_code}.")

        content_type = response.headers.get("content-type", "").casefold()
        if content_type and "html" not in content_type and "xml" not in content_type:
            raise ParseError(f"Custom careers page '{url}' did not return HTML content.")

        return response.text

    def _parse_page(self, html: str, page_url: str) -> ParsedPage:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        title_tag = soup.find("title")
        page_title = self._clean_text(title_tag.get_text(" ", strip=True)) if title_tag else None
        visible_text = self._clean_text(soup.get_text(" ", strip=True))
        return ParsedPage(url=page_url, soup=soup, title=page_title, text=visible_text)

    def _extract_candidate_links(self, soup: BeautifulSoup, page_url: str) -> list[CandidateLink]:
        parsed_root = urlparse(page_url)
        candidates: list[CandidateLink] = []
        seen: set[str] = set()

        for anchor in soup.find_all("a", href=True):
            href = anchor.get("href")
            if not href:
                continue

            absolute_url = urljoin(page_url, href)
            normalized_url = absolute_url.split("#", 1)[0]
            if not normalized_url or normalized_url in seen:
                continue

            parsed_candidate = urlparse(normalized_url)
            if parsed_candidate.scheme not in ("http", "https"):
                continue
            if parsed_candidate.netloc != parsed_root.netloc:
                continue

            anchor_text = self._clean_text(anchor.get_text(" ", strip=True))
            scoring_text = " ".join(
                piece for piece in [normalized_url, anchor_text] if piece
            ).casefold()

            if any(keyword in scoring_text for keyword in NEGATIVE_KEYWORDS):
                continue

            matched_keywords = [keyword for keyword in POSITIVE_KEYWORDS if keyword in scoring_text]
            if not matched_keywords:
                continue

            seen.add(normalized_url)
            candidates.append(
                CandidateLink(
                    url=normalized_url,
                    anchor_text=anchor_text or None,
                    matched_keywords=matched_keywords,
                    score=len(matched_keywords),
                    depth=1,
                    source_url=page_url,
                ),
            )

        return sorted(candidates, key=lambda candidate: (-candidate.score, candidate.url))

    def _page_to_job(
        self,
        company: Company,
        page: ParsedPage,
        depth: int,
        source_url: str,
        anchor_text: str | None,
        candidate_score: int,
        matched_keywords: list[str],
    ) -> RawJob | None:
        title = self._detect_title(page.soup, page.title, anchor_text)
        if not title:
            return None

        matched = self._matched_job_keywords(title, page.text, page.url, anchor_text)
        if not matched:
            return None

        description_raw = page.text or None
        apply_url = self._detect_apply_url(page.soup, page.url)
        location_raw = self._detect_location(page.text)
        department = self._detect_department(page.text)

        return RawJob(
            source_type=self.source_type,
            source_name="Custom Career Page",
            company_id=company.id,
            company_name=company.name,
            title=title,
            url=page.url,
            apply_url=apply_url,
            location_raw=location_raw,
            description_raw=description_raw,
            department=department,
            raw_payload={
                "page_title": page.title,
                "source_url": source_url,
                "matched_keywords": matched,
                "depth": depth,
                "anchor_text": anchor_text,
                "candidate_score": candidate_score,
            },
        )

    def _detect_title(
        self,
        soup: BeautifulSoup,
        page_title: str | None,
        anchor_text: str | None,
    ) -> str | None:
        for tag_name in ("h1", "h2"):
            heading = soup.find(tag_name)
            if heading:
                text = self._clean_text(heading.get_text(" ", strip=True))
                if text:
                    return text

        for candidate in (page_title, anchor_text):
            if candidate:
                cleaned = self._clean_text(candidate)
                if cleaned:
                    return cleaned

        return None

    def _matched_job_keywords(
        self,
        title: str,
        text: str,
        url: str,
        anchor_text: str | None,
    ) -> list[str]:
        haystack = " ".join(piece for piece in [title, text, url, anchor_text] if piece).casefold()
        return [keyword for keyword in JOB_SIGNALS if keyword in haystack]

    def _detect_apply_url(self, soup: BeautifulSoup, page_url: str) -> str | None:
        for anchor in soup.find_all("a", href=True):
            href = anchor.get("href")
            if not href:
                continue

            text = self._clean_text(anchor.get_text(" ", strip=True))
            haystack = " ".join(piece for piece in [text, href] if piece).casefold()
            if any(signal in haystack for signal in APPLY_SIGNALS):
                return urljoin(page_url, href).split("#", 1)[0]

        return None

    def _detect_location(self, text: str) -> str | None:
        lowered = text.casefold()
        for location in LOCATION_PATTERNS:
            if location.casefold() in lowered:
                return location
        return None

    def _detect_department(self, text: str) -> str | None:
        match = re.search(r"department:\s*([A-Za-z &/-]+)", text, flags=re.IGNORECASE)
        if match:
            return self._clean_text(match.group(1))
        return None

    def _clean_text(self, value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()


@dataclass(slots=True)
class ParsedPage:
    url: str
    soup: BeautifulSoup
    title: str | None
    text: str
