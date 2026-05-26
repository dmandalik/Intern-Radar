"""High-precision fallback collector for public custom career pages."""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field, fields
from typing import Any, Literal
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup, Tag

from internradar.core.config import AppConfig
from internradar.core.errors import InvalidConfigError, NetworkError, ParseError, RateLimitedError
from internradar.core.models import Company, RawJob

DEFAULT_TIMEOUT_SECONDS = 20.0
DEFAULT_USER_AGENT = "InternRadar/0.1"
DEFAULT_POLITE_DELAY_SECONDS = 0.0
DEFAULT_MAX_DEPTH = 1
DEFAULT_MAX_PAGES_PER_COMPANY = 20

PageClassification = Literal[
    "job_detail",
    "job_listing",
    "program_editorial",
    "future_opportunity",
    "generic_homepage",
]

STATUS_HINTS = Literal["open", "coming_soon", "closed", "unknown"]

ROLE_SIGNAL_TERMS = (
    "intern",
    "internship",
    "engineer",
    "engineering",
    "developer",
    "analyst",
    "researcher",
    "research",
    "scientist",
    "trader",
    "trading",
    "quant",
    "quantitative",
    "software",
    "market data",
    "infrastructure",
    "systems",
    "backend",
    "hardware",
    "fpga",
    "machine learning",
    "data analyst",
    "data engineer",
)
GENERIC_DISCOVERY_TERMS = (
    "careers",
    "career",
    "jobs",
    "job openings",
    "students and graduates",
    "students & graduates",
    "student opportunities",
    "programs",
    "our opportunities",
)
GENERIC_PAGE_TERMS = (
    "how we hire",
    "recruitment process",
    "talent community",
    "join our team",
    "life at",
    "work at",
    "who we are",
    "about hrt",
    "join a community guided by",
    "find your role",
    "grow with us",
    "opportunities for early talent",
    "full-time & internship opportunities",
    "built by coders",
    "a place where kindness and excellence converge",
    "team",
    "engineering team",
    "tech blog",
    "future opportunities",
)
NEGATIVE_LINK_TERMS = (
    "privacy",
    "terms",
    "cookies",
    "blog",
    "news",
    "press",
    "contact",
    "linkedin",
    "facebook",
    "twitter",
    "instagram",
    "login",
    "sign in",
    "sign-in",
    "account",
)
EXACT_GENERIC_TITLES = {
    "internship",
    "internships",
    "careers",
    "career opportunities",
    "student opportunities",
    "students and graduates",
    "students & graduates",
    "our opportunities",
}
MARKETING_TITLE_PREFIXES = (
    "join ",
    "discover ",
    "explore ",
    "learn ",
    "welcome ",
    "work where",
)
APPLY_TERMS = ("apply", "apply now", "submit application", "apply here", "express interest")
CLOSED_TERMS = (
    "applications are closed",
    "position has been filled",
    "vacancy has been filled",
    "no longer available",
    "no longer accepting applications",
    "job not found",
    "posting has expired",
    "this job is closed",
    "this vacancy has been filled",
)
COMING_SOON_TERMS = (
    "check back next year",
    "check back soon",
    "applications will open",
    "join our talent community",
    "join here",
    "not currently accepting applications",
)
FUTURE_OPPORTUNITY_PATH_HINTS = (
    "/future-opportunities",
    "/talent-community",
    "/talentcommunity",
)
GENERIC_SECTION_SEGMENTS = {
    "",
    "careers",
    "search-careers",
    "career",
    "jobs",
    "job",
    "students-graduates",
    "students-and-graduates",
    "student-opportunities",
    "internships",
    "programs",
    "teams",
    "team",
    "engineering",
    "future-opportunities",
    "talent-community",
    "recruitment-process",
    "about",
}
DIRECT_DETAIL_PATH_PATTERNS = (
    "/job/",
    "/jobs/",
    "/positions/",
    "/vacancies/",
    "/hrt-job/",
)
LOCATION_TOKENS = (
    "new york, ny",
    "new york city",
    "new york",
    "nyc",
    "london",
    "singapore",
    "chicago, il",
    "chicago",
    "remote",
    "austin",
    "boston",
    "amsterdam",
)
SEASON_PATTERN = re.compile(r"\b(summer|winter|fall|spring)\s+20\d{2}\b", flags=re.IGNORECASE)
YEAR_PATTERN = re.compile(r"\b20\d{2}\b")
WHITESPACE_PATTERN = re.compile(r"\s+")
NON_WORD_PATTERN = re.compile(r"[^a-z0-9]+")

STOPWORDS = {
    "a",
    "an",
    "and",
    "at",
    "for",
    "in",
    "of",
    "on",
    "our",
    "the",
    "to",
    "with",
    "your",
}


@dataclass(slots=True)
class ResolvedPage:
    requested_url: str
    final_url: str
    status_code: int
    content_type: str
    soup: BeautifulSoup
    page_title: str | None
    visible_text: str
    redirected: bool
    json_ld_job_postings: list[dict[str, Any]]


