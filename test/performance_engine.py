"""
Genesis QA - Performance / Load Test Engine
==============================================
Executes performance, concurrent, stress, and endurance tests against
endpoints. Provides statistical timing output via ``PerformanceResult``.

Usage:
    engine = PerformanceEngine("https://api.example.com")
    result = engine.test_response_time("/health", "GET")
    perf  = engine.test_concurrent("/api/users", num_requests=20, concurrency=5)
    stress = engine.test_stress("/api/users", num_requests=50, ramp_up=5)
    endurance = engine.test_endurance("/health", duration_sec=30, interval_ms=1000)
"""

from __future__ import annotations

import logging
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Optional

import requests

from test.base_engine import BaseEngine, PerformanceResult

logger = logging.getLogger(__name__)


class PerformanceEngine(BaseEngine):
    """Performance / load test engine.

    Attributes:
        session: Reusable ``requests.Session`` instance.
    """

    DEFAULT_TIMEOUT: float = 30.0

    def __init__(self, base_url: str, *, timeout: float = DEFAULT_TIMEOUT) -> None:
        """Initialise the performance engine.

        Args:
            base_url: Base URL of the target system.
            timeout:  Default per-request timeout in seconds.
        """
        super().__init__(base_url, timeout=timeout)
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "GenesisQA-PerformanceEngine/0.1.0",
                "Accept": "*/*",
            }
        )

    # ------------------------------------------------------------------
    # Public API — run() for polymorphic BaseEngine compatibility
    # ------------------------------------------------------------------

    def run(self, scenario: Any) -> PerformanceResult:
        """Placeholder to satisfy the abstract ``BaseEngine.run()`` interface.

        This engine is designed for ad-hoc performance tests rather than
        ``ScenarioConfig``-driven workflows.  Use the dedicated methods
        (``test_response_time``, ``test_concurrent``, …) directly.

        Raises:
            NotImplementedError: Always — use a specific test method instead.
        """
        raise NotImplementedError(
            "PerformanceEngine does not support ScenarioConfig-based run(). "
            "Use test_response_time(), test_concurrent(), test_stress(), "
            "or test_endurance() directly."
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _do_request(
        self,
        endpoint: str,
        method: str = "GET",
        headers: Optional[dict[str, str]] = None,
        body: Optional[Any] = None,
    ) -> tuple[float, int, str]:
        """Execute a single HTTP request and measure its timing.

        Args:
            endpoint: Full URL or path (relative to ``base_url``).
            method:   HTTP method.
            headers:  Optional request headers.
            body:     Optional request body (dict → JSON, other → raw).

        Returns:
            A tuple of (elapsed_ms, status_code, error_message).
        """
        url = endpoint if endpoint.startswith("http") else f"{self.base_url}{endpoint}"
        method = method.upper()
        prepared_headers = dict(self.session.headers)
        if headers:
            prepared_headers.update(headers)

        start = time.monotonic()
        try:
            resp = self.session.request(
                method=method,
                url=url,
                headers=prepared_headers,
                json=body if isinstance(body, dict) else None,
                data=body if not isinstance(body, dict) else None,
                timeout=self.timeout,
            )
            elapsed = (time.monotonic() - start) * 1000.0
            return elapsed, resp.status_code, ""
        except requests.exceptions.Timeout:
            elapsed = (time.monotonic() - start) * 1000.0
            return elapsed, 0, f"Timeout after {self.timeout}s"
        except requests.exceptions.ConnectionError as exc:
            elapsed = (time.monotonic() - start) * 1000.0
            return elapsed, 0, f"Connection error: {exc}"
        except requests.exceptions.RequestException as exc:
            elapsed = (time.monotonic() - start) * 1000.0
            return elapsed, 0, f"Request failed: {exc}"

    def _build_result(
        self,
        timings: list[float],
        errors: list[str],
        endpoint: str,
        method: str,
        threshold_ms: float = 2000.0,
    ) -> PerformanceResult:
        """Compute summary statistics from a list of request timings.

        Args:
            timings:       List of response times in ms.
            errors:        Corresponding error messages (empty string = success).
            endpoint:      The endpoint URL tested.
            method:        HTTP method used.
            threshold_ms:  Alert threshold — if ``avg_ms`` exceeds this a warning
                           is logged.

        Returns:
            A ``PerformanceResult``.
        """
        sorted_t = sorted(timings)
        n = len(sorted_t)
        failed = sum(1 for e in errors if e)
        total = n

        avg_ms = statistics.mean(sorted_t) if sorted_t else 0.0
        p50 = sorted_t[int(n * 0.50)] if n else 0.0
        p95 = sorted_t[int(n * 0.95)] if n else 0.0
        p99 = sorted_t[int(n * 0.99)] if n else 0.0
        min_ms = sorted_t[0] if sorted_t else 0.0
        max_ms = sorted_t[-1] if sorted_t else 0.0
        duration_sec = (sum(timings) / 1000.0) if timings else 0.0
        throughput = total / duration_sec if duration_sec > 0 else 0.0

        result = PerformanceResult(
            avg_ms=round(avg_ms, 2),
            p50_ms=round(p50, 2),
            p95_ms=round(p95, 2),
            p99_ms=round(p99, 2),
            min_ms=round(min_ms, 2),
            max_ms=round(max_ms, 2),
            total_requests=total,
            failed_requests=failed,
            throughput_req_per_sec=round(throughput, 2),
            endpoint=endpoint,
            method=method,
        )

        if avg_ms > threshold_ms:
            logger.warning(
                "[PERF] %s %s — avg %.0fms exceeds threshold %.0fms",
                method,
                endpoint,
                avg_ms,
                threshold_ms,
            )
        else:
            logger.info(
                "[PERF] %s %s — avg %.0fms  p50=%.0fms  p95=%.0fms  p99=%.0fms  "
                "throughput=%.1f req/s",
                method,
                endpoint,
                avg_ms,
                p50,
                p95,
                p99,
                throughput,
            )

        return result

    # ------------------------------------------------------------------
    # Performance test methods
    # ------------------------------------------------------------------

    def test_response_time(
        self,
        endpoint: str,
        method: str = "GET",
        headers: Optional[dict[str, str]] = None,
        body: Optional[Any] = None,
        threshold_ms: float = 2000.0,
    ) -> PerformanceResult:
        """Test single request timing against an endpoint.

        Args:
            endpoint:     URL path or full URL.
            method:       HTTP method.
            headers:      Optional request headers.
            body:         Optional request body.
            threshold_ms: Alert threshold for average response time.

        Returns:
            ``PerformanceResult`` with a single data point.
        """
        timing, status, error = self._do_request(endpoint, method, headers, body)
        return self._build_result(
            timings=[timing],
            errors=[error],
            endpoint=endpoint,
            method=method,
            threshold_ms=threshold_ms,
        )

    def test_concurrent(
        self,
        endpoint: str,
        method: str = "GET",
        headers: Optional[dict[str, str]] = None,
        body: Optional[Any] = None,
        num_requests: int = 10,
        concurrency: int = 5,
        threshold_ms: float = 2000.0,
    ) -> PerformanceResult:
        """Test endpoint under concurrent load using ``ThreadPoolExecutor``.

        Args:
            endpoint:     URL path or full URL.
            method:       HTTP method.
            headers:      Optional request headers.
            body:         Optional request body.
            num_requests: Total number of requests to fire.
            concurrency:  Max number of parallel workers.
            threshold_ms: Alert threshold for average response time.

        Returns:
            ``PerformanceResult`` with aggregate statistics.
        """
        logger.info(
            "[PERF] Concurrent test — %s %s  requests=%d  concurrency=%d",
            method,
            endpoint,
            num_requests,
            concurrency,
        )

        timings: list[float] = []
        errors: list[str] = []

        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [
                executor.submit(self._do_request, endpoint, method, headers, body)
                for _ in range(num_requests)
            ]
            for future in as_completed(futures):
                t, _status, err = future.result()
                timings.append(t)
                errors.append(err)

        return self._build_result(
            timings, errors, endpoint, method, threshold_ms
        )

    def test_stress(
        self,
        endpoint: str,
        method: str = "GET",
        headers: Optional[dict[str, str]] = None,
        body: Optional[Any] = None,
        num_requests: int = 50,
        ramp_up: int = 5,
        threshold_ms: float = 2000.0,
    ) -> PerformanceResult:
        """Stress test endpoint with incrementally increasing concurrency.

        Requests are submitted in ``ramp_up`` waves.  Each wave uses a
        progressively higher concurrency level (1, 2, 3, … ``ramp_up``),
        distributing the total ``num_requests`` evenly across waves.

        Args:
            endpoint:     URL path or full URL.
            method:       HTTP method.
            headers:      Optional request headers.
            body:         Optional request body.
            num_requests: Total number of requests to fire.
            ramp_up:      Number of load steps (each step increases concurrency).
            threshold_ms: Alert threshold for average response time.

        Returns:
            ``PerformanceResult`` with aggregate statistics.
        """
        logger.info(
            "[PERF] Stress test — %s %s  requests=%d  ramp_up=%d",
            method,
            endpoint,
            num_requests,
            ramp_up,
        )

        requests_per_wave = max(1, num_requests // ramp_up)
        timings: list[float] = []
        errors: list[str] = []

        for wave in range(1, ramp_up + 1):
            concurrency = wave
            count = requests_per_wave if wave < ramp_up else (
                num_requests - (requests_per_wave * (ramp_up - 1))
            )

            logger.debug(
                "[PERF]  Stress wave %d/%d — concurrency=%d  requests=%d",
                wave,
                ramp_up,
                concurrency,
                count,
            )

            with ThreadPoolExecutor(max_workers=concurrency) as executor:
                futures = [
                    executor.submit(
                        self._do_request, endpoint, method, headers, body
                    )
                    for _ in range(count)
                ]
                for future in as_completed(futures):
                    t, _status, err = future.result()
                    timings.append(t)
                    errors.append(err)

            # Brief inter-wave cooldown
            time.sleep(0.5)

        return self._build_result(
            timings, errors, endpoint, method, threshold_ms
        )

    def test_endurance(
        self,
        endpoint: str,
        method: str = "GET",
        headers: Optional[dict[str, str]] = None,
        body: Optional[Any] = None,
        duration_sec: int = 30,
        interval_ms: int = 1000,
        threshold_ms: float = 2000.0,
    ) -> PerformanceResult:
        """Endurance (soak) test — keep hitting the endpoint for a set duration.

        Requests are fired at a fixed interval (every ``interval_ms``
        milliseconds) for ``duration_sec`` seconds.

        Args:
            endpoint:     URL path or full URL.
            method:       HTTP method.
            headers:      Optional request headers.
            body:         Optional request body.
            duration_sec: How long the test should run (in seconds).
            interval_ms:  Milliseconds between successive requests.
            threshold_ms: Alert threshold for average response time.

        Returns:
            ``PerformanceResult`` with aggregate statistics.
        """
        logger.info(
            "[PERF] Endurance test — %s %s  duration=%ds  interval=%dms",
            method,
            endpoint,
            duration_sec,
            interval_ms,
        )

        timings: list[float] = []
        errors: list[str] = []
        deadline = time.monotonic() + duration_sec
        interval_sec = interval_ms / 1000.0

        while time.monotonic() < deadline:
            t, _status, err = self._do_request(endpoint, method, headers, body)
            timings.append(t)
            errors.append(err)

            # Sleep for the remainder of the interval
            elapsed_since_start = (  # noqa: F841
                sum(timings) / 1000.0 if timings else 0.0
            )
            time.sleep(max(0.0, interval_sec - (t / 1000.0)))

        return self._build_result(
            timings, errors, endpoint, method, threshold_ms
        )
