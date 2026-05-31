"""
Genesis QA - Redirect Test Engine
==================================
Tests HTTP redirect chains, detects redirect loops, and validates
that method and scheme are preserved for 307/308 redirects.

Usage:
    engine = RedirectEngine("https://example.com")
    result = engine.test_redirect_chain("/old-path")
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import requests
from requests.exceptions import RequestException

from test.base_engine import BaseEngine, TestResult, ScenarioConfig

logger = logging.getLogger(__name__)


class RedirectEngine(BaseEngine):
    """Engine for testing HTTP redirect behavior.

    Features:
    - Follow and validate redirect chains up to ``MAX_HOPS``.
    - Detect redirect loops.
    - Ensure 307/308 preserve the original HTTP method.
    - Ensure scheme (http/https) is preserved where expected.
    """

    MAX_HOPS: int = 10

    REDIRECT_STATUSES: set[int] = {301, 302, 303, 307, 308}

    METHOD_PRESERVING_STATUSES: set[int] = {307, 308}

    def __init__(self, base_url: str, *, timeout: float = 30.0) -> None:
        super().__init__(base_url, timeout=timeout)
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "GenesisQA-RedirectEngine/0.1.0",
            }
        )

    def run(self, scenario: ScenarioConfig) -> TestResult:
        """Run a redirect test scenario."""
        return self.test_redirect_chain(
            endpoint=scenario.endpoint,
            method=scenario.method,
            follow_redirects=scenario.follow_redirects,
        )

    def test_redirect_chain(
        self,
        endpoint: str,
        method: str = "GET",
        follow_redirects: bool = True,
        expected_final_status: Optional[list[int]] = None,
    ) -> TestResult:
        """Test a redirect chain starting from *endpoint*.

        Args:
            endpoint:             Starting URL or path.
            method:               HTTP method.
            follow_redirects:     Whether to follow redirects (use our own
                                  chain-following logic for validation).
            expected_final_status: Acceptable final status codes.

        Returns:
            A ``TestResult`` describing the redirect chain.
        """
        expected_final_status = expected_final_status or [200, 201, 204]
        url = endpoint if endpoint.startswith("http") else f"{self.base_url}{endpoint}"
        start = __import__("time").monotonic()

        # --- Manual redirect chain following (to detect loops) ---
        chain: list[dict[str, Any]] = []
        visited_urls: set[str] = set()
        current_url = url
        current_method = method.upper()
        final_status = 0
        error = ""
        body = ""

        for hop in range(self.MAX_HOPS + 1):
            if current_url in visited_urls:
                error = f"Redirect loop detected at hop {hop}: {current_url}"
                break
            visited_urls.add(current_url)

            try:
                resp = self.session.request(
                    method=current_method,
                    url=current_url,
                    allow_redirects=False,  # We follow manually
                    timeout=self.timeout,
                )
            except RequestException as exc:
                error = f"Request at hop {hop}: {exc}"
                final_status = 0
                break

            chain.append(
                {
                    "hop": hop,
                    "url": current_url,
                    "method": current_method,
                    "status": resp.status_code,
                    "location": resp.headers.get("Location", ""),
                }
            )

            if resp.status_code in self.REDIRECT_STATUSES:
                location = resp.headers.get("Location", "")
                if not location:
                    error = f"Redirect status {resp.status_code} at hop {hop} without Location header"
                    break

                # Resolve relative redirect
                from urllib.parse import urljoin

                next_url = urljoin(current_url, location)

                # 307/308 must preserve method
                if resp.status_code in self.METHOD_PRESERVING_STATUSES:
                    # Method stays the same
                    pass
                elif resp.status_code == 303:
                    # 303 always changes to GET
                    current_method = "GET"
                else:
                    # 301/302 — conventionally changes to GET (browsers do this)
                    if current_method != "GET":
                        current_method = "GET"

                current_url = next_url

            else:
                final_status = resp.status_code
                body = resp.text
                break

        else:
            if not error:
                error = f"Redirect chain exceeded {self.MAX_HOPS} hops (possible loop)"

        elapsed_ms = round((__import__("time").monotonic() - start) * 1000.0, 2)

        passed = not error and self._assert_status(final_status, expected_final_status)

        # --- Method preservation check for 307/308 ---
        method_issues: list[str] = []
        for entry in chain:
            if entry["status"] in self.METHOD_PRESERVING_STATUSES:
                if entry["method"] != method.upper():
                    method_issues.append(
                        f"Hop {entry['hop']}: 307/308 but method changed from "
                        f"{method} to {entry['method']}"
                    )
        if method_issues:
            error = (error + "; " if error else "") + "; ".join(method_issues)

        # --- Scheme preservation check ---
        scheme_issues: list[str] = []
        initial_scheme = url.split("://")[0] if "://" in url else "https"
        for entry in chain[1:]:  # Skip first (it's the original URL)
            entry_scheme = entry["url"].split("://")[0] if "://" in entry["url"] else ""
            if entry_scheme and entry_scheme != initial_scheme:
                scheme_issues.append(
                    f"Hop {entry['hop']}: scheme changed from {initial_scheme} to {entry_scheme}"
                )
        if scheme_issues:
            error = (error + "; " if error else "") + "; ".join(scheme_issues)

        result = TestResult(
            name=f"Redirect chain: {method} {endpoint}",
            passed=passed and not method_issues,
            status_code=final_status,
            expected_status=expected_final_status,
            endpoint=url,
            method=method,
            timing_ms=elapsed_ms,
            error=error,
            response_body_preview=body[:500] if body else "",
            details={
                "hops": len(chain),
                "chain": chain,
                "max_hops_allowed": self.MAX_HOPS,
                "loop_detected": "Redirect loop" in error,
                "method_preserved": not method_issues,
                "scheme_preserved": not scheme_issues,
            },
        )

        self._log_result(result)
        return result
