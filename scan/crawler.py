"""
Genesis QA - Crawler Module
============================
Asynchronous web crawler that discovers reachable web pages from a given seed URL.
Supports depth limits, domain scoping, and configurable concurrency via aiohttp.

Typical usage:
    crawler = Crawler("https://example.com")
    results = await crawler.run(max_pages=200)
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urljoin, urlparse

import aiohttp
from aiohttp import ClientTimeout, TCPConnector

logger = logging.getLogger(__name__)


class CrawlerError(Exception):
    """Base exception for crawler failures."""


class CrawlerTimeoutError(CrawlerError):
    """Raised when a page fetch times out."""


class CrawlerConnectionError(CrawlerError):
    """Raised when a connection cannot be established."""


@dataclass
class CrawledPage:
    """Represents a successfully crawled page."""

    url: str
    status: int
    title: Optional[str] = None
    links: list[str] = field(default_factory=list)
    content_length: int = 0
    response_time_ms: float = 0.0
    content_type: str = ""


class Crawler:
    """Asynchronous web crawler with depth limiting and domain scoping.

    Attributes:
        seed_url:        Starting URL for the crawl.
        base_domain:     Domain extracted from seed_url (used for scoping).
        max_concurrency: Maximum number of simultaneous page fetches.
        timeout:         HTTP request timeout in seconds.
        user_agent:      User-Agent header sent with requests.
        respect_robots:  Whether to check robots.txt before crawling (future).
    """

    URL_REGEX = re.compile(r'href=["\'](.*?)["\']', re.IGNORECASE)
    TITLE_REGEX = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)

    def __init__(
        self,
        seed_url: str,
        *,
        max_concurrency: int = 10,
        timeout: float = 30.0,
        user_agent: str = "GenesisQA-Crawler/0.1.0",
        respect_robots: bool = False,
    ) -> None:
        if not seed_url or not isinstance(seed_url, str):
            raise ValueError("seed_url must be a non-empty string")

        self.seed_url = seed_url.rstrip("/")
        parsed = urlparse(self.seed_url)
        self.base_domain = parsed.netloc.lower()
        self.base_scheme = parsed.scheme
        self.max_concurrency = max_concurrency
        self.timeout = timeout
        self.user_agent = user_agent
        self.respect_robots = respect_robots

        self._visited: set[str] = set()
        self._results: list[CrawledPage] = []
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._session: Optional[aiohttp.ClientSession] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(
        self,
        max_pages: int = 100,
        max_depth: int = 3,
    ) -> list[CrawledPage]:
        """Execute the crawl starting from *seed_url*.

        Args:
            max_pages: Maximum number of pages to crawl (soft limit).
            max_depth: Maximum link depth from seed (0 = seed only).

        Returns:
            A list of successfully crawled pages.
        """
        logger.info(
            "Starting crawl of %s (max_pages=%d, max_depth=%d)",
            self.seed_url,
            max_pages,
            max_depth,
        )

        self._visited.clear()
        self._results = []
        self._semaphore = asyncio.Semaphore(self.max_concurrency)

        connector = TCPConnector(limit=self.max_concurrency, force_close=True)
        timeout_obj = ClientTimeout(total=self.timeout)

        async with aiohttp.ClientSession(
            connector=connector,
            timeout=timeout_obj,
            headers={"User-Agent": self.user_agent},
        ) as self._session:
            await self._crawl(self.seed_url, depth=0, max_pages=max_pages, max_depth=max_depth)

        logger.info("Crawl finished — visited %d pages", len(self._results))
        return self._results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _crawl(
        self,
        url: str,
        depth: int,
        max_pages: int,
        max_depth: int,
    ) -> None:
        """Recursively crawl *url* up to *max_depth*."""
        if len(self._results) >= max_pages:
            return
        if url in self._visited:
            return
        if depth > max_depth:
            return

        self._visited.add(url)

        try:
            page = await self._fetch(url)
        except CrawlerError as exc:
            logger.debug("Skipping %s — %s", url, exc)
            return

        self._results.append(page)
        logger.debug("Crawled [%d] %s (depth=%d)", page.status, url, depth)

        # Recursively crawl discovered links
        tasks: list[asyncio.Task[None]] = []
        for link in page.links:
            if len(self._results) >= max_pages:
                break
            tasks.append(
                asyncio.create_task(
                    self._crawl(link, depth=depth + 1, max_pages=max_pages, max_depth=max_depth)
                )
            )

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _fetch(self, url: str) -> CrawledPage:
        """Fetch a single URL and parse its contents.

        Returns a CrawledPage or raises CrawlerError on failure.
        """
        async with self._semaphore:  # type: ignore[union-attr]
            start = time.monotonic()
            try:
                async with self._session.get(  # type: ignore[union-attr]
                    url,
                    allow_redirects=True,
                    ssl=False,
                ) as resp:
                    elapsed = (time.monotonic() - start) * 1000.0
                    body = await resp.text(encoding="utf-8", errors="replace")
            except asyncio.TimeoutError:
                raise CrawlerTimeoutError(f"Timeout fetching {url}")
            except aiohttp.ClientError as exc:
                raise CrawlerConnectionError(f"Connection error for {url}: {exc}")

        title = self._extract_title(body)
        links = self._extract_links(url, body) if resp.status == 200 else []

        return CrawledPage(
            url=str(resp.url),
            status=resp.status,
            title=title,
            links=links,
            content_length=len(body),
            response_time_ms=round(elapsed, 2),
            content_type=resp.content_type or "",
        )

    def _extract_title(self, html: str) -> Optional[str]:
        """Extract page title from HTML."""
        match = self.TITLE_REGEX.search(html)
        if match:
            return match.group(1).strip()
        return None

    def _extract_links(self, base_url: str, html: str) -> list[str]:
        """Extract and normalize same-domain links from HTML."""
        raw_links: list[str] = self.URL_REGEX.findall(html)
        normalized: set[str] = set()

        for link in raw_links:
            # Skip anchors, javascript, mailto
            if link.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue

            absolute = urljoin(base_url, link)
            parsed = urlparse(absolute)

            # Scope to same domain and scheme
            if parsed.netloc.lower() != self.base_domain:
                continue
            if parsed.scheme not in ("http", "https"):
                continue

            # Normalize: remove fragment, trailing slash
            clean = parsed._replace(fragment="").geturl().rstrip("/")
            if clean:
                normalized.add(clean)

        return sorted(normalized)
