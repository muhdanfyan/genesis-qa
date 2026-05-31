"""
Genesis QA - Security Scanner Module
=====================================
Runs security checks against a web application target, including:

- HTTP security headers audit (CSP, HSTS, X-Frame-Options, etc.)
- Information disclosure detection (server banners, directory listing)
- Basic injection point discovery (URL params, forms)
- CSRF protection checks
- SSL/TLS best practices

Typical usage:
    scanner = SecurityScanner("https://example.com")
    report = await scanner.run()
"""

from __future__ import annotations

import asyncio
import logging
import re
import ssl
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

import aiohttp
from aiohttp import ClientTimeout, TCPConnector

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


class Severity(Enum):
    """Severity level of a security finding."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class SecurityFinding:
    """A single security finding discovered during the scan."""

    check_name: str
    severity: Severity
    description: str
    detail: str = ""
    recommendation: str = ""


@dataclass
class SecurityReport:
    """Aggregated results of a security scan."""

    target_url: str
    findings: list[SecurityFinding] = field(default_factory=list)
    scan_duration_ms: float = 0.0

    @property
    def count_by_severity(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for f in self.findings:
            counts[f.severity.value] = counts.get(f.severity.value, 0) + 1
        return counts


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------


class SecurityScanner:
    """Performs security checks against a web application.

    Attributes:
        target_url: URL to scan (scheme + host, optionally with path).
        timeout:    HTTP request timeout in seconds.
        user_agent: User-Agent header value.
    """

    HEADER_CHECKS: list[dict[str, Any]] = [
        {
            "name": "Content-Security-Policy",
            "header": "Content-Security-Policy",
            "severity": Severity.HIGH,
            "desc": "Missing Content-Security-Policy header",
            "rec": "Set a CSP header to mitigate XSS and data injection attacks.",
        },
        {
            "name": "Strict-Transport-Security",
            "header": "Strict-Transport-Security",
            "severity": Severity.MEDIUM,
            "desc": "Missing Strict-Transport-Security (HSTS) header",
            "rec": "Add the Strict-Transport-Security header to enforce HTTPS.",
        },
        {
            "name": "X-Content-Type-Options",
            "header": "X-Content-Type-Options",
            "severity": Severity.MEDIUM,
            "desc": "Missing X-Content-Type-Options: nosniff header",
            "rec": "Set X-Content-Type-Options: nosniff to prevent MIME sniffing.",
        },
        {
            "name": "X-Frame-Options",
            "header": "X-Frame-Options",
            "severity": Severity.MEDIUM,
            "desc": "Missing X-Frame-Options header",
            "rec": "Set X-Frame-Options: DENY or SAMEORIGIN to prevent clickjacking.",
        },
        {
            "name": "X-XSS-Protection",
            "header": "X-XSS-Protection",
            "severity": Severity.LOW,
            "desc": "Missing X-XSS-Protection header",
            "rec": "Consider adding X-XSS-Protection: 1; mode=block (legacy browser support).",
        },
        {
            "name": "Referrer-Policy",
            "header": "Referrer-Policy",
            "severity": Severity.LOW,
            "desc": "Missing Referrer-Policy header",
            "rec": "Set Referrer-Policy to control referrer information leakage.",
        },
        {
            "name": "Permissions-Policy",
            "header": "Permissions-Policy",
            "severity": Severity.LOW,
            "desc": "Missing Permissions-Policy header",
            "rec": "Set Permissions-Policy to restrict browser feature access.",
        },
    ]

    SERVER_BANNER_SENSITIVE = re.compile(
        r"^(Apache|nginx|Microsoft-IIS|Tomcat|Jetty|Node\.js|Express)", re.IGNORECASE
    )
    GENERIC_500_REGEX = re.compile(
        r"(?:Stack trace|Traceback|Fatal error|Warning:|Notice:|Parse error|SQL syntax)",
        re.IGNORECASE,
    )
    FORM_ACTION_REGEX = re.compile(
        r'<form[^>]*\saction\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE
    )

    def __init__(
        self,
        target_url: str,
        *,
        timeout: float = 20.0,
        user_agent: str = "GenesisQA-SecurityScanner/0.1.0",
    ) -> None:
        if not target_url or not isinstance(target_url, str):
            raise ValueError("target_url must be a non-empty string")

        self.target_url = target_url.rstrip("/")
        self.timeout = timeout
        self.user_agent = user_agent

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self) -> SecurityReport:
        """Execute all security checks against *target_url*.

        Returns:
            A ``SecurityReport`` containing all findings.
        """
        start = time.monotonic()
        logger.info("Starting security scan of %s", self.target_url)

        findings: list[SecurityFinding] = []

        connector = TCPConnector(limit=10, force_close=True)
        timeout_obj = ClientTimeout(total=self.timeout)

        async with aiohttp.ClientSession(
            connector=connector,
            timeout=timeout_obj,
            headers={"User-Agent": self.user_agent},
        ) as session:
            response = await self._fetch_main_page(session)

            if response is None:
                findings.append(
                    SecurityFinding(
                        check_name="Connectivity",
                        severity=Severity.CRITICAL,
                        description=f"Unable to reach {self.target_url}",
                        detail="The target did not respond within the timeout period.",
                        recommendation="Verify the URL is correct and the server is reachable.",
                    )
                )
                elapsed = (time.monotonic() - start) * 1000.0
                return SecurityReport(
                    target_url=self.target_url,
                    findings=findings,
                    scan_duration_ms=round(elapsed, 2),
                )

            # Run all checks concurrently
            check_tasks = [
                self._check_headers(response, findings),
                self._check_server_banner(response, findings),
                self._check_error_disclosure(session, response, findings),
                self._check_ssl(session, findings),
                self._check_csrf_protection(response, findings),
                self._check_injection_points(response, findings),
            ]
            await asyncio.gather(*check_tasks, return_exceptions=True)

        elapsed = (time.monotonic() - start) * 1000.0
        logger.info(
            "Security scan complete — %d findings in %.0fms",
            len(findings),
            elapsed,
        )
        return SecurityReport(
            target_url=self.target_url,
            findings=findings,
            scan_duration_ms=round(elapsed, 2),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _fetch_main_page(
        self, session: aiohttp.ClientSession
    ) -> Optional[aiohttp.ClientResponse]:
        """Fetch the main page of the target."""
        try:
            resp = await session.get(
                self.target_url,
                allow_redirects=True,
                ssl=False,
            )
            return resp
        except (asyncio.TimeoutError, aiohttp.ClientError) as exc:
            logger.error("Failed to fetch main page: %s", exc)
            return None

    async def _check_headers(
        self,
        response: aiohttp.ClientResponse,
        findings: list[SecurityFinding],
    ) -> None:
        """Check for missing or weak security headers."""
        for check in self.HEADER_CHECKS:
            value = response.headers.get(check["header"])
            if not value:
                findings.append(
                    SecurityFinding(
                        check_name=check["name"],
                        severity=check["severity"],
                        description=check["desc"],
                        recommendation=check["rec"],
                    )
                )
            else:
                logger.debug("  %s: %s", check["header"], value)

    async def _check_server_banner(
        self,
        response: aiohttp.ClientResponse,
        findings: list[SecurityFinding],
    ) -> None:
        """Check for information disclosure via Server header."""
        server = response.headers.get("Server")
        if server:
            if self.SERVER_BANNER_SENSITIVE.match(server):
                verb = "identifies"
            else:
                verb = "may identify"
            findings.append(
                SecurityFinding(
                    check_name="Server Banner Disclosure",
                    severity=Severity.LOW,
                    description=f"Server header {verb} the software as '{server}'",
                    detail=f"Header value: {server}",
                    recommendation="Remove or obfuscate the Server header in production.",
                )
            )

        powered_by = response.headers.get("X-Powered-By")
        if powered_by:
            findings.append(
                SecurityFinding(
                    check_name="X-Powered-By Disclosure",
                    severity=Severity.LOW,
                    description=f"X-Powered-By header reveals: '{powered_by}'",
                    detail=f"Header value: {powered_by}",
                    recommendation="Remove the X-Powered-By header in production.",
                )
            )

    async def _check_error_disclosure(
        self,
        session: aiohttp.ClientSession,
        response: aiohttp.ClientResponse,
        findings: list[SecurityFinding],
    ) -> None:
        """Probe for error pages that leak stack traces."""
        error_paths = [
            "/nonexistent-test-path-12345",
            "/../",
            "/?.php",
            "/admin/../",
        ]

        for path in error_paths:
            url = f"{self.target_url}{path}"
            try:
                async with session.get(url, allow_redirects=False, ssl=False) as resp:
                    if resp.status in (500, 200):
                        body = await resp.text(encoding="utf-8", errors="replace")
                        if self.GENERIC_500_REGEX.search(body):
                            findings.append(
                                SecurityFinding(
                                    check_name="Error Disclosure",
                                    severity=Severity.HIGH,
                                    description="Application leaks error/debug information",
                                    detail=(
                                        f"Path '{path}' returned status {resp.status} "
                                        "with stack trace / debug output."
                                    ),
                                    recommendation="Disable detailed error messages in production; "
                                    "use a generic error page.",
                                )
                            )
                            break
            except (asyncio.TimeoutError, aiohttp.ClientError):
                continue

    async def _check_ssl(
        self,
        session: aiohttp.ClientSession,
        findings: list[SecurityFinding],
    ) -> None:
        """Check SSL/TLS certificate and best practices (info-level)."""
        if not self.target_url.startswith("https://"):
            findings.append(
                SecurityFinding(
                    check_name="HTTPS Enforcement",
                    severity=Severity.HIGH,
                    description="Target is not served over HTTPS",
                    recommendation="Enforce HTTPS with a valid TLS certificate and redirect HTTP traffic.",
                )
            )
            return

        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = True
            ctx.verify_mode = ssl.CERT_REQUIRED

            connector = TCPConnector(ssl=ctx)
            async with aiohttp.ClientSession(connector=connector) as ssl_session:
                async with ssl_session.get(
                    self.target_url,
                    allow_redirects=False,
                    timeout=ClientTimeout(total=10),
                ) as resp:
                    logger.debug("SSL connection succeeded for %s", self.target_url)
        except ssl.SSLCertVerificationError as exc:
            findings.append(
                SecurityFinding(
                    check_name="SSL Certificate Validation",
                    severity=Severity.HIGH,
                    description=f"SSL certificate verification failed: {exc}",
                    recommendation="Replace or fix the TLS certificate on the server.",
                )
            )
        except aiohttp.ClientConnectorCertificateError as exc:
            findings.append(
                SecurityFinding(
                    check_name="SSL Certificate Error",
                    severity=Severity.HIGH,
                    description=f"Certificate error: {exc}",
                    recommendation="Ensure a valid, trusted TLS certificate is installed.",
                )
            )
        except (asyncio.TimeoutError, aiohttp.ClientError) as exc:
            findings.append(
                SecurityFinding(
                    check_name="SSL Connection",
                    severity=Severity.MEDIUM,
                    description=f"Could not establish SSL connection: {exc}",
                    recommendation="Check network connectivity and TLS configuration.",
                )
            )

    async def _check_csrf_protection(
        self,
        response: aiohttp.ClientResponse,
        findings: list[SecurityFinding],
    ) -> None:
        """Check for basic CSRF protection signals."""
        body = await response.text(encoding="utf-8", errors="replace")

        # Look for common CSRF token patterns
        csrf_signals = [
            "csrf",
            "csrf_token",
            "csrf-token",
            "_csrf",
            "csrfmiddlewaretoken",
            "authenticity_token",
            "__RequestVerificationToken",
            "xsrf-token",
        ]

        forms = self.FORM_ACTION_REGEX.findall(body)
        if forms:
            body_lower = body.lower()
            has_csrf = any(signal in body_lower for signal in csrf_signals)

            if not has_csrf:
                found_forms_str = ", ".join(forms[:5])
                findings.append(
                    SecurityFinding(
                        check_name="CSRF Protection",
                        severity=Severity.MEDIUM,
                        description="Forms detected without CSRF tokens",
                        detail=f"Found {len(forms)} form(s) — no CSRF token detected. "
                        f"Sample actions: {found_forms_str}",
                        recommendation="Implement anti-CSRF tokens for all state-changing forms.",
                    )
                )

    async def _check_injection_points(
        self,
        response: aiohttp.ClientResponse,
        findings: list[SecurityFinding],
    ) -> None:
        """Identify potential injection points (URL params, forms) — info only."""
        body = await response.text(encoding="utf-8", errors="replace")

        params: list[str] = []
        for match in re.finditer(r'<input[^>]*\sname\s*=\s*["\']([^"\']+)["\']', body, re.IGNORECASE):
            params.append(match.group(1))

        actions = self.FORM_ACTION_REGEX.findall(body)

        if params:
            param_sample = ", ".join(params[:10])
            findings.append(
                SecurityFinding(
                    check_name="Injection Points Discovered",
                    severity=Severity.INFO,
                    description=f"Found {len(params)} input parameter(s) on the page",
                    detail=f"Parameters: {param_sample}",
                    recommendation="Ensure all inputs are properly validated and sanitized.",
                )
            )

        if actions:
            action_sample = ", ".join(actions[:5])
            findings.append(
                SecurityFinding(
                    check_name="Form Endpoints",
                    severity=Severity.INFO,
                    description=f"Found {len(actions)} form submission endpoint(s)",
                    detail=f"Actions: {action_sample}",
                    recommendation="Review form handlers for proper input validation, "
                    "authentication, and CSRF protection.",
                )
            )
