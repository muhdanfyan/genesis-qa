"""
Genesis QA - CORS Test Engine
==============================
Tests Cross-Origin Resource Sharing (CORS) configuration by sending
requests with various Origin headers and inspecting the response for
proper CORS headers.

Usage:
    engine = CorsEngine("https://api.example.com")
    result = engine.test_cors("/api/users", method="GET")
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import requests
from requests.exceptions import RequestException

from test.base_engine import BaseEngine, ScenarioConfig, TestResult

logger = logging.getLogger(__name__)


class CorsEngine(BaseEngine):
    """Engine for testing CORS configuration.

    Sends preflight (OPTIONS) and actual requests with various Origin
    headers and validates that the ``Access-Control-*`` response headers
    are correctly configured.
    """

    TEST_ORIGINS: dict[str, str] = {
        "same": None,  # Will be filled with base_url origin
        "different": "https://attacker.example.com",
        "null": "null",
    }

    REQUIRED_CORS_HEADERS: list[str] = [
        "Access-Control-Allow-Origin",
        "Access-Control-Allow-Methods",
        "Access-Control-Allow-Headers",
    ]

    def __init__(self, base_url: str, *, timeout: float = 30.0) -> None:
        super().__init__(base_url, timeout=timeout)
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "GenesisQA-CorsEngine/0.1.0",
            }
        )
        # Set the "same" origin from base_url
        from urllib.parse import urlparse

        parsed = urlparse(base_url)
        self.TEST_ORIGINS["same"] = f"{parsed.scheme}://{parsed.netloc}"

    def run(self, scenario: ScenarioConfig) -> TestResult:
        """Run a CORS test scenario.

        Delegates to :meth:`test_cors` using the scenario's endpoint and method.
        """
        return self.test_cors(
            endpoint=scenario.endpoint,
            method=scenario.method,
            headers=scenario.headers,
        )

    def test_cors(
        self,
        endpoint: str,
        method: str = "GET",
        headers: Optional[dict[str, str]] = None,
    ) -> TestResult:
        """Test CORS configuration for an endpoint.

        For each test origin (same, different, null), sends an OPTIONS
        preflight request and validates the CORS response headers.

        Args:
            endpoint: API endpoint path (e.g. /api/users).
            method:   HTTP method to test.
            headers:  Additional headers to include.

        Returns:
            A ``TestResult`` with cumulative CORS findings.
        """
        url = endpoint if endpoint.startswith("http") else f"{self.base_url}{endpoint}"
        all_passed = True
        findings: list[str] = []
        details: dict[str, Any] = {}
        start = __import__("time").monotonic()

        for origin_label, origin_value in self.TEST_ORIGINS.items():
            if origin_value is None:
                continue

            origin_result = self._test_origin(url, method, origin_label, origin_value, headers)
            details[origin_label] = origin_result
            if not origin_result.get("passed", False):
                all_passed = False
                findings.append(
                    f"[{origin_label}] {origin_result.get('error', 'CORS check failed')}"
                )

        elapsed_ms = round((__import__("time").monotonic() - start) * 1000.0, 2)

        return TestResult(
            name=f"CORS {method} {endpoint}",
            passed=all_passed,
            status_code=200 if all_passed else 0,
            expected_status=[200, 204],
            endpoint=url,
            method=method,
            timing_ms=elapsed_ms,
            error="; ".join(findings) if findings else "",
            response_body_preview="",
            details={
                "origins_tested": list(self.TEST_ORIGINS.keys()),
                "origin_results": details,
            },
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _test_origin(
        self,
        url: str,
        method: str,
        origin_label: str,
        origin_value: str,
        extra_headers: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        """Test CORS for a single origin value."""
        result: dict[str, Any] = {"origin": origin_value, "passed": True, "error": ""}

        # --- Preflight (OPTIONS) check ---
        try:
            preflight_headers = {
                "Origin": origin_value,
                "Access-Control-Request-Method": method,
            }
            if extra_headers:
                preflight_headers.update(extra_headers)

            pre_resp = self.session.options(
                url, headers=preflight_headers, timeout=self.timeout
            )
        except RequestException as exc:
            result["passed"] = False
            result["error"] = f"OPTIONS preflight failed: {exc}"
            return result

        # Check required CORS headers on preflight
        for header in self.REQUIRED_CORS_HEADERS:
            if header not in pre_resp.headers:
                result["passed"] = False
                result["error"] += f"Missing {header} in preflight; "

        # Validate Access-Control-Allow-Origin
        acao = pre_resp.headers.get("Access-Control-Allow-Origin", "")
        if origin_label == "same":
            # Should echo back the origin or be '*' — check it's not null
            if not acao or acao == "null":
                result["passed"] = False
                result["error"] += (
                    f"ACAO '{acao}' does not allow same-origin; "
                )
        elif origin_label == "different":
            # Should NOT be the different origin (unless wildcard)
            if acao != "*" and (acao and origin_value in acao):
                result["passed"] = False
                result["error"] += f"ACAO allows cross-origin '{origin_value}'; "

        # Check Access-Control-Allow-Credentials
        credentials = pre_resp.headers.get("Access-Control-Allow-Credentials", "")
        if credentials.lower() == "true" and acao == "*":
            result["passed"] = False
            result["error"] += "Credentials allowed with wildcard origin; "

        # Check Max-Age (advisory)
        max_age = pre_resp.headers.get("Access-Control-Max-Age", "")
        result["max_age"] = max_age

        # --- Actual request check ---
        try:
            actual_headers = {"Origin": origin_value}
            if extra_headers:
                actual_headers.update(extra_headers)

            actual_resp = self.session.request(
                method=method,
                url=url,
                headers=actual_headers,
                timeout=self.timeout,
            )
        except RequestException as exc:
            result["passed"] = False
            result["error"] += f"Actual request failed: {exc}; "
            return result

        acao_actual = actual_resp.headers.get("Access-Control-Allow-Origin", "")
        if origin_label == "same" and not acao_actual:
            result["passed"] = False
            result["error"] += "Missing ACAO on actual response; "

        result["preflight_status"] = pre_resp.status_code
        result["actual_status"] = actual_resp.status_code
        result["headers"] = {
            "preflight": dict(pre_resp.headers),
            "actual": dict(actual_resp.headers),
        }

        return result
