"""
Genesis QA - Base Test Engine
==============================
Abstract base class for all test engines. Defines the common interface
and utility methods that every engine must implement.

Usage:
    class MyEngine(BaseEngine):
        def run(self, scenario: ScenarioConfig) -> TestResult:
            ...
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class PerformanceResult:
    """Aggregate statistics from a performance / load test.

    Attributes:
        avg_ms:               Average (mean) response time in milliseconds.
        p50_ms:               50th percentile (median) response time.
        p95_ms:               95th percentile response time.
        p99_ms:               99th percentile response time.
        min_ms:               Minimum observed response time.
        max_ms:               Maximum observed response time.
        total_requests:       Total number of requests sent.
        failed_requests:      Number of requests that failed (timeout / error).
        throughput_req_per_sec: Achieved throughput (requests / second).
        endpoint:             The endpoint URL that was tested.
        method:               HTTP method used.
    """

    avg_ms: float = 0.0
    p50_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    min_ms: float = 0.0
    max_ms: float = 0.0
    total_requests: int = 0
    failed_requests: int = 0
    throughput_req_per_sec: float = 0.0
    endpoint: str = ""
    method: str = ""
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


@dataclass
class TestResult:
    """Represents the outcome of a single test execution.

    Attributes:
        name:                 Human-readable test name.
        passed:               Whether the test passed.
        status_code:          Actual HTTP response status code (0 on failure).
        expected_status:      Expected status code or list of acceptable codes.
        endpoint:             The endpoint URL that was tested.
        method:               HTTP method used.
        timing_ms:            Response time in milliseconds.
        error:                Error message if the test failed.
        response_body_preview: Truncated response body snippet.
        timestamp:            ISO-formatted UTC timestamp of the test run.
        details:              Optional extended details / assertions checked.
    """

    name: str = ""
    passed: bool = False
    status_code: int = 0
    expected_status: list[int] = field(default_factory=list)
    endpoint: str = ""
    method: str = ""
    timing_ms: float = 0.0
    error: str = ""
    response_body_preview: str = ""
    timestamp: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


@dataclass
class ScenarioConfig:
    """Configuration for a single test scenario.

    Attributes:
        name:             Test scenario name.
        method:           HTTP method (GET, POST, PUT, DELETE, etc.).
        endpoint:         API endpoint path (e.g. /api/users).
        headers:          Request headers.
        body:             Request body (dict or None).
        expected_status:  Expected status code or list of acceptable codes.
        expected_contains: Optional substring(s) to find in response body.
        follow_redirects: Whether to follow HTTP redirects.
        timeout:          Request timeout in seconds.
        retries:          Number of retries on timeout/failure.
    """

    name: str = ""
    method: str = "GET"
    endpoint: str = "/"
    headers: dict[str, str] = field(default_factory=dict)
    body: Optional[dict[str, Any]] = None
    expected_status: list[int] = field(default_factory=lambda: [200])
    expected_contains: Optional[list[str]] = None
    follow_redirects: bool = True
    timeout: float = 30.0
    retries: int = 1


class BaseEngine(ABC):
    """Abstract base test engine.

    All engines inherit from this class and must implement the
    :meth:`run` method. Common assertion and logging utilities are
    provided for subclasses to use.
    """

    def __init__(self, base_url: str, *, timeout: float = 30.0) -> None:
        """Initialize the engine with a target base URL.

        Args:
            base_url: Base URL of the system under test (e.g. https://api.example.com).
            timeout:  Default request timeout in seconds.
        """
        if not base_url or not isinstance(base_url, str):
            raise ValueError("base_url must be a non-empty string")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        logger.debug(
            "%s initialized with base_url=%s, timeout=%s",
            self.__class__.__name__,
            self.base_url,
            self.timeout,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @abstractmethod
    def run(self, scenario: ScenarioConfig) -> TestResult:
        """Execute a single test scenario and return the result.

        Args:
            scenario: The scenario configuration to execute.

        Returns:
            A ``TestResult`` describing the outcome.
        """
        ...

    # ------------------------------------------------------------------
    # Assertion helpers
    # ------------------------------------------------------------------

    def _assert_status(self, status_code: int, expected: list[int]) -> bool:
        """Assert that an HTTP status code matches the expected value(s).

        Args:
            status_code: Actual response status code.
            expected:    List of acceptable status codes.

        Returns:
            ``True`` if the status code is in the expected list.
        """
        return status_code in expected

    def _assert_contains(
        self, body: str, expected_substrings: Optional[list[str]]
    ) -> str:
        """Assert that the response body contains expected substrings.

        Args:
            body:               The response body string.
            expected_substrings: List of substrings to check, or ``None``.

        Returns:
            An error message if any substring is missing, otherwise an
            empty string.
        """
        if not expected_substrings:
            return ""
        body_lower = body.lower()
        missing: list[str] = []
        for s in expected_substrings:
            if s.lower() not in body_lower:
                missing.append(s)
        if missing:
            return f"Response body missing expected content: {missing}"
        return ""

    # ------------------------------------------------------------------
    # Logging helper
    # ------------------------------------------------------------------

    def _log_result(self, result: TestResult) -> None:
        """Log a test result at the appropriate level.

        Args:
            result: The test result to log.
        """
        status = "PASS" if result.passed else "FAIL"
        msg = (
            f"[{status}] {result.method} {result.endpoint} "
            f"-> {result.status_code} (expected {result.expected_status}) "
            f"in {result.timing_ms:.0f}ms"
        )
        if result.passed:
            logger.info(msg)
        else:
            logger.warning("%s — %s", msg, result.error)