@dataclass(slots=True)
class ExtractedRoleCandidate:
    title: str
    source_url: str
    apply_url: str | None
    description: str | None
    location_raw: str | None
    season_hint: str | None
    status_hint: STATUS_HINTS
    block_text: str
    evidence: list[str] = field(default_factory=list)
    adapter_name: str | None = None
    confidence: float = 0.0
    page_type: PageClassification = "job_detail"
    extracted_from: str = "detail_page"
    title_source: str = "heading"
    block_anchor_text: str | None = None
    matched_keywords: list[str] = field(default_factory=list)
    requested_url: str | None = None
    final_url: str | None = None
    status_evidence: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ContainerCandidate:
    container: Tag
    anchor: Tag | None
    title: str
    anchor_text: str | None


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
            raise InvalidConfigError(f"No careers URL is available for company '{company.name}'.")

        timeout_seconds = float(config.get("request_timeout_seconds", DEFAULT_TIMEOUT_SECONDS))
        user_agent = str(config.get("user_agent", DEFAULT_USER_AGENT))
        polite_delay_seconds = float(config.get("polite_delay_seconds", DEFAULT_POLITE_DELAY_SECONDS))
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
            cache: dict[str, ResolvedPage] = {}
            root_page = self._load_page(client, careers_url, cache=cache, strict=True)
            pages_fetched = 1
            pages_to_process = [root_page]
            discovered_pages, discovered_fetches = self._discover_seed_pages(
                client,
                root_page,
                cache=cache,
                pages_remaining=max_pages - pages_fetched,
                polite_delay_seconds=polite_delay_seconds,
            )
            pages_fetched += discovered_fetches
            pages_to_process.extend(discovered_pages)
            jobs: list[RawJob] = []
            seen_job_keys: set[tuple[str, str]] = set()

            for page in pages_to_process:
                page_candidates = self._extract_candidates_from_page(page, current_depth=0)
                for candidate in self._dedupe_candidates(page_candidates):
                    verified, extra_fetches = self._verify_candidate(
                        client,
                        candidate,
                        parent_page=page,
                        cache=cache,
                        max_depth=max_depth,
                        current_depth=0,
                        pages_remaining=max_pages - pages_fetched,
                        polite_delay_seconds=polite_delay_seconds,
                    )
                    pages_fetched += extra_fetches
                    if verified is None:
                        continue
                    raw_job = self._candidate_to_raw_job(company, verified)
                    key = (raw_job.title.casefold(), raw_job.url)
                    if key in seen_job_keys:
                        continue
                    seen_job_keys.add(key)
                    jobs.append(raw_job)
                    if pages_fetched >= max_pages:
                        break

            return jobs
        finally:
            if owns_client:
                client.close()

    def _load_page(
        self,
        client: httpx.Client,
        url: str,
        *,
        cache: dict[str, ResolvedPage],
        strict: bool,
    ) -> ResolvedPage:
        cached = cache.get(url)
        if cached is not None:
            return cached

        try:
            response = client.get(url)
        except httpx.TimeoutException as exc:
            raise NetworkError(f"Timed out while requesting custom careers page '{url}'.") from exc
        except httpx.HTTPError as exc:
            raise NetworkError(f"HTTP error while requesting custom careers page '{url}': {exc}") from exc

        if response.status_code == 429:
            raise RateLimitedError(f"Custom careers page '{url}' returned HTTP 429.")
        if strict and response.status_code == 404:
            raise InvalidConfigError(f"Custom careers page '{url}' returned HTTP 404.")
        if strict and 400 <= response.status_code < 500:
            raise InvalidConfigError(f"Custom careers page '{url}' returned HTTP {response.status_code}.")
        if strict and response.status_code >= 500:
            raise NetworkError(f"Custom careers page '{url}' returned HTTP {response.status_code}.")

        content_type = response.headers.get("content-type", "").casefold()
        if content_type and "html" not in content_type and "xml" not in content_type:
            if strict:
                raise ParseError(f"Custom careers page '{url}' did not return HTML content.")
            raise InvalidConfigError(f"Custom careers page '{url}' did not return HTML content.")

        soup = BeautifulSoup(response.text, "html.parser")
        json_ld_job_postings = self._extract_json_ld_job_postings(soup)
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        title_tag = soup.find("title")
        page_title = self._clean_text(title_tag.get_text(" ", strip=True)) if title_tag else None
        visible_text = self._clean_text(soup.get_text(" ", strip=True))
        final_url = str(response.url)
        page = ResolvedPage(
            requested_url=url,
            final_url=final_url,
            status_code=response.status_code,
            content_type=content_type,
            soup=soup,
            page_title=page_title,
            visible_text=visible_text,
            redirected=bool(response.history) or final_url != url,
            json_ld_job_postings=json_ld_job_postings,
        )
        cache[url] = page
        cache[final_url] = page
        return page

    def _extract_candidates_from_page(
        self,
        page: ResolvedPage,
        *,
        current_depth: int,
    ) -> list[ExtractedRoleCandidate]:
        adapter_name = self._adapter_name_for_url(page.final_url)
        if adapter_name == "hrt":
            return self._extract_hrt_candidates(page, current_depth=current_depth)
        if adapter_name == "gresearch":
            return self._extract_gresearch_candidates(page, current_depth=current_depth)
        if adapter_name == "imc":
            return self._extract_imc_candidates(page, current_depth=current_depth)

        classification = self._classify_page(page)
        if classification == "job_detail":
            structured = self._extract_structured_data_candidates(page)
            if structured:
                return structured
            candidate = self._extract_generic_detail_candidate(page)
            return [candidate] if candidate is not None else []
        if classification == "job_listing":
            return self._extract_generic_listing_candidates(page, current_depth=current_depth)
        return []

    def _discover_seed_pages(
        self,
        client: httpx.Client,
        root_page: ResolvedPage,
        *,
        cache: dict[str, ResolvedPage],
        pages_remaining: int,
        polite_delay_seconds: float,
    ) -> tuple[list[ResolvedPage], int]:
        if pages_remaining <= 0:
            return [], 0

        adapter_name = self._adapter_name_for_url(root_page.final_url)
        if adapter_name != "imc":
            return [], 0
        if "/search-careers" in urlparse(root_page.final_url).path.casefold():
            return [], 0

        search_url = self._find_imc_search_careers_url(root_page)
        if not search_url:
            return [], 0

        if polite_delay_seconds > 0:
            self._sleeper(polite_delay_seconds)

        try:
            page = self._load_page(client, search_url, cache=cache, strict=False)
        except (InvalidConfigError, NetworkError, ParseError):
            return [], 0
        return [page], 1

    def _verify_candidate(
        self,
        client: httpx.Client,
        candidate: ExtractedRoleCandidate,
        *,
        parent_page: ResolvedPage,
        cache: dict[str, ResolvedPage],
        max_depth: int,
        current_depth: int,
        pages_remaining: int,
        polite_delay_seconds: float,
    ) -> tuple[ExtractedRoleCandidate | None, int]:
        source_url = candidate.source_url
        if source_url == parent_page.final_url:
            return (candidate if self._accept_candidate(candidate) else None, 0)
        if current_depth >= max_depth or pages_remaining <= 0:
            if self._can_emit_without_verification(candidate):
                return (candidate if self._accept_candidate(candidate) else None, 0)
            return None, 0

        if polite_delay_seconds > 0:
            self._sleeper(polite_delay_seconds)

        try:
            detail_page = self._load_page(client, source_url, cache=cache, strict=False)
        except (InvalidConfigError, NetworkError, ParseError):
            return (candidate if self._accept_candidate(candidate) else None, 0)

        verified = self._merge_candidate_with_detail(candidate, detail_page, parent_page=parent_page)
        if verified is None:
            return None, 1
        return (verified if self._accept_candidate(verified) else None, 1)

    def _merge_candidate_with_detail(
        self,
        candidate: ExtractedRoleCandidate,
        detail_page: ResolvedPage,
        *,
        parent_page: ResolvedPage,
    ) -> ExtractedRoleCandidate | None:
        detail_classification = self._classify_page(detail_page)
        if detail_page.status_code in {404, 410}:
            if candidate.status_hint == "unknown":
                return None
            return self._candidate_with_updates(
                candidate,
                source_url=parent_page.final_url,
                apply_url=None,
                requested_url=detail_page.requested_url,
                final_url=detail_page.final_url,
                status_hint=candidate.status_hint,
                status_evidence=[*candidate.status_evidence, f"detail URL returned HTTP {detail_page.status_code}"],
            )

        if detail_classification == "future_opportunity":
            status_hint, status_evidence = self._detect_status_hint(detail_page.visible_text)
            if status_hint == "unknown":
                status_hint = candidate.status_hint if candidate.status_hint != "unknown" else "closed"
            return self._candidate_with_updates(
                candidate,
                source_url=parent_page.final_url,
                apply_url=None,
                requested_url=detail_page.requested_url,
                final_url=detail_page.final_url,
                status_hint=status_hint,
                status_evidence=[*candidate.status_evidence, *status_evidence],
            )

        if detail_classification in {"program_editorial", "generic_homepage"}:
            if candidate.status_hint in {"closed", "coming_soon"}:
                return self._candidate_with_updates(
                    candidate,
                    source_url=parent_page.final_url,
                    apply_url=None,
                    requested_url=detail_page.requested_url,
                    final_url=detail_page.final_url,
                )
            return None

        detail_candidates = self._extract_candidates_from_page(detail_page, current_depth=1)
        detail_candidate = self._best_matching_detail_candidate(candidate, detail_candidates)
        if detail_candidate is None:
            if candidate.status_hint in {"closed", "coming_soon"}:
                return self._candidate_with_updates(
                    candidate,
                    source_url=parent_page.final_url,
                    requested_url=detail_page.requested_url,
                    final_url=detail_page.final_url,
                )
            return None

        if not self._titles_match(candidate.title, detail_candidate.title):
            if candidate.status_hint in {"closed", "coming_soon"}:
                return self._candidate_with_updates(
                    candidate,
                    source_url=parent_page.final_url,
                    requested_url=detail_page.requested_url,
                    final_url=detail_page.final_url,
                    status_evidence=[*candidate.status_evidence, "detail page title no longer matches expected role"],
                )
            return None

        status_hint, status_evidence = self._detect_status_hint(detail_candidate.block_text or detail_page.visible_text)
        merged_status = detail_candidate.status_hint if detail_candidate.status_hint != "unknown" else status_hint
        if merged_status == "unknown":
            merged_status = candidate.status_hint
        merged_status_evidence = [*candidate.status_evidence, *detail_candidate.status_evidence, *status_evidence]
        merged = self._candidate_with_updates(
            candidate,
            title=detail_candidate.title,
            source_url=detail_page.final_url,
            apply_url=detail_candidate.apply_url or candidate.apply_url,
            description=detail_candidate.description or candidate.description,
            location_raw=detail_candidate.location_raw or candidate.location_raw,
            season_hint=detail_candidate.season_hint or candidate.season_hint,
            status_hint=merged_status,
            block_text=detail_candidate.block_text or candidate.block_text,
            evidence=[*candidate.evidence, *detail_candidate.evidence],
            confidence=max(candidate.confidence, detail_candidate.confidence),
            page_type=detail_candidate.page_type,
            extracted_from=detail_candidate.extracted_from,
            title_source=detail_candidate.title_source,
            matched_keywords=self._unique_strings([*candidate.matched_keywords, *detail_candidate.matched_keywords]),
            requested_url=detail_page.requested_url,
            final_url=detail_page.final_url,
            status_evidence=merged_status_evidence,
        )
        if merged.apply_url and self._is_generic_destination(merged.apply_url):
            merged = self._candidate_with_updates(merged, apply_url=None)
        return merged

    def _extract_hrt_candidates(
        self,
        page: ResolvedPage,
        *,
        current_depth: int,
    ) -> list[ExtractedRoleCandidate]:
        path = urlparse(page.final_url).path.casefold()
        if "student-opportunities" in path:
            return self._extract_listing_candidates_from_blocks(
                page,
                current_depth=current_depth,
                adapter_name="hrt",
                extracted_from="adapter",
                preferred_detail_segment="/hrt-job/",
            )
        if "/hrt-job/" in path:
            candidate = self._extract_generic_detail_candidate(page, adapter_name="hrt", extracted_from="adapter")
            return [candidate] if candidate is not None else []
        return []

    def _extract_gresearch_candidates(
        self,
        page: ResolvedPage,
        *,
        current_depth: int,
    ) -> list[ExtractedRoleCandidate]:
        path = urlparse(page.final_url).path.casefold()
        if "/teams/engineering" in path:
            return self._extract_gresearch_opportunity_links(page, current_depth=current_depth)
        if "/vacancies/" in path:
            candidate = self._extract_generic_detail_candidate(page, adapter_name="gresearch", extracted_from="adapter")
            return [candidate] if candidate is not None else []
        return []

    def _extract_imc_candidates(
        self,
        page: ResolvedPage,
        *,
        current_depth: int,
    ) -> list[ExtractedRoleCandidate]:
        del current_depth
        path = urlparse(page.final_url).path.casefold()
        if "/search-careers" in path:
            candidates = self._extract_listing_candidates_from_blocks(
                page,
                current_depth=0,
                adapter_name="imc",
                extracted_from="adapter",
                preferred_detail_segment="/careers/jobs/",
            )
            return self._assign_imc_detail_links(page, candidates)
        if "/careers/jobs/" in path:
            candidate = self._extract_generic_detail_candidate(page, adapter_name="imc", extracted_from="adapter")
            return [candidate] if candidate is not None else []
        if "/careers/students-graduates/internships/" in path and self._find_imc_job_links(page.soup, page.final_url):
            candidates = self._extract_listing_candidates_from_blocks(
                page,
                current_depth=0,
                adapter_name="imc",
                extracted_from="adapter",
                preferred_detail_segment="/careers/jobs/",
            )
            return self._assign_imc_detail_links(page, candidates)
        return []

    def _extract_structured_data_candidates(self, page: ResolvedPage) -> list[ExtractedRoleCandidate]:
        candidates: list[ExtractedRoleCandidate] = []
        for payload in page.json_ld_job_postings:
            title = self._clean_text(str(payload.get("title", "")))
            if not self._looks_like_role_title(title):
                continue

            description = self._clean_text(self._htmlish_text(payload.get("description")))
            location = self._extract_job_posting_location(payload)
            source_url = self._clean_url(str(payload.get("url") or page.final_url), page.final_url)
            apply_url = self._detect_apply_url(page.soup, page.final_url, page.final_url)
            status_hint, status_evidence = self._detect_status_hint(description or page.visible_text)
            candidates.append(
                ExtractedRoleCandidate(
                    title=title,
                    source_url=source_url,
                    apply_url=apply_url,
                    description=description or page.visible_text,
                    location_raw=location or self._detect_location(page.visible_text),
                    season_hint=self._detect_season_hint(description or page.visible_text),
                    status_hint=status_hint,
                    block_text=description or page.visible_text,
                    evidence=["structured data job posting"],
                    confidence=0.97,
                    page_type="job_detail",
                    extracted_from="structured_data",
                    title_source="structured_data",
                    matched_keywords=self._matched_keywords(title, description or page.visible_text),
                    requested_url=page.requested_url,
                    final_url=page.final_url,
                    status_evidence=status_evidence,
                ),
            )
        return candidates

    def _extract_generic_detail_candidate(
        self,
        page: ResolvedPage,
        *,
        adapter_name: str | None = None,
        extracted_from: str = "detail_page",
    ) -> ExtractedRoleCandidate | None:
        title, title_source = self._extract_page_title(page.soup, page.page_title)
        if not title or not self._looks_like_role_title(title):
            return None

        if self._looks_like_marketing_copy(title):
            return None

        description = self._extract_detail_description(page.soup)
        detail_text = self._clean_text(f"{description or ''} {page.visible_text}")
        if description is None:
            description = page.visible_text
        location = self._detect_location(detail_text)
        apply_url = self._detect_apply_url(page.soup, page.final_url, page.final_url)
        if apply_url and self._is_generic_destination(apply_url):
            apply_url = None
        status_hint, status_evidence = self._detect_status_hint(detail_text)
        matched_keywords = self._matched_keywords(title, detail_text)
        if not matched_keywords and not self._looks_like_direct_detail_url(page.final_url):
            return None

        return ExtractedRoleCandidate(
            title=title,
            source_url=page.final_url,
            apply_url=apply_url,
            description=description,
            location_raw=location,
            season_hint=self._detect_season_hint(detail_text),
            status_hint=status_hint,
            block_text=detail_text,
            evidence=["specific detail page"],
            adapter_name=adapter_name,
            confidence=0.9 if apply_url else 0.8,
            page_type="job_detail",
            extracted_from=extracted_from,
            title_source=title_source,
            block_anchor_text=None,
            matched_keywords=matched_keywords,
            requested_url=page.requested_url,
            final_url=page.final_url,
            status_evidence=status_evidence,
        )

    def _extract_generic_listing_candidates(
        self,
        page: ResolvedPage,
        *,
        current_depth: int,
    ) -> list[ExtractedRoleCandidate]:
        return self._extract_listing_candidates_from_blocks(
            page,
            current_depth=current_depth,
            adapter_name=None,
            extracted_from="listing_block",
            preferred_detail_segment=None,
        )

    def _extract_listing_candidates_from_blocks(
        self,
        page: ResolvedPage,
        *,
        current_depth: int,
        adapter_name: str | None,
        extracted_from: str,
        preferred_detail_segment: str | None,
    ) -> list[ExtractedRoleCandidate]:
        del current_depth
        blocks = self._find_role_blocks(page.soup, page.final_url)
        candidates: list[ExtractedRoleCandidate] = []
        for block in blocks:
            block_text = self._block_text(block.container)
            if not block_text:
                continue
            if self._looks_like_editorial_block(block_text):
                continue

            title = block.title
            matched_keywords = self._matched_keywords(title, block_text)
            if not matched_keywords:
                continue

            status_hint, status_evidence = self._detect_status_hint(block_text)
            location = self._detect_location(block_text)
            description = self._extract_block_description(block.container, title)
            source_url = self._extract_role_link(block.container, page.final_url, preferred_detail_segment) or page.final_url
            apply_url = self._detect_apply_url(block.container, page.final_url, source_url)
            if apply_url and self._is_generic_destination(apply_url):
                apply_url = None
            if not self._is_valid_listing_candidate(
                title=title,
                block_text=block_text,
                source_url=source_url,
                apply_url=apply_url,
                status_hint=status_hint,
            ):
                continue

            candidates.append(
                ExtractedRoleCandidate(
                    title=title,
                    source_url=source_url,
                    apply_url=apply_url,
                    description=description or block_text,
                    location_raw=location,
                    season_hint=self._detect_season_hint(block_text),
                    status_hint=status_hint,
                    block_text=block_text,
                    evidence=["listing block with role-local metadata"],
                    adapter_name=adapter_name,
                    confidence=0.8 if source_url != page.final_url else 0.72,
                    page_type="job_listing",
                    extracted_from=extracted_from,
                    title_source="listing_block_heading" if block.anchor_text != title else "listing_block_anchor",
                    block_anchor_text=block.anchor_text,
                    matched_keywords=matched_keywords,
                    requested_url=source_url,
                    final_url=page.final_url if source_url == page.final_url else None,
                    status_evidence=status_evidence,
                ),
            )
        return candidates

    def _extract_gresearch_opportunity_links(
        self,
        page: ResolvedPage,
        *,
        current_depth: int,
    ) -> list[ExtractedRoleCandidate]:
        del current_depth
        candidates: list[ExtractedRoleCandidate] = []
        for anchor in page.soup.find_all("a", href=True):
            href = self._clean_url(anchor.get("href"), page.final_url)
            if "/vacancies/" not in urlparse(href).path.casefold():
                continue
            text = self._clean_text(anchor.get_text(" ", strip=True))
            if not self._looks_like_role_title(text):
                continue
            container = self._nearest_role_container(anchor)
            block_text = self._block_text(container) if container is not None else text
            candidates.append(
                ExtractedRoleCandidate(
                    title=text,
                    source_url=href,
                    apply_url=None,
                    description=self._extract_block_description(container, text) if container is not None else block_text,
                    location_raw=self._detect_location(block_text),
                    season_hint=self._detect_season_hint(block_text),
                    status_hint="unknown",
                    block_text=block_text,
                    evidence=["g-research opportunity link from engineering page"],
                    adapter_name="gresearch",
                    confidence=0.68,
                    page_type="program_editorial",
                    extracted_from="adapter",
                    title_source="opportunity_link",
                    block_anchor_text=text,
                    matched_keywords=self._matched_keywords(text, block_text),
                    requested_url=href,
                    final_url=None,
                    status_evidence=[],
                ),
            )
        return candidates

    def _find_imc_search_careers_url(self, page: ResolvedPage) -> str | None:
        for anchor in page.soup.find_all("a", href=True):
            href = self._clean_url(anchor.get("href"), page.final_url)
            if "/search-careers" in urlparse(href).path.casefold():
                return href
            text = self._clean_text(anchor.get_text(" ", strip=True)).casefold()
            if text == "search careers" and href:
                return href
        parsed = urlparse(page.final_url)
        segments = [segment for segment in parsed.path.split("/") if segment]
        if not segments:
            return f"{parsed.scheme}://{parsed.netloc}/search-careers"
        region = segments[0]
        return f"{parsed.scheme}://{parsed.netloc}/{region}/search-careers"

    def _find_imc_job_links(self, soup: BeautifulSoup, page_url: str) -> list[str]:
        return [href for href, _ in self._find_imc_job_anchors(soup, page_url)]

    def _find_imc_job_anchors(self, soup: BeautifulSoup, page_url: str) -> list[tuple[str, str]]:
        anchors: list[tuple[str, str]] = []
        seen: set[str] = set()
        for anchor in soup.find_all("a", href=True):
            href = self._clean_url(anchor.get("href"), page_url)
            path = urlparse(href).path.casefold()
            if "/careers/jobs/" not in path or path.endswith("/apply"):
                continue
            if href in seen:
                continue
            seen.add(href)
            anchors.append((href, self._clean_text(anchor.get_text(" ", strip=True))))
        return anchors

    def _assign_imc_detail_links(
        self,
        page: ResolvedPage,
        candidates: list[ExtractedRoleCandidate],
    ) -> list[ExtractedRoleCandidate]:
        job_anchors = self._find_imc_job_anchors(page.soup, page.final_url)
        if not job_anchors:
            return candidates

        remaining = list(job_anchors)
        assigned: list[ExtractedRoleCandidate] = []
        for candidate in candidates:
            if candidate.source_url != page.final_url:
                assigned.append(candidate)
                continue

            matched_index = -1
            candidate_lower = candidate.title.casefold()
            for index, (_, anchor_text) in enumerate(remaining):
                if candidate_lower and candidate_lower in anchor_text.casefold():
                    matched_index = index
                    break
            if matched_index == -1 and remaining:
                matched_index = 0

            if matched_index >= 0:
                matched_url, matched_text = remaining.pop(matched_index)
                assigned.append(
                    self._candidate_with_updates(
                        candidate,
                        source_url=matched_url,
                        requested_url=matched_url,
                        block_anchor_text=matched_text or candidate.block_anchor_text,
                    ),
                )
            else:
                assigned.append(candidate)
        return assigned

    def _classify_page(self, page: ResolvedPage) -> PageClassification:
        if page.json_ld_job_postings:
            return "job_detail"

        lowered_text = page.visible_text.casefold()
        lowered_title = (page.page_title or "").casefold()
        final_path = urlparse(page.final_url).path.casefold()

        if self._is_future_opportunity_page(final_path, lowered_text):
            return "future_opportunity"

        blocks = self._find_role_blocks(page.soup, page.final_url)
        if blocks:
            repeated = len(blocks) >= 2 or any(
                self._looks_like_direct_detail_url(
                    self._extract_role_link(block.container, page.final_url, None) or "",
                )
                for block in blocks
            )
            if repeated or self._is_generic_destination(page.final_url):
                return "job_listing"

        if self._looks_like_direct_detail_url(page.final_url):
            title, _ = self._extract_page_title(page.soup, page.page_title)
            if title and self._looks_like_role_title(title):
                return "job_detail"

        if any(term in lowered_title or term in lowered_text for term in GENERIC_PAGE_TERMS):
            return "program_editorial"

        if self._is_generic_destination(page.final_url):
            return "generic_homepage"

        return "program_editorial"

    def _find_role_blocks(self, soup: BeautifulSoup, page_url: str) -> list[ContainerCandidate]:
        seeds: list[ContainerCandidate] = []
        for anchor in soup.find_all("a", href=True):
            anchor_text = self._clean_text(anchor.get_text(" ", strip=True))
            href = self._clean_url(anchor.get("href"), page_url)
            if not href:
                continue
            if any(term in anchor_text.casefold() or term in href.casefold() for term in NEGATIVE_LINK_TERMS):
                continue
            if not self._looks_like_role_title(anchor_text) and not self._looks_like_direct_detail_url(href):
                continue
            container = self._nearest_role_container(anchor)
            if container is None:
                continue
            title = anchor_text if self._looks_like_role_title(anchor_text) else self._best_title_from_container(container) or anchor_text
            if not self._looks_like_role_title(title):
                continue
            seeds.append(ContainerCandidate(container=container, anchor=anchor, title=title, anchor_text=anchor_text or None))

        for heading in soup.find_all(["h1", "h2", "h3", "h4"]):
            title = self._clean_text(heading.get_text(" ", strip=True))
            if not self._looks_like_role_title(title):
                continue
            container = self._nearest_role_container(heading)
            if container is None:
                continue
            seeds.append(ContainerCandidate(container=container, anchor=None, title=title, anchor_text=None))

        deduped: list[ContainerCandidate] = []
        for seed in sorted(seeds, key=lambda item: len(self._block_text(item.container))):
            if self._is_duplicate_container(seed.container, [candidate.container for candidate in deduped]):
                continue
            deduped.append(seed)
        return deduped

    def _nearest_role_container(self, seed: Tag) -> Tag | None:
        current: Tag | None = seed if isinstance(seed, Tag) else None
        while current is not None and current.name not in {"body", "html"}:
            if current.name == "a":
                text = self._clean_text(current.get_text(" ", strip=True))
                if self._looks_like_role_title(text):
                    return current
            if current.name in {"article", "section", "li", "div"}:
                text = self._block_text(current)
                if 40 <= len(text) <= 2400 and any(term in text.casefold() for term in ROLE_SIGNAL_TERMS):
                    return current
            parent = current.parent
            current = parent if isinstance(parent, Tag) else None
        return None

    def _block_text(self, container: Tag | None) -> str:
        if container is None:
            return ""
        return self._clean_text(container.get_text(" ", strip=True))

    def _extract_page_title(self, soup: BeautifulSoup, page_title: str | None) -> tuple[str | None, str]:
        heading_candidates: list[tuple[str, str]] = []
        for tag_name in ("h1", "h2"):
            heading = soup.find(tag_name)
            if heading is None:
                continue
            text = self._clean_text(heading.get_text(" ", strip=True))
            if text:
                heading_candidates.append((text, "heading"))
        if heading_candidates:
            ranked_headings = sorted(
                heading_candidates,
                key=lambda item: self._title_specificity_score(item[0]),
                reverse=True,
            )
            return ranked_headings[0]

        candidates: list[tuple[str, str]] = []
        if page_title:
            cleaned_page_title = self._clean_text(page_title)
            candidates.append((cleaned_page_title, "page_title"))
            if "|" in cleaned_page_title:
                trimmed = self._clean_text(cleaned_page_title.split("|", 1)[0])
                if trimmed:
                    candidates.append((trimmed, "page_title_trimmed"))
        if not candidates:
            return None, "unknown"
        source_priority = {
            "heading": 3,
            "page_title_trimmed": 2,
            "page_title": 1,
        }
        ranked = sorted(
            candidates,
            key=lambda item: (self._title_specificity_score(item[0]), source_priority.get(item[1], 0)),
            reverse=True,
        )
        return ranked[0]

    def _best_title_from_container(self, container: Tag) -> str | None:
        candidates: list[str] = []
        for tag_name in ("h2", "h3", "h4", "a", "strong"):
            for tag in container.find_all(tag_name):
                text = self._clean_text(tag.get_text(" ", strip=True))
                if self._looks_like_role_title(text):
                    candidates.append(text)
        if not candidates:
            return None
        return sorted(candidates, key=self._title_specificity_score, reverse=True)[0]

    def _extract_role_link(
        self,
        container: Tag,
        page_url: str,
        preferred_detail_segment: str | None,
    ) -> str | None:
        best_url: str | None = None
        best_score = -1
        anchors = [container] if container.name == "a" and container.get("href") else []
        anchors.extend(container.find_all("a", href=True))
        for anchor in anchors:
            href = self._clean_url(anchor.get("href"), page_url)
            if not href:
                continue
            if any(term in href.casefold() for term in NEGATIVE_LINK_TERMS):
                continue
            text = self._clean_text(anchor.get_text(" ", strip=True))
            score = 0
            if preferred_detail_segment and preferred_detail_segment in urlparse(href).path.casefold():
                score += 5
            if self._looks_like_direct_detail_url(href):
                score += 4
            if self._looks_like_role_title(text):
                score += 3
            if any(term in text.casefold() for term in APPLY_TERMS):
                score -= 1
            if score > best_score:
                best_score = score
                best_url = href
        return best_url

    def _detect_apply_url(self, node: Tag | BeautifulSoup, page_url: str, source_url: str) -> str | None:
        for anchor in node.find_all("a", href=True):
            href = self._clean_url(anchor.get("href"), page_url)
            if not href:
                continue
            text = self._clean_text(anchor.get_text(" ", strip=True))
            haystack = f"{text} {href}".casefold()
            if any(term in haystack for term in APPLY_TERMS):
                if self._is_explicit_apply_destination(href, source_url):
                    return href
        return None

    def _is_explicit_apply_destination(self, url: str, source_url: str) -> bool:
        if not url:
            return False
        parsed_url = urlparse(url)
        if parsed_url.scheme not in {"http", "https"}:
            return False
        if self._is_generic_destination(url):
            return False
        if parsed_url.netloc != urlparse(source_url).netloc:
            return True
        path = parsed_url.path.casefold()
        return any(term in path for term in ("/apply", "/application", "/jobs/", "/vacancies/", "/hrt-job/"))

    def _is_valid_listing_candidate(
        self,
        *,
        title: str,
        block_text: str,
        source_url: str,
        apply_url: str | None,
        status_hint: STATUS_HINTS,
    ) -> bool:
        if not self._looks_like_role_title(title):
            return False
        if self._looks_like_marketing_copy(title):
            return False
        if self._looks_like_editorial_block(block_text):
            return False
        has_metadata = bool(
            self._detect_season_hint(block_text)
            or self._detect_location(block_text)
            or status_hint != "unknown"
            or source_url
            or apply_url
        )
        if not has_metadata:
            return False
        if source_url == "" and apply_url is None:
            return False
        return True

    def _accept_candidate(self, candidate: ExtractedRoleCandidate) -> bool:
        if not candidate.title or not self._looks_like_role_title(candidate.title):
            return False
        if self._looks_like_marketing_copy(candidate.title):
            return False
        if candidate.page_type in {"program_editorial", "generic_homepage"} and candidate.status_hint == "unknown":
            return False
        if candidate.source_url and self._is_generic_destination(candidate.source_url) and candidate.status_hint == "unknown":
            return False
        if candidate.apply_url and self._is_generic_destination(candidate.apply_url):
            return False
        return True

    def _can_emit_without_verification(self, candidate: ExtractedRoleCandidate) -> bool:
        return bool(
            candidate.location_raw
            or candidate.season_hint
            or candidate.status_hint != "unknown"
            or (candidate.apply_url and not self._is_generic_destination(candidate.apply_url))
            or (candidate.description and len(candidate.description.split()) >= 10)
        )

    def _candidate_to_raw_job(self, company: Company, candidate: ExtractedRoleCandidate) -> RawJob:
        return RawJob(
            source_type=self.source_type,
            source_name="Custom Career Page",
            company_id=company.id,
            company_name=company.name,
            title=candidate.title,
            url=candidate.source_url,
            apply_url=candidate.apply_url,
            location_raw=candidate.location_raw,
            description_raw=candidate.description or candidate.block_text,
            department=None,
            raw_payload={
                "page_type": candidate.page_type,
                "adapter": candidate.adapter_name,
                "requested_url": candidate.requested_url or candidate.source_url,
                "final_url": candidate.final_url or candidate.source_url,
                "extracted_from": candidate.extracted_from,
                "status_evidence": candidate.status_evidence,
                "matched_keywords": candidate.matched_keywords,
                "block_anchor_text": candidate.block_anchor_text,
                "title_source": candidate.title_source,
                "status_hint": candidate.status_hint,
                "season_hint": candidate.season_hint,
                "confidence": candidate.confidence,
                "evidence": candidate.evidence,
            },
        )

    def _extract_json_ld_job_postings(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        postings: list[dict[str, Any]] = []
        for script in soup.find_all("script", attrs={"type": re.compile(r"ld\+json", re.IGNORECASE)}):
            raw_text = script.string or script.get_text(" ", strip=True)
            if not raw_text.strip():
                continue
            try:
                payload = json.loads(raw_text)
            except json.JSONDecodeError:
                continue
            for obj in self._iter_json_objects(payload):
                types = obj.get("@type")
                if isinstance(types, str):
                    type_values = {types.casefold()}
                elif isinstance(types, list):
                    type_values = {str(item).casefold() for item in types}
                else:
                    continue
                if "jobposting" in type_values:
                    postings.append(obj)
        return postings

    def _iter_json_objects(self, payload: Any) -> Iterable[dict[str, Any]]:
        if isinstance(payload, dict):
            yield payload
            graph = payload.get("@graph")
            if isinstance(graph, list):
                for item in graph:
                    yield from self._iter_json_objects(item)
        elif isinstance(payload, list):
            for item in payload:
                yield from self._iter_json_objects(item)

    def _extract_job_posting_location(self, payload: dict[str, Any]) -> str | None:
        job_location = payload.get("jobLocation")
        if isinstance(job_location, list) and job_location:
            job_location = job_location[0]
        if isinstance(job_location, dict):
            address = job_location.get("address")
            if isinstance(address, dict):
                locality = self._clean_text(str(address.get("addressLocality", "")))
                if locality:
                    return locality
                pieces = [
                    self._clean_text(str(address.get(key, "")))
                    for key in ("addressRegion", "addressCountry")
                    if address.get(key)
                ]
                if pieces:
                    return ", ".join(piece for piece in pieces if piece)
        return None

    def _extract_detail_description(self, soup: BeautifulSoup) -> str | None:
        paragraphs: list[str] = []
        for paragraph in soup.find_all(["p", "li"]):
            text = self._clean_text(paragraph.get_text(" ", strip=True))
            if not text:
                continue
            if len(text) < 20:
                continue
            if any(term in text.casefold() for term in NEGATIVE_LINK_TERMS):
                continue
            paragraphs.append(text)
        if not paragraphs:
            return None
        return self._clean_text(" ".join(paragraphs[:6]))

    def _extract_block_description(self, container: Tag | None, title: str) -> str | None:
        if container is None:
            return None
        paragraphs: list[str] = []
        for paragraph in container.find_all(["p", "li"]):
            text = self._clean_text(paragraph.get_text(" ", strip=True))
            if not text or text == title:
                continue
            paragraphs.append(text)
        if not paragraphs:
            return None
        return self._clean_text(" ".join(paragraphs[:4]))

    def _detect_location(self, text: str) -> str | None:
        lowered = text.casefold()
        for token in LOCATION_TOKENS:
            if token in lowered:
                if token == "nyc":
                    return "NYC"
                if token == "new york city":
                    return "New York City"
                if token == "new york, ny":
                    return "New York, NY"
                return self._clean_text(token.title() if token.islower() else token)

        for line in self._short_text_lines(text):
            lowered_line = line.casefold()
            if any(token in lowered_line for token in LOCATION_TOKENS):
                return line
        return None

    def _detect_season_hint(self, text: str) -> str | None:
        match = SEASON_PATTERN.search(text)
        if match:
            return self._clean_text(match.group(0))
        year_match = YEAR_PATTERN.search(text)
        if year_match and "intern" in text.casefold():
            return year_match.group(0)
        return None

    def _detect_status_hint(self, text: str) -> tuple[STATUS_HINTS, list[str]]:
        lowered = text.casefold()
        evidence: list[str] = []
        for term in COMING_SOON_TERMS:
            if term in lowered:
                evidence.append(term)
        for term in CLOSED_TERMS:
            if term in lowered:
                evidence.append(term)

        if evidence:
            if any(term in lowered for term in COMING_SOON_TERMS):
                return "coming_soon", self._unique_strings(evidence)
            return "closed", self._unique_strings(evidence)
        return "unknown", []

    def _is_future_opportunity_page(self, path: str, lowered_text: str) -> bool:
        if any(hint in path for hint in FUTURE_OPPORTUNITY_PATH_HINTS):
            return True
        if "vacancy has been filled" in lowered_text or "this vacancy has been filled" in lowered_text:
            return True
        if "check back next year" in lowered_text and "applications" in lowered_text:
            return True
        if "join our talent community" in lowered_text:
            return True
        return False

    def _looks_like_role_title(self, text: str | None) -> bool:
        if not text:
            return False
        cleaned = self._clean_text(text)
        if not cleaned:
            return False
        lowered = cleaned.casefold()
        if lowered in EXACT_GENERIC_TITLES:
            return False
        if any(lowered.startswith(prefix) for prefix in MARKETING_TITLE_PREFIXES):
            return False
        if any(term in lowered for term in GENERIC_DISCOVERY_TERMS) and not any(signal in lowered for signal in ROLE_SIGNAL_TERMS):
            return False
        if any(term in lowered for term in GENERIC_PAGE_TERMS):
            return False
        if len(cleaned.split()) > 12:
            return False
        if re.search(r"[.!?]", cleaned) and not any(signal in lowered for signal in ROLE_SIGNAL_TERMS):
            return False
        return any(signal in lowered for signal in ROLE_SIGNAL_TERMS)

    def _looks_like_marketing_copy(self, text: str) -> bool:
        lowered = text.casefold()
        if lowered in EXACT_GENERIC_TITLES:
            return True
        if any(lowered.startswith(prefix) for prefix in MARKETING_TITLE_PREFIXES):
            return True
        if any(term in lowered for term in GENERIC_PAGE_TERMS):
            return True
        if len(lowered.split()) >= 11 and not any(term in lowered for term in ROLE_SIGNAL_TERMS):
            return True
        return False

    def _looks_like_editorial_block(self, text: str) -> bool:
        lowered = text.casefold()
        generic_hits = sum(1 for term in GENERIC_PAGE_TERMS if term in lowered)
        role_hits = sum(1 for term in ROLE_SIGNAL_TERMS if term in lowered)
        if generic_hits >= 2 and role_hits <= 1:
            return True
        if "tech blog" in lowered or "follow us" in lowered:
            return True
        return False

    def _looks_like_direct_detail_url(self, url: str) -> bool:
        lowered = url.casefold()
        if any(pattern in lowered for pattern in DIRECT_DETAIL_PATH_PATTERNS):
            return True
        segments = [segment for segment in urlparse(url).path.casefold().split("/") if segment]
        if not segments:
            return False
        last_segment = segments[-1]
        if last_segment in GENERIC_SECTION_SEGMENTS:
            return False
        if any(term in last_segment for term in ("intern", "engineer", "developer", "analyst", "research", "trader")):
            return True
        return False

    def _is_generic_destination(self, url: str) -> bool:
        parsed = urlparse(url)
        path = parsed.path.strip("/").casefold()
        if not path:
            return True
        segments = [segment for segment in path.split("/") if segment]
        if not segments:
            return True
        if len(segments) == 1 and segments[0] in GENERIC_SECTION_SEGMENTS:
            return True
        if segments[-1] in GENERIC_SECTION_SEGMENTS:
            return True
        return False

    def _matched_keywords(self, title: str, text: str) -> list[str]:
        lowered = f"{title} {text}".casefold()
        return [term for term in ROLE_SIGNAL_TERMS if term in lowered]

    def _titles_match(self, expected: str, actual: str, threshold: float = 0.45) -> bool:
        expected_tokens = self._title_tokens(expected)
        actual_tokens = self._title_tokens(actual)
        if not expected_tokens or not actual_tokens:
            return False
        intersection = expected_tokens & actual_tokens
        if not intersection:
            return False
        score = len(intersection) / max(len(expected_tokens), len(actual_tokens))
        return score >= threshold

    def _title_tokens(self, text: str) -> set[str]:
        tokens = {
            token
            for token in NON_WORD_PATTERN.sub(" ", text.casefold()).split()
            if token and token not in STOPWORDS and not re.fullmatch(r"20\d{2}", token)
        }
        return tokens

    def _title_specificity_score(self, title: str) -> tuple[int, int, int]:
        lowered = title.casefold()
        role_hits = sum(1 for signal in ROLE_SIGNAL_TERMS if signal in lowered)
        generic_penalty = sum(1 for signal in GENERIC_PAGE_TERMS if signal in lowered)
        return (role_hits, -generic_penalty, -len(lowered))

    def _best_matching_detail_candidate(
        self,
        listing_candidate: ExtractedRoleCandidate,
        detail_candidates: list[ExtractedRoleCandidate],
    ) -> ExtractedRoleCandidate | None:
        best: ExtractedRoleCandidate | None = None
        best_score = -1.0
        for detail_candidate in detail_candidates:
            if not self._titles_match(listing_candidate.title, detail_candidate.title):
                continue
            score = len(self._title_tokens(listing_candidate.title) & self._title_tokens(detail_candidate.title))
            if score > best_score:
                best = detail_candidate
                best_score = float(score)
        return best

    def _adapter_name_for_url(self, url: str) -> str | None:
        netloc = urlparse(url).netloc.casefold()
        if "hudsonrivertrading.com" in netloc:
            return "hrt"
        if "gresearch.com" in netloc:
            return "gresearch"
        if "imc.com" in netloc:
            return "imc"
        return None

    def _short_text_lines(self, text: str) -> list[str]:
        chunks = [self._clean_text(chunk) for chunk in re.split(r"[•\n|]+", text)]
        return [chunk for chunk in chunks if chunk and len(chunk) <= 120]

    def _htmlish_text(self, value: Any) -> str:
        if value is None:
            return ""
        return BeautifulSoup(str(value), "html.parser").get_text(" ", strip=True)

    def _clean_url(self, href: str | None, page_url: str) -> str:
        if not href:
            return ""
        return urljoin(page_url, href).split("#", 1)[0]

    def _is_duplicate_container(self, candidate: Tag, chosen: list[Tag]) -> bool:
        for existing in chosen:
            if candidate is existing:
                return True
            if candidate in existing.descendants or existing in candidate.descendants:
                return True
        return False

    def _dedupe_candidates(self, candidates: Iterable[ExtractedRoleCandidate]) -> list[ExtractedRoleCandidate]:
        deduped: list[ExtractedRoleCandidate] = []
        seen: set[tuple[str, str]] = set()
        for candidate in candidates:
            key = (candidate.title.casefold(), candidate.source_url)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(candidate)
        return deduped

    def _candidate_with_updates(
        self,
        candidate: ExtractedRoleCandidate,
        **updates: Any,
    ) -> ExtractedRoleCandidate:
        payload = {field_def.name: getattr(candidate, field_def.name) for field_def in fields(candidate)}
        payload.update(updates)
        return ExtractedRoleCandidate(**payload)

    def _unique_strings(self, values: Iterable[str]) -> list[str]:
        seen: set[str] = set()
        unique: list[str] = []
        for value in values:
            cleaned = self._clean_text(value)
            if not cleaned or cleaned in seen:
                continue
            seen.add(cleaned)
            unique.append(cleaned)
        return unique

    def _clean_text(self, value: str | None) -> str:
        if value is None:
            return ""
        return WHITESPACE_PATTERN.sub(" ", value.replace("\xa0", " ")).strip()


__all__ = ["CustomPageCollector"]
