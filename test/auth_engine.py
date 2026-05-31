"""
Genesis QA - Auth Test Engine
==============================
Tests authentication and authorization flows, including login,
token validation, and role-based access control.

Usage:
    engine = AuthEngine("https://api.example.com")
    result = engine.test_login(username="admin", password="secret")
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import requests
from requests.exceptions import RequestException

from test.base_engine import BaseEngine, TestResult, ScenarioConfig

logger = logging.getLogger(__name__)


class AuthEngine(BaseEngine):
    """Engine for testing authentication flows.

    Supports:
    - Login with credentials
    - Token validation
    - Role-based access control (RBAC)
    - Invalid credential rejection
    - Session expiry / reuse
    """

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 30.0,
        credentials: Optional[dict[str, str]] = None,
    ) -> None:
        """Initialize the auth engine.

        Args:
            base_url:     Base URL of the target system.
            timeout:      Request timeout in seconds.
            credentials:  Optional dict of role -> {username, password}.
                          Example: {"admin": {"username": "admin", "password": "secret"}}
        """
        super().__init__(base_url, timeout=timeout)
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "GenesisQA-AuthEngine/0.1.0",
                "Content-Type": "application/json",
            }
        )
        self.credentials: dict[str, dict[str, str]] = credentials or {}
        self._tokens: dict[str, str] = {}

    def run(self, scenario: ScenarioConfig) -> TestResult:
        """Run an auth test scenario.

        Delegates based on scenario name patterns or custom logic.
        Default: treat as a login test.
        """
        name_lower = scenario.name.lower()
        if "login" in name_lower or "authenticate" in name_lower:
            return self.test_login(
                username=scenario.body.get("username", "") if scenario.body else "",
                password=scenario.body.get("password", "") if scenario.body else "",
                endpoint=scenario.endpoint,
            )
        elif "token" in name_lower:
            return self.test_token_validation(
                token=scenario.headers.get("Authorization", ""),
                endpoint=scenario.endpoint,
            )
        else:
            return self.test_role_access(
                role="user",
                endpoint=scenario.endpoint,
                method=scenario.method,
            )

    def test_login(
        self,
        username: str,
        password: str,
        endpoint: str = "/auth/login",
        expected_status: Optional[list[int]] = None,
    ) -> TestResult:
        """Test a login endpoint with provided credentials.

        Args:
            username:        Login username.
            password:        Login password.
            endpoint:        Login endpoint path.
            expected_status: Acceptable status codes for successful auth.

        Returns:
            A ``TestResult``.
        """
        expected_status = expected_status or [200]
        url = endpoint if endpoint.startswith("http") else f"{self.base_url}{endpoint}"
        start = __import__("time").monotonic()
        error = ""
        status_code = 0
        body = ""
        token = ""

        try:
            resp = self.session.post(
                url,
                json={"username": username, "password": password},
                timeout=self.timeout,
            )
            status_code = resp.status_code
            body = resp.text

            if status_code in expected_status:
                # Try to extract token from response
                try:
                    data = resp.json()
                    token = data.get("token") or data.get("access_token") or data.get("id_token") or ""
                except ValueError:
                    token = ""
            else:
                error = f"Expected {expected_status}, got {status_code}"

        except RequestException as exc:
            error = f"Login request failed: {exc}"

        elapsed_ms = round((__import__("time").monotonic() - start) * 1000.0, 2)
        passed = not error and self._assert_status(status_code, expected_status)

        result = TestResult(
            name=f"Login: {username}",
            passed=passed,
            status_code=status_code,
            expected_status=expected_status,
            endpoint=url,
            method="POST",
            timing_ms=elapsed_ms,
            error=error,
            response_body_preview=body[:500] if body else "",
            details={
                "username": username,
                "token_extracted": bool(token),
            },
        )

        self._log_result(result)
        return result

    def test_token_validation(
        self,
        token: str,
        endpoint: str = "/auth/me",
        expected_status: Optional[list[int]] = None,
    ) -> TestResult:
        """Test a token validation endpoint.

        Args:
            token:           Bearer token or authorization string.
            endpoint:        Token validation endpoint.
            expected_status: Acceptable status codes.

        Returns:
            A ``TestResult``.
        """
        expected_status = expected_status or [200]
        url = endpoint if endpoint.startswith("http") else f"{self.base_url}{endpoint}"
        start = __import__("time").monotonic()
        error = ""
        status_code = 0
        body = ""

        try:
            resp = self.session.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.timeout,
            )
            status_code = resp.status_code
            body = resp.text
            if status_code not in expected_status:
                error = f"Expected {expected_status}, got {status_code}"
        except RequestException as exc:
            error = f"Token validation failed: {exc}"

        elapsed_ms = round((__import__("time").monotonic() - start) * 1000.0, 2)
        passed = not error and self._assert_status(status_code, expected_status)

        result = TestResult(
            name="Token Validation",
            passed=passed,
            status_code=status_code,
            expected_status=expected_status,
            endpoint=url,
            method="GET",
            timing_ms=elapsed_ms,
            error=error,
            response_body_preview=body[:500] if body else "",
            details={"token_prefix": token[:20] + "..." if len(token) > 20 else token},
        )

        self._log_result(result)
        return result

    def test_role_access(
        self,
        role: str,
        endpoint: str,
        method: str = "GET",
        expected_allowed: Optional[list[int]] = None,
        expected_denied: Optional[list[int]] = None,
    ) -> TestResult:
        """Test role-based access to an endpoint.

        Args:
            role:             Role name (must exist in ``credentials``).
            endpoint:         Endpoint to test.
            method:           HTTP method.
            expected_allowed: Status codes that indicate allowed access.
            expected_denied:  Status codes that indicate denied access.

        Returns:
            A ``TestResult``.
        """
        expected_allowed = expected_allowed or [200, 201, 204]
        expected_denied = expected_denied or [401, 403]
        url = endpoint if endpoint.startswith("http") else f"{self.base_url}{endpoint}"

        # Try to authenticate first if credentials available
        token = ""
        error = ""
        status_code = 0
        body = ""

        if role in self.credentials:
            creds = self.credentials[role]
            login_result = self.test_login(
                username=creds.get("username", ""),
                password=creds.get("password", ""),
            )
            if login_result.passed:
                # Re-extract token from login result details
                if login_result.status_code in [200]:
                    try:
                        import json
                        data = json.loads(login_result.response_body_preview) if login_result.response_body_preview else {}
                        token = data.get("token") or data.get("access_token") or ""
                    except (json.JSONDecodeError, AttributeError):
                        token = ""

        start = __import__("time").monotonic()

        if not token:
            # No auth — should be denied
            try:
                resp = self.session.request(method=method, url=url, timeout=self.timeout)
                status_code = resp.status_code
                body = resp.text
                if status_code not in expected_denied:
                    error = f"No auth: expected {expected_denied}, got {status_code}"
            except RequestException as exc:
                error = f"Request failed: {exc}"
        else:
            # With auth token
            try:
                resp = self.session.request(
                    method=method,
                    url=url,
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=self.timeout,
                )
                status_code = resp.status_code
                body = resp.text
                if status_code not in expected_allowed:
                    # Check if it was denied instead
                    if status_code in expected_denied:
                        error = f"Auth'd {role} was denied ({status_code})"
                    else:
                        error = f"Unexpected status {status_code}"
            except RequestException as exc:
                error = f"Request failed: {exc}"

        elapsed_ms = round((__import__("time").monotonic() - start) * 1000.0, 2)
        passed = not error

        result = TestResult(
            name=f"RBAC: {role} {method} {endpoint}",
            passed=passed,
            status_code=status_code,
            expected_status=expected_allowed + expected_denied,
            endpoint=url,
            method=method,
            timing_ms=elapsed_ms,
            error=error,
            response_body_preview=body[:500] if body else "",
            details={
                "role": role,
                "authenticated": bool(token),
                "role_exists": role in self.credentials,
            },
        )

        self._log_result(result)
        return result
