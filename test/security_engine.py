"""
Genesis QA - Security Test Engine
==================================
Tests security-related aspects of endpoints including security headers,
sensitive information disclosure, and directory listing.

Usage:
    engine = SecurityEngine("https://example.com")
    result = engine.test_security_headers("/path")
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

import requests
from requests.exceptions import RequestException

from test.base_engine import BaseEngine, TestResult, ScenarioConfig

logger = logging.getLogger(__name__)


class SecurityEngine(BaseEngine):
    """Engine for testing security configuration.

    Checks:
    - Security headers (HSTS, X-Content-Type-Options, X-Frame-Options, CSP, X-XSS-Protection)
    - Sensitive information leakage (stack traces, path disclosure, version banners)
    - Directory listing on common paths
    """

    SECURITY_HEADERS: dict[str, str] = {
        "Strict-Transport-Security": "Missing HSTS header — enforce HTTPS",
        "X-Content-Type-Options": "Missing X-Content-Type-Options: nosniff — MIME sniffing risk",
        "X-Frame-Options": "Missing X-Frame-Options — clickjacking risk",
        "Content-Security-Policy": "Missing CSP header — XSS risk",
        "X-XSS-Protection": "Missing X-XSS-Protection header (legacy)",
    }

    SENSITIVE_PATTERNS: dict[str, str] = {
        r"Traceback \(most recent call last\)": "Python stack trace",
        r"at\s+[\w.]+\.[\w]+\([\w.]+\:\d+\)": "Java stack trace",
        r"in\s+[\w\d_]+\.php on line \d+": "PHP path disclosure",
        r"Warning:\s+.*on line \d+": "PHP warning with path",
        r"Fatal error:\s+": "PHP fatal error",
        r"\/var\/www\/": "Linux web root path disclosure",
        r"\/home\/": "Home directory path disclosure",
        r"Server:\s+Apache/[\d\.]+": "Apache version disclosure",
        r"Server:\s+nginx/[\d\.]+": "Nginx version disclosure",
        r"X-Powered-By:\s+PHP/[\d\.]+": "PHP version disclosure",
        r"X-AspNet-Version:\s+[\d\.]+": "ASP.NET version disclosure",
    }

    DIRECTORY_LISTING_PATTERNS: list[str] = [
        "Index of /",
        "<title>Index of",
        "<h1>Directory Listing:</h1>",
        "Parent Directory</a>",
    ]

    def __init__(self, base_url: str, *, timeout: float = 30.0) -> None:
        super().__init__(base_url, timeout=timeout)
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "GenesisQA-SecurityEngine/0.1.0",
            }
        )

    def run(self, scenario: ScenarioConfig) -> TestResult:
        """Run a security test scenario."""
        name_lower = scenario.name.lower()
        if "header" in name_lower:
            return self.test_security_headers(endpoint=scenario.endpoint)
        elif "disclosure" in name_lower or "leak" in name_lower:
            return self.test_sensitive_info(endpoint=scenario.endpoint)
        elif "directory listing" in name_lower or "dir listing" in name_lower:
            return self.test_directory_listing()
        else:
            # Run all security checks
            header_result = self.test_security_headers(endpoint=scenario.endpoint)
            return header_result

    def test_security_headers(self, endpoint: str = "/") -> TestResult:
        """Check for missing security headers in the response.

        Args:
            endpoint: Endpoint to check.

        Returns:
            A ``TestResult``.
        """
        url = endpoint if endpoint.startswith("http") else f"{self.base_url}{endpoint}"
        start = __import__("time").monotonic()
        error = ""
        status_code = 0
        body = ""
        response_headers: dict[str, str] = {}

        try:
            resp = self.session.get(url, timeout=self.timeout)
            status_code = resp.status_code
            body = resp.text
            response_headers = {k.lower(): v for k, v in resp.headers.items()}
        except RequestException as exc:
            error = f"Request failed: {exc}"

        elapsed_ms = round((__import__("time").monotonic() - start) * 1000.0, 2)

        # Check for missing headers
        missing_headers: list[str] = []
        for header, warning in self.SECURITY_HEADERS.items():
            if header.lower() not in response_headers:
                missing_headers.append(warning)

        if missing_headers:
            error = "; ".join(missing_headers[:5])
            if len(missing_headers) > 5:
                error += f"; ... and {len(missing_headers) - 5} more"

        passed = not error

        result = TestResult(
            name=f"Security Headers: GET {endpoint}",
            passed=passed,
            status_code=status_code,
            expected_status=[200, 301, 302, 403],
            endpoint=url,
            method="GET",
            timing_ms=elapsed_ms,
            error=error,
            response_body_preview=body[:500] if body else "",
            details={
                "missing_headers": missing_headers,
                "present_headers": list(response_headers.keys()),
                "check_count": len(self.SECURITY_HEADERS),
                "missing_count": len(missing_headers),
            },
        )

        self._log_result(result)
        return result

    def test_sensitive_info(self, endpoint: str = "/") -> TestResult:
        """Scan the response for sensitive information disclosure.

        Args:
            endpoint: Endpoint to check.

        Returns:
            A ``TestResult``.
        """
        url = endpoint if endpoint.startswith("http") else f"{self.base_url}{endpoint}"
        start = __import__("time").monotonic()
        error = ""
        status_code = 0
        body = ""
        findings: dict[str, str] = {}

        try:
            resp = self.session.get(url, timeout=self.timeout)
            status_code = resp.status_code
            body = resp.text

            # Check response headers for version disclosure
            header_findings = self._check_header_disclosure(dict(resp.headers))
            findings.update(header_findings)

            # Check response body for sensitive patterns
            body_findings = self._check_body_disclosure(body)
            findings.update(body_findings)

            if findings:
                error = "; ".join(
                    f"{pattern}: {desc}" for pattern, desc in list(findings.items())[:5]
                )

        except RequestException as exc:
            error = f"Request failed: {exc}"

        elapsed_ms = round((__import__("time").monotonic() - start) * 1000.0, 2)
        passed = not error

        result = TestResult(
            name=f"Info Disclosure: GET {endpoint}",
            passed=passed,
            status_code=status_code,
            expected_status=[200],
            endpoint=url,
            method="GET",
            timing_ms=elapsed_ms,
            error=error,
            response_body_preview=body[:500] if body else "",
            details={
                "findings": findings,
                "finding_count": len(findings),
            },
        )

        self._log_result(result)
        return result

    def test_directory_listing(self) -> TestResult:
        """Check common paths for directory listing vulnerabilities.

        Returns:
            A ``TestResult``.
        """
        common_dirs = ["/", "/uploads", "/images", "/css", "/js", "/backup", "/admin"]
        error = ""
        status_code = 0
        findings: list[str] = []
        start = __import__("time").monotonic()

        for dir_path in common_dirs:
            url = f"{self.base_url}{dir_path}"
            try:
                resp = self.session.get(url, timeout=self.timeout)
                body = resp.text
                for pattern in self.DIRECTORY_LISTING_PATTERNS:
                    if pattern in body:
                        findings.append(f"Directory listing at {dir_path}")
                        break
            except RequestException:
                continue

        elapsed_ms = round((__import__("time").monotonic() - start) * 1000.0, 2)

        if findings:
            error = "; ".join(findings)

        passed = not error
        result = TestResult(
            name="Directory Listing Check",
            passed=passed,
            status_code=status_code if status_code else 0,
            expected_status=[200, 403],
            endpoint=self.base_url,
            method="GET",
            timing_ms=elapsed_ms,
            error=error,
            response_body_preview="",
            details={
                "dirs_checked": common_dirs,
                "vulnerable_dirs": findings,
            },
        )

        self._log_result(result)
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _check_header_disclosure(self, headers: dict[str, str]) -> dict[str, str]:
        """Check response headers for version/info disclosure."""
        findings: dict[str, str] = {}
        header_str = "\n".join(f"{k}: {v}" for k, v in headers.items())
        for pattern, description in self.SENSITIVE_PATTERNS.items():
            if re.search(pattern, header_str, re.IGNORECASE):
                findings[pattern] = description
        return findings

    def _check_body_disclosure(self, body: str) -> dict[str, str]:
        """Check response body for sensitive information."""
        findings: dict[str, str] = {}
        for pattern, description in self.SENSITIVE_PATTERNS.items():
            if re.search(pattern, body, re.IGNORECASE):
                findings[pattern] = description
        return findings
