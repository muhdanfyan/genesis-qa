"""
Genesis QA - HTTP Test Engine
==============================
Executes HTTP requests against endpoints and validates responses.
Supports timing, retry on timeout, and redirect following.

Usage:
    engine = HttpEngine("https://api.example.com")
    result = engine.execute("GET", "/health", expected_status=[200])
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional, Union

import requests
from requests.exceptions import ConnectionError, Timeout, RequestException

from test.base_engine import BaseEngine, ScenarioConfig, TestResult

logger = logging.getLogger(__name__)


class HttpEngine(BaseEngine):
    """Test engine that executes HTTP requests with timing and retry logic.

    Attributes:
        session: Reusable ``requests.Session`` instance.
    """

    DEFAULT_TIMEOUT: float = 30.0
    MAX_RETRIES: int = 3

    def __init__(self, base_url: str, *, timeout: float = DEFAULT_TIMEOUT) -> None:
        """Initialize the HTTP engine.

        Args:
            base_url: Base URL of the target system.
            timeout:  Default request timeout in seconds.
        """
        super().__init__(base_url, timeout=timeout)
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "GenesisQA-HttpEngine/0.1.0",
                "Accept": "*/*",
            }
        )

    def run(self, scenario: ScenarioConfig) -> TestResult:
        """Execute a test scenario by making an HTTP request.

        This is the polymorphic ``BaseEngine.run()`` implementation.

        Args:
            scenario: The scenario configuration.

        Returns:
            A ``TestResult``.
        """
        return self.execute(
            method=scenario.method,
            url=scenario.endpoint,
            headers=scenario.headers,
            body=scenario.body,
            expected_status=scenario.expected_status,
            follow_redirects=scenario.follow_redirects,
            timeout=scenario.timeout,
            retries=scenario.retries,
        )

    def execute(
        self,
        method: str,
        url: str,
        headers: Optional[dict[str, str]] = None,
        body: Optional[Any] = None,
        expected_status: Optional[list[int]] = None,
        follow_redirects: bool = True,
        timeout: Optional[float] = None,
        retries: int = 1,
    ) -> TestResult:
        """Execute an HTTP request and return a structured result.

        Args:
            method:           HTTP method (GET, POST, PUT, PATCH, DELETE, etc.).
            url:              Endpoint path (e.g. /api/users) or full URL.
            headers:          Request headers.
            body:             Request body. Can be a dict (auto-JSON-serialized),
                              a string, bytes, or ``None``.
            expected_status:  List of acceptable HTTP status codes.
            follow_redirects: Whether to follow HTTP redirects.
            timeout:          Per-request timeout in seconds (default: instance default).
            retries:          Number of retries on timeout/connection failure.

        Returns:
            A ``TestResult`` with the outcome.
        """
        expected_status = expected_status or [200]
        effective_timeout = timeout or self.timeout
        method = method.upper()
        endpoint_url = url if url.startswith("http") else f"{self.base_url}{url}"

        last_error: str = ""
        status_code: int = 0
        response_body: str = ""
        start: float = 0.0

        for attempt in range(max(1, retries)):
            start = time.monotonic()
            try:
                prepared_headers = dict(self.session.headers)
                if headers:
                    prepared_headers.update(headers)

                resp = self.session.request(
                    method=method,
                    url=endpoint_url,
                    headers=prepared_headers,
                    json=body if isinstance(body, dict) else None,
                    data=body if not isinstance(body, dict) else None,
                    allow_redirects=follow_redirects,
                    timeout=effective_timeout,
                )
                status_code = resp.status_code
                response_body = resp.text
                last_error = ""
                break

            except Timeout:
                last_error = f"Request timed out after {effective_timeout}s"
                logger.debug(
                    "Attempt %d/%d timed out for %s %s",
                    attempt + 1,
                    retries,
                    method,
                    endpoint_url,
                )
                if attempt + 1 < retries:
                    time.sleep(1.0)

            except ConnectionError as exc:
                last_error = f"Connection error: {exc}"
                logger.debug(
                    "Attempt %d/%d connection error for %s %s: %s",
                    attempt + 1,
                    retries,
                    method,
                    endpoint_url,
                    exc,
                )
                if attempt + 1 < retries:
                    time.sleep(2.0)

            except RequestException as exc:
                last_error = f"Request failed: {exc}"
                logger.debug(
                    "Attempt %d/%d request failed for %s %s: %s",
                    attempt + 1,
                    retries,
                    method,
                    endpoint_url,
                    exc,
                )
                break

        elapsed_ms = round((time.monotonic() - start) * 1000.0, 2)

        # Build the response body preview
        body_preview = ""
        if response_body:
            body_preview = response_body[:500]
            if len(response_body) > 500:
                body_preview += "..."

        # Optional: check response body for expected content
        detail_error = ""
        if not last_error:
            detail_error = self._assert_contains(
                response_body, None
            )

        passed = self._assert_status(status_code, expected_status) and not last_error

        result = TestResult(
            name=f"{method} {url}",
            passed=passed,
            status_code=status_code,
            expected_status=expected_status,
            endpoint=endpoint_url,
            method=method,
            timing_ms=elapsed_ms,
            error=last_error or detail_error,
            response_body_preview=body_preview,
            details={
                "retries_used": max(1, retries),
                "redirects_followed": follow_redirects,
                "response_headers": dict(resp.headers) if status_code else {},
            },
        )

        self._log_result(result)
        return result
