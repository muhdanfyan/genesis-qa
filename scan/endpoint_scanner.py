"""
Genesis QA - Endpoint Scanner Module
=====================================
Scans a web application for hidden or exposed endpoints (paths, files, routes).
Uses wordlist-based brute-forcing to discover resources not linked from the
homepage. Results include HTTP status codes and response metadata.

Typical usage:
    scanner = EndpointScanner("https://example.com")
    results = await scanner.scan(wordlist=["/admin", "/api", "/.env"])
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

import aiohttp
from aiohttp import ClientTimeout, TCPConnector

logger = logging.getLogger(__name__)


class EndpointError(Exception):
    """Base exception for endpoint scanner failures."""


@dataclass
class EndpointResult:
    """Represents a discovered endpoint check result."""

    path: str
    url: str
    status: int
    content_length: int = 0
    content_type: str = ""
    response_time_ms: float = 0.0
    redirect_url: Optional[str] = None
    keywords_found: list[str] = field(default_factory=list)


class EndpointScanner:
    """Scans a target web application for hidden or unlinked endpoints.

    Attributes:
        base_url:         Target URL (scheme + host, e.g. ``https://example.com``).
        concurrency:      Maximum simultaneous HTTP requests.
        timeout:          Request timeout in seconds.
        user_agent:       User-Agent header value.
        follow_redirects: Whether to follow HTTP redirects (default False).
    """

    DEFAULT_WORDLIST: list[str] = [
        "/admin",
        "/api",
        "/api/v1",
        "/api/v2",
        "/backup",
        "/config",
        "/config.json",
        "/config.xml",
        "/config.php",
        "/cron",
        "/css",
        "/dashboard",
        "/db",
        "/debug",
        "/error",
        "/error_log",
        "/favicon.ico",
        "/health",
        "/healthcheck",
        "/index.html",
        "/info",
        "/info.php",
        "/js",
        "/login",
        "/logout",
        "/logs",
        "/maintenance",
        "/phpinfo.php",
        "/private",
        "/reset",
        "/robots.txt",
        "/sitemap.xml",
        "/sql",
        "/src",
        "/status",
        "/swagger",
        "/swagger.json",
        "/swagger.yaml",
        "/test",
        "/tmp",
        "/upload",
        "/uploads",
        "/vendor",
        "/webpack",
        "/webroot",
        "/wp-admin",
        "/wp-content",
        "/wp-includes",
        "/wp-json",
        ".env",
        ".git/HEAD",
        ".gitignore",
        ".htaccess",
        "Dockerfile",
        "package.json",
        "robots.txt",
        "sitemap.xml",
    ]

    SENSITIVE_KEYWORDS: list[str] = [
        "password",
        "secret",
        "api_key",
        "api-key",
        "token",
        "database",
        "db_password",
        "ssh",
        "private_key",
        "access_key",
        "credentials",
    ]

    def __init__(
        self,
        base_url: str,
        *,
        concurrency: int = 10,
        timeout: float = 15.0,
        user_agent: str = "GenesisQA-EndpointScanner/0.1.0",
        follow_redirects: bool = False,
    ) -> None:
        if not base_url or not isinstance(base_url, str):
            raise ValueError("base_url must be a non-empty string")

        self.base_url = base_url.rstrip("/")
        self.concurrency = concurrency
        self.timeout = timeout
        self.user_agent = user_agent
        self.follow_redirects = follow_redirects

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def scan(
        self,
        wordlist: Optional[list[str]] = None,
        *,
        status_filter: Optional[set[int]] = None,
        max_results: Optional[int] = None,
    ) -> list[EndpointResult]:
        """Scan *base_url* with the given *wordlist*.

        Args:
            wordlist:      Paths/endpoints to probe. Defaults to
                           ``DEFAULT_WORDLIST`` if ``None``.
            status_filter: Only return results matching these HTTP statuses.
                           Example: ``{200, 301, 403}``.
            max_results:   Stop after discovering this many results.

        Returns:
            A list of endpoint discovery results.
        """
        paths = wordlist if wordlist is not None else self.DEFAULT_WORDLIST
        logger.info(
            "Scanning %s with %d paths (status_filter=%s, max_results=%s)",
            self.base_url,
            len(paths),
            status_filter,
            max_results,
        )

        semaphore = asyncio.Semaphore(self.concurrency)

        connector = TCPConnector(limit=self.concurrency, force_close=True)
        timeout_obj = ClientTimeout(total=self.timeout)

        results: list[EndpointResult] = []

        async with aiohttp.ClientSession(
            connector=connector,
            timeout=timeout_obj,
            headers={"User-Agent": self.user_agent},
        ) as session:
            tasks = [
                self._probe(session, semaphore, path, results, status_filter, max_results)
                for path in paths
            ]
            await asyncio.gather(*tasks, return_exceptions=True)

        logger.info("Endpoint scan complete — %d results", len(results))
        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _probe(
        self,
        session: aiohttp.ClientSession,
        semaphore: asyncio.Semaphore,
        path: str,
        results: list[EndpointResult],
        status_filter: Optional[set[int]],
        max_results: Optional[int],
    ) -> None:
        """Probe a single endpoint path."""
        if max_results is not None and len(results) >= max_results:
            return

        url = f"{self.base_url}/{path.lstrip('/')}"

        async with semaphore:
            start = time.monotonic()
            try:
                async with session.get(
                    url,
                    allow_redirects=self.follow_redirects,
                    ssl=False,
                ) as resp:
                    elapsed = (time.monotonic() - start) * 1000.0
                    body = await resp.text(encoding="utf-8", errors="replace")
            except (asyncio.TimeoutError, aiohttp.ClientError) as exc:
                logger.debug("Probe failed for %s — %s", url, exc)
                return

        if status_filter and resp.status not in status_filter:
            return

        redirect_url: Optional[str] = None
        if resp.status in (301, 302, 303, 307, 308):
            redirect_url = str(resp.url)

        keywords_found = [
            kw for kw in self.SENSITIVE_KEYWORDS if kw in body.lower()
        ]

        result = EndpointResult(
            path=path,
            url=str(resp.url),
            status=resp.status,
            content_length=len(body),
            content_type=resp.content_type or "",
            response_time_ms=round(elapsed, 2),
            redirect_url=redirect_url,
            keywords_found=keywords_found,
        )

        results.append(result)
        logger.info(
            "  [%d] %s (%.0fms, %d bytes)",
            result.status,
            result.url,
            result.response_time_ms,
            result.content_length,
        )
