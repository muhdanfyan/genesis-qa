"""Genesis QA - Edge Case Factory
=================================
Generates edge case test scenarios for API endpoints.

Edge cases covered:
  - Empty payloads (null, empty string, empty object, empty array)
  - Boundary values (very long strings, special characters, unicode)
  - Type mismatch (string sent as number, number as string, etc.)
  - Injection attempts (SQLi, XSS, template injection, path traversal)
  - Protocol manipulation (HTTP methods, content-types, headers)
  - State manipulation (race conditions, concurrent requests)
  - Schema validation (missing fields, extra fields, nested depth)

Typical usage:
    factory = EdgeCaseFactory()
    edge_cases = factory.create_edge_cases("/api/auth/login", "POST", {"email": "str", "password": "str"})
"""

from __future__ import annotations

import copy
import json
import logging
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class EdgeCaseCategory(Enum):
    """Category of edge case test."""

    EMPTY = "empty"
    BOUNDARY = "boundary"
    TYPE_MISMATCH = "type_mismatch"
    INJECTION = "injection"
    PROTOCOL = "protocol"
    STATE = "state"
    SCHEMA = "schema"
    AUTH = "auth"
    RATE_LIMIT = "rate_limit"


class EdgeCaseSeverity(Enum):
    """Severity if this edge case fails."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class EdgeCase:
    """A single edge case test scenario."""

    uid: str = ""
    name: str = ""
    category: EdgeCaseCategory = EdgeCaseCategory.EMPTY
    severity: EdgeCaseSeverity = EdgeCaseSeverity.MEDIUM
    endpoint: str = ""
    method: str = "GET"
    headers: dict[str, str] = field(default_factory=dict)
    body: Optional[dict[str, Any]] = None
    expected_status: list[int] = field(default_factory=lambda: [400, 422])
    description: str = ""
    tags: list[str] = field(default_factory=list)
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.uid:
            self.uid = uuid.uuid4().hex[:12]
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["category"] = self.category.value
        d["severity"] = self.severity.value
        return d


class EdgeCaseFactory:
    """Produces edge case test scenarios for any API endpoint.

    The factory introspects the endpoint's method and optional schema
    (parameter names/types) to generate relevant edge cases.
    """

    SQLI_PAYLOADS = [
        "' OR '1'='1",
        "' OR 1=1 --",
        "'; DROP TABLE users; --",
        "' UNION SELECT * FROM users --",
        "1; SELECT * FROM admin --",
        "' OR '1'='1' --",
        "admin' --",
        "1' ORDER BY 1--",
        "1' ORDER BY 100--",
    ]

    XSS_PAYLOADS = [
        "<script>alert(1)</script>",
        "<img src=x onerror=alert(1)>",
        "<svg onload=alert(1)>",
        "javascript:alert(1)",
        "\"><script>alert(1)</script>",
        "'; alert(1); //",
    ]

    PATH_TRAVERSAL_PAYLOADS = [
        "../../etc/passwd",
        "../../../etc/passwd",
        "..\\..\\windows\\win.ini",
        "%2e%2e%2f%2e%2e%2fetc/passwd",
        "....//....//etc/passwd",
    ]

    LONG_STRING = "A" * 10000
    UNICODE_STRING = "你好世界! 😊 ñoño 日本語 𝒮𝓅𝑒𝒸𝒾𝒶𝓁"

    @staticmethod
    def _make_edge_case(
        name: str,
        category: EdgeCaseCategory,
        severity: EdgeCaseSeverity,
        endpoint: str,
        method: str,
        headers: dict[str, str] | None = None,
        body: Any = None,
        expected_status: list[int] | None = None,
        description: str = "",
        tags: list[str] | None = None,
    ) -> EdgeCase:
        return EdgeCase(
            name=name,
            category=category,
            severity=severity,
            endpoint=endpoint,
            method=method,
            headers=headers or {},
            body=body,
            expected_status=expected_status or [400, 422],
            description=description,
            tags=tags or [],
        )

    def create_edge_cases(
        self,
        endpoint: str,
        method: str = "GET",
        schema: Optional[dict[str, str]] = None,
        has_auth: bool = False,
    ) -> list[EdgeCase]:
        """Generate edge cases for the given endpoint.

        Args:
            endpoint: API path (e.g. /api/auth/login).
            method: HTTP method (GET, POST, PUT, PATCH, DELETE).
            schema: Dict mapping field name to type hint ("str", "int", "email", etc.).
            has_auth: Whether the endpoint requires authentication.

        Returns:
            List of EdgeCase instances.
        """
        edge_cases: list[EdgeCase] = []
        schema = schema or {}
        fields = list(schema.keys())

        # --- EMPTY CATEGORY ---
        if method in ("POST", "PUT", "PATCH"):
            edge_cases.append(self._make_edge_case(
                f"Empty body to {method} {endpoint}",
                EdgeCaseCategory.EMPTY, EdgeCaseSeverity.MEDIUM,
                endpoint, method,
                body={},
                expected_status=[400, 422],
                description="Send empty JSON body to a write endpoint.",
                tags=["empty", "validation"],
            ))
            edge_cases.append(self._make_edge_case(
                f"Null body to {method} {endpoint}",
                EdgeCaseCategory.EMPTY, EdgeCaseSeverity.MEDIUM,
                endpoint, method,
                body=None,
                expected_status=[400, 422, 415],
                description="Send null/raw body with wrong Content-Type.",
                tags=["empty", "malformed"],
            ))
            edge_cases.append(self._make_edge_case(
                f"All fields null to {endpoint}",
                EdgeCaseCategory.EMPTY, EdgeCaseSeverity.HIGH,
                endpoint, method,
                body={f: None for f in fields} if fields else {"email": None, "password": None},
                expected_status=[400, 422],
                description="Every field in the payload is set to null.",
                tags=["null", "validation"],
            ))

        # --- BOUNDARY CATEGORY ---
        if fields:
            for field_name in fields[:2]:  # Top 2 fields only to avoid explosion
                edge_cases.append(self._make_edge_case(
                    f"Very long string for '{field_name}' on {endpoint}",
                    EdgeCaseCategory.BOUNDARY, EdgeCaseSeverity.MEDIUM,
                    endpoint, method,
                    body={field_name: self.LONG_STRING},
                    expected_status=[400, 413, 422],
                    description=f"Send 10k char string for field '{field_name}'.",
                    tags=["boundary", "overflow"],
                ))
                edge_cases.append(self._make_edge_case(
                    f"Unicode string for '{field_name}' on {endpoint}",
                    EdgeCaseCategory.BOUNDARY, EdgeCaseSeverity.LOW,
                    endpoint, method,
                    body={field_name: self.UNICODE_STRING},
                    expected_status=[200, 201, 400, 422],
                    description=f"Send multi-language/emoji string for '{field_name}'.",
                    tags=["unicode", "i18n"],
                ))

        # --- INJECTION CATEGORY ---
        if fields:
            for field_name in fields[:1]:
                edge_cases.append(self._make_edge_case(
                    f"SQLi on '{field_name}' of {endpoint}",
                    EdgeCaseCategory.INJECTION, EdgeCaseSeverity.CRITICAL,
                    endpoint, method,
                    body={field_name: self.SQLI_PAYLOADS[0]},
                    expected_status=[400, 422, 403],
                    description=f"Basic SQL injection on field '{field_name}'.",
                    tags=["sqli", "injection", "security"],
                ))
                edge_cases.append(self._make_edge_case(
                    f"XSS on '{field_name}' of {endpoint}",
                    EdgeCaseCategory.INJECTION, EdgeCaseSeverity.CRITICAL,
                    endpoint, method,
                    body={field_name: self.XSS_PAYLOADS[0]},
                    expected_status=[400, 422],
                    description=f"Basic XSS payload on field '{field_name}'.",
                    tags=["xss", "injection", "security"],
                ))
        edge_cases.append(self._make_edge_case(
            f"Path traversal on {endpoint}",
            EdgeCaseCategory.INJECTION, EdgeCaseSeverity.HIGH,
            endpoint, "GET",
            headers={"X-Original-URL": self.PATH_TRAVERSAL_PAYLOADS[0]},
            expected_status=[400, 403, 404],
            description="Attempt path traversal via header.",
            tags=["path-traversal", "security"],
        ))

        # --- TYPE MISMATCH ---
        if schema:
            for fname, ftype in list(schema.items())[:2]:
                if ftype == "int":
                    edge_cases.append(self._make_edge_case(
                        f"String instead of int for '{fname}' on {endpoint}",
                        EdgeCaseCategory.TYPE_MISMATCH, EdgeCaseSeverity.MEDIUM,
                        endpoint, method,
                        body={fname: "not-a-number"},
                        expected_status=[400, 422],
                        description=f"Send string where int expected for '{fname}'.",
                        tags=["type", "validation"],
                    ))
                elif ftype == "email":
                    edge_cases.append(self._make_edge_case(
                        f"Bad email format for '{fname}' on {endpoint}",
                        EdgeCaseCategory.TYPE_MISMATCH, EdgeCaseSeverity.MEDIUM,
                        endpoint, method,
                        body={fname: "not-an-email"},
                        expected_status=[400, 422],
                        description=f"Send non-email string for email field '{fname}'.",
                        tags=["email", "validation"],
                    ))

        # --- PROTOCOL MANIPULATION ---
        if method != "GET":
            edge_cases.append(self._make_edge_case(
                f"GET instead of {method} on {endpoint}",
                EdgeCaseCategory.PROTOCOL, EdgeCaseSeverity.LOW,
                endpoint, "GET",
                expected_status=[405],
                description=f"Use GET method on endpoint that expects {method}.",
                tags=["method", "protocol"],
            ))
        if method != "OPTIONS":
            edge_cases.append(self._make_edge_case(
                f"OPTIONS preflight on {endpoint}",
                EdgeCaseCategory.PROTOCOL, EdgeCaseSeverity.LOW,
                endpoint, "OPTIONS",
                expected_status=[204, 200],
                description="Check CORS preflight response.",
                tags=["cors", "options", "protocol"],
            ))
        if method not in ("DELETE", "PATCH", "PUT"):
            edge_cases.append(self._make_edge_case(
                f"DELETE method on {endpoint} (should be blocked)",
                EdgeCaseCategory.PROTOCOL, EdgeCaseSeverity.MEDIUM,
                endpoint, "DELETE",
                expected_status=[405, 403, 401],
                description="DELETE method should be rejected if not allowed.",
                tags=["method", "safety"],
            ))

        # --- AUTH EDGE CASES ---
        if has_auth:
            edge_cases.append(self._make_edge_case(
                f"No auth header on {endpoint}",
                EdgeCaseCategory.AUTH, EdgeCaseSeverity.CRITICAL,
                endpoint, method,
                headers={},
                expected_status=[401, 403],
                description="Request without any authentication.",
                tags=["auth", "unauthorized"],
            ))
            edge_cases.append(self._make_edge_case(
                f"Invalid token on {endpoint}",
                EdgeCaseCategory.AUTH, EdgeCaseSeverity.CRITICAL,
                endpoint, method,
                headers={"Authorization": "Bearer invalid.token.here"},
                expected_status=[401, 403],
                description="Request with a malformed/expired token.",
                tags=["auth", "token"],
            ))
            edge_cases.append(self._make_edge_case(
                f"Empty auth header on {endpoint}",
                EdgeCaseCategory.AUTH, EdgeCaseSeverity.HIGH,
                endpoint, method,
                headers={"Authorization": ""},
                expected_status=[401, 403],
                description="Authorization header present but empty.",
                tags=["auth", "header"],
            ))

        # --- SCHEMA MANIPULATION ---
        if fields:
            edge_cases.append(self._make_edge_case(
                f"Missing all fields on {endpoint}",
                EdgeCaseCategory.SCHEMA, EdgeCaseSeverity.HIGH,
                endpoint, method,
                body={"unexpected_field": "value"},
                expected_status=[400, 422],
                description="Send completely unrelated fields.",
                tags=["schema", "validation"],
            ))
            # Missing one required field
            if len(fields) >= 2:
                partial = {fields[0]: "test"}
                edge_cases.append(self._make_edge_case(
                    f"Partial fields (missing '{fields[1]}') on {endpoint}",
                    EdgeCaseCategory.SCHEMA, EdgeCaseSeverity.HIGH,
                    endpoint, method,
                    body=partial,
                    expected_status=[400, 422],
                    description=f"Send payload without required field '{fields[1]}'.",
                    tags=["schema", "missing-field"],
                ))

        logger.info(
            "Generated %d edge cases for %s %s",
            len(edge_cases), method, endpoint,
        )
        return edge_cases

    def export_to_json(
        self,
        edge_cases: list[EdgeCase],
        path: str,
        indent: int = 2,
    ) -> str:
        """Export edge cases to a JSON file."""
        import json as j
        data = [ec.to_dict() for ec in edge_cases]
        with open(path, "w") as f:
            j.dump(data, f, indent=indent, default=str)
        logger.info("Exported %d edge cases to %s", len(edge_cases), path)
        return path
