"""
Genesis QA — OpenAPI / Swagger Parser
======================================
Parses OpenAPI 3.0 and Swagger 2.0 specification files (JSON or YAML)
and produces ready-to-execute test scenarios compatible with the
genesis-qa pipeline.

Typical usage::

    parser = OpenApiParser()
    spec = parser.parse_file("swagger.json")
    scenarios = parser.to_scenarios(spec)
    config_yaml = parser.to_config_yaml(spec)
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants — common HTTP status categories
# ---------------------------------------------------------------------------

STATUS_CATEGORIES: dict[str, list[int]] = {
    "success": [200, 201, 202, 204],
    "redirect": [301, 302, 303, 307, 308],
    "client_error": [400, 401, 403, 404, 405, 409, 422, 429],
    "server_error": [500, 502, 503],
}

# ---------------------------------------------------------------------------
# Dummy value generators for common parameter types
# ---------------------------------------------------------------------------

DUMMY_VALUES: dict[str, str] = {
    "string": "test_string",
    "integer": "1",
    "number": "1.5",
    "boolean": "true",
    "array": "[]",
    "object": "{}",
    "email": "user@example.com",
    "uuid": "550e8400-e29b-41d4-a716-446655440000",
    "uri": "https://example.com/resource",
    "date": "2025-01-01",
    "date-time": "2025-01-01T00:00:00Z",
    "slug": "test-slug",
    "id": "123",
}

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ApiEndpoint:
    """A single API endpoint extracted from the spec.

    Attributes:
        path:        URL path, e.g. ``/api/users/{id}``.
        method:      HTTP method (``GET``, ``POST``, etc.).
        summary:     Short description from the spec.
        description: Longer description.
        operation_id: Unique operation ID from the spec.
        parameters:  List of parameter dicts.
        request_body: Request body schema summary (if any).
        responses:   Dict mapping status code strings to response summaries.
        tags:        OpenAPI tags attached to the operation.
        security:    Security requirements for this operation.
    """

    path: str = ""
    method: str = "GET"
    summary: str = ""
    description: str = ""
    operation_id: str = ""
    parameters: list[dict[str, Any]] = field(default_factory=list)
    request_body: Optional[dict[str, Any]] = None
    responses: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    security: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ApiSpec:
    """Top-level parsed API specification.

    Attributes:
        openapi_version:  ``"3.0"``, ``"2.0"``, or ``None``.
        title:            API title.
        version:          API version string.
        description:      API description.
        servers:          List of server URLs.
        base_path:        Base path (Swagger 2.0 ``basePath``).
        endpoints:        All parsed ``ApiEndpoint`` instances.
        security_definitions: Dict of auth scheme definitions.
        security:         Global security requirements.
    """

    openapi_version: Optional[str] = None
    title: str = ""
    version: str = ""
    description: str = ""
    servers: list[str] = field(default_factory=list)
    base_path: str = ""
    endpoints: list[ApiEndpoint] = field(default_factory=list)
    security_definitions: dict[str, Any] = field(default_factory=dict)
    security: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


class OpenApiParser:
    """Parse OpenAPI / Swagger specifications and generate test artefacts.

    Supports both **OpenAPI 3.0** and **Swagger 2.0** formats. Input can be
    a local file path or a URL.  Output is a structured ``ApiSpec`` object,
    a list of ``Scenario`` objects ready for the test pipeline, or a full
    configuration YAML string.

    Examples::

        parser = OpenApiParser()
        spec = parser.parse_file("specs/my_api.yaml")
        scenarios = parser.to_scenarios(spec)
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse_file(self, path: str | Path) -> ApiSpec:
        """Read and parse an OpenAPI spec from a local file.

        Supports ``.json``, ``.yaml``, and ``.yml`` extensions.  Auto-detects
        OpenAPI 3.0 vs Swagger 2.0 from the root keys.

        Args:
            path: Path to the spec file.

        Returns:
            An ``ApiSpec`` instance.

        Raises:
            FileNotFoundError:  If the file does not exist.
            ValueError:         If the file extension or content is
                                unsupported.
        """
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"OpenAPI spec not found: {p.resolve()}")

        raw = p.read_text(encoding="utf-8")
        ext = p.suffix.lower()

        if ext == ".json":
            data: dict[str, Any] = json.loads(raw)
        elif ext in (".yaml", ".yml"):
            try:
                import yaml
            except ImportError:
                raise RuntimeError(
                    "PyYAML is required to parse YAML files. "
                    "Install it with: pip install pyyaml"
                )
            data = yaml.safe_load(raw)
            if not isinstance(data, dict):
                raise ValueError("YAML content is not a dict — invalid OpenAPI spec")
        else:
            raise ValueError(
                f"Unsupported file extension '{ext}'. "
                f"Use .json, .yaml, or .yml"
            )

        return self._parse_dict(data)

    def parse_url(self, url: str) -> ApiSpec:
        """Fetch and parse an OpenAPI spec from a URL.

        Uses ``urllib.request`` (stdlib, no extra dependencies).

        Args:
            url: URL pointing to a JSON or YAML OpenAPI spec.

        Returns:
            An ``ApiSpec`` instance.

        Raises:
            RuntimeError: If the URL cannot be fetched or content is
                          invalid.
        """
        import urllib.error
        import urllib.request

        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json, text/yaml"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                content_type = resp.headers.get("Content-Type", "")
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"HTTP {exc.code} fetching {url}: {exc.reason}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"URL error for {url}: {exc.reason}") from exc
        except Exception as exc:
            raise RuntimeError(f"Failed to fetch {url}: {exc}") from exc

        # Try JSON first, fall back to YAML
        data: dict[str, Any]
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            try:
                import yaml
            except ImportError:
                raise RuntimeError(
                    "PyYAML is required to parse YAML responses from URLs. "
                    "Install it with: pip install pyyaml"
                )
            data = yaml.safe_load(raw)
            if not isinstance(data, dict):
                raise ValueError("URL returned non-dict content — invalid OpenAPI spec")

        logger.info("Fetched OpenAPI spec from %s", url)
        return self._parse_dict(data)

    def to_scenarios(self, api_spec: ApiSpec) -> list[dict[str, Any]]:
        """Convert a parsed ``ApiSpec`` into a list of scenario dicts.

        Each scenario corresponds to one endpoint + method + expected status
        code.  The output dicts are compatible with the ``ScenarioConfig``
        dataclass used by the test engines.

        Args:
            api_spec: A parsed ``ApiSpec`` instance.

        Returns:
            A list of scenario dicts, each with keys:
            ``uid``, ``name``, ``method``, ``endpoint``, ``headers``,
            ``body``, ``expected_status``, ``tags``, ``metadata``.
        """
        base_url = self._pick_base_url(api_spec)
        scenarios: list[dict[str, Any]] = []

        for ep in api_spec.endpoints:
            # Resolve path parameters to concrete values
            resolved_path = self._resolve_path_params(ep.path, ep.parameters)
            full_url = f"{base_url}{api_spec.base_path}{resolved_path}".rstrip("/")

            # Build query string from query params
            query_string = self._build_query_string(ep.parameters)
            endpoint_url = f"{full_url}{query_string}"

            # Build headers from security / auth requirements
            headers = self._build_headers(ep, api_spec)

            # Build request body example from schema
            body = self._build_request_body(ep.request_body)

            for status_code_str, _resp_info in ep.responses.items():
                expected = self._parse_status_code(status_code_str)
                if expected is None:
                    continue

                scenario = {
                    "uid": uuid.uuid4().hex[:12],
                    "name": (
                        ep.summary
                        or ep.operation_id
                        or f"{ep.method.upper()} {ep.path}"
                    ),
                    "method": ep.method.upper(),
                    "endpoint": endpoint_url,
                    "headers": headers,
                    "body": body,
                    "expected_status": expected,
                    "tags": list(ep.tags),
                    "metadata": {
                        "source": "openapi_parser",
                        "path": ep.path,
                        "operation_id": ep.operation_id,
                        "status_code": status_code_str,
                        "parameters": ep.parameters,
                        "security": ep.security,
                    },
                }
                scenarios.append(scenario)

        logger.info(
            "Generated %d scenarios from %d endpoints",
            len(scenarios),
            len(api_spec.endpoints),
        )
        return scenarios

    def to_config_yaml(self, api_spec: ApiSpec) -> str:
        """Generate a complete configuration YAML from the parsed spec.

        The output YAML is compatible with ``run.py``'s ``load_config()``
        format, including system info, endpoints, auth, security, and CORS
        sections inferred from the spec.

        Args:
            api_spec: A parsed ``ApiSpec`` instance.

        Returns:
            A YAML string that can be written directly to
            ``config/systems/<name>.yaml``.
        """
        try:
            import yaml
        except ImportError:
            raise RuntimeError(
                "PyYAML is required to generate YAML config. "
                "Install it with: pip install pyyaml"
            )

        base_url = self._pick_base_url(api_spec)
        system_name = api_spec.title.replace(" ", "_").lower() or "api"

        # Build endpoints section
        endpoints: dict[str, Any] = {}
        for ep in api_spec.endpoints:
            resolved_path = self._resolve_path_params(ep.path, ep.parameters)
            query_string = self._build_query_string(ep.parameters)
            endpoint_url = f"{resolved_path}{query_string}"

            expected_statuses: list[int] = []
            for sc_str in ep.responses:
                parsed = self._parse_status_code(sc_str)
                if parsed:
                    expected_statuses.extend(parsed)

            # Use tags as category keys if available
            category_key = ep.tags[0] if ep.tags else "default"
            sub_key = ep.operation_id or f"{ep.method.lower()}_{ep.path.replace('/', '_').strip('_')}"

            if category_key not in endpoints:
                endpoints[category_key] = {}

            endpoints[category_key][sub_key] = {
                "path": endpoint_url,
                "method": ep.method.upper(),
                "expected_status": sorted(set(expected_statuses)) or [200],
            }

        # Detect auth type
        auth_config = self._build_auth_config(api_spec)
        security_config = self._build_security_config(api_spec)
        cors_config = self._build_cors_config(api_spec)

        config: dict[str, Any] = {
            "system": {
                "name": system_name,
                "base_url": base_url,
                "type": "api",
                "version": api_spec.version,
                "description": api_spec.description,
            },
            "endpoints": endpoints,
        }

        if auth_config:
            config["auth"] = auth_config
        if security_config:
            config["security"] = security_config
        if cors_config:
            config["cors"] = cors_config

        return yaml.dump(config, default_flow_style=False, sort_keys=False, allow_unicode=True)

    # ------------------------------------------------------------------
    # Internal — parsing
    # ------------------------------------------------------------------

    def _parse_dict(self, data: dict[str, Any]) -> ApiSpec:
        """Detect version and dispatch to the appropriate parser."""
        # Auto-detect spec version
        if "openapi" in data:
            version = str(data["openapi"])
            logger.info("Detected OpenAPI %s spec", version)
            return self._parse_openapi_v3(data, version)
        elif "swagger" in data:
            version = str(data["swagger"])
            logger.info("Detected Swagger %s spec", version)
            return self._parse_swagger_v2(data, version)
        else:
            raise ValueError(
                "Unrecognised spec format — missing 'openapi' or 'swagger' key"
            )

    def _parse_openapi_v3(self, data: dict[str, Any], version: str) -> ApiSpec:
        """Parse an OpenAPI 3.x spec dict."""
        info = data.get("info", {})

        servers_urls: list[str] = []
        for s in data.get("servers", []):
            url = s.get("url", "")
            if url:
                servers_urls.append(url)

        # Security definitions (components/securitySchemes)
        components = data.get("components", {})
        security_defs: dict[str, Any] = components.get("securitySchemes", {})

        # Global security
        global_security: list[dict[str, Any]] = data.get("security", [])

        spec = ApiSpec(
            openapi_version=version,
            title=info.get("title", ""),
            version=info.get("version", ""),
            description=info.get("description", ""),
            servers=servers_urls,
            base_path="",
            security_definitions=security_defs,
            security=global_security,
        )

        # Parse paths
        paths = data.get("paths", {})
        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue

            # Path-level parameters
            path_params: list[dict[str, Any]] = [
                self._normalize_param(p, "3.0") for p in path_item.get("parameters", [])
            ]

            for method in ("get", "post", "put", "delete", "patch", "head", "options", "trace"):
                operation = path_item.get(method)
                if not isinstance(operation, dict):
                    continue

                endpoint = self._parse_operation_v3(
                    path, method, operation, path_params, security_defs
                )
                spec.endpoints.append(endpoint)

        return spec

    def _parse_operation_v3(
        self,
        path: str,
        method: str,
        operation: dict[str, Any],
        path_params: list[dict[str, Any]],
        security_defs: dict[str, Any],
    ) -> ApiEndpoint:
        """Parse a single OpenAPI 3.x operation into an ApiEndpoint."""
        # Operation-level parameters override path-level
        op_params_raw: list[dict[str, Any]] = operation.get("parameters", [])
        op_params = [self._normalize_param(p, "3.0") for p in op_params_raw]

        # Merge: operation params override path params
        merged_params = list(path_params)
        op_param_names = {p.get("name", "") for p in op_params}
        merged_params = [p for p in merged_params if p.get("name", "") not in op_param_names]
        merged_params.extend(op_params)

        # Request body
        request_body: Optional[dict[str, Any]] = None
        rb = operation.get("requestBody")
        if rb:
            content = rb.get("content", {})
            # Prefer application/json
            json_schema = None
            for ctype, ctype_info in content.items():
                if "application/json" in ctype or "*/*" in ctype:
                    json_schema = ctype_info.get("schema")
                    break
            if json_schema is None:
                # Fallback: first content type
                for ctype_info in content.values():
                    json_schema = ctype_info.get("schema")
                    break

            request_body = {
                "required": rb.get("required", False),
                "description": rb.get("description", ""),
                "schema": json_schema or {},
            }

        # Responses
        responses: dict[str, Any] = {}
        for sc_str, resp_obj in operation.get("responses", {}).items():
            if isinstance(resp_obj, dict):
                resp_content = resp_obj.get("content", {})
                resp_schema = None
                for ctype_info in resp_content.values():
                    resp_schema = ctype_info.get("schema")
                    break
                responses[sc_str] = {
                    "description": resp_obj.get("description", ""),
                    "schema": resp_schema,
                }
            else:
                responses[sc_str] = {"description": str(resp_obj), "schema": None}

        # Security
        op_security: list[dict[str, Any]] = operation.get("security", [])

        return ApiEndpoint(
            path=path,
            method=method.upper(),
            summary=operation.get("summary", ""),
            description=operation.get("description", ""),
            operation_id=operation.get("operationId", ""),
            parameters=merged_params,
            request_body=request_body,
            responses=responses,
            tags=operation.get("tags", []),
            security=op_security,
        )

    def _parse_swagger_v2(self, data: dict[str, Any], version: str) -> ApiSpec:
        """Parse a Swagger 2.0 spec dict."""
        info = data.get("info", {})
        base_path = data.get("basePath", "")

        # Schemes + host + basePath = base URL
        schemes = data.get("schemes", ["https"])
        host = data.get("host", "")
        servers_urls: list[str] = []
        for scheme in schemes:
            if host:
                servers_urls.append(f"{scheme}://{host}")

        # Security definitions
        security_defs: dict[str, Any] = data.get("securityDefinitions", {})

        # Global security
        global_security: list[dict[str, Any]] = data.get("security", [])

        spec = ApiSpec(
            openapi_version=version,
            title=info.get("title", ""),
            version=info.get("version", ""),
            description=info.get("description", ""),
            servers=servers_urls,
            base_path=base_path,
            security_definitions=security_defs,
            security=global_security,
        )

        # Parse paths
        paths = data.get("paths", {})
        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue

            # Path-level parameters
            path_params: list[dict[str, Any]] = [
                self._normalize_param(p, "2.0") for p in path_item.get("parameters", [])
            ]

            for method in ("get", "post", "put", "delete", "patch", "head", "options"):
                operation = path_item.get(method)
                if not isinstance(operation, dict):
                    continue

                endpoint = self._parse_operation_v2(
                    path, method, operation, path_params
                )
                spec.endpoints.append(endpoint)

        return spec

    def _parse_operation_v2(
        self,
        path: str,
        method: str,
        operation: dict[str, Any],
        path_params: list[dict[str, Any]],
    ) -> ApiEndpoint:
        """Parse a single Swagger 2.0 operation into an ApiEndpoint."""
        op_params_raw: list[dict[str, Any]] = operation.get("parameters", [])
        op_params = [self._normalize_param(p, "2.0") for p in op_params_raw]

        # Merge: operation params override path params
        merged_params = list(path_params)
        op_param_names = {p.get("name", "") for p in op_params}
        merged_params = [p for p in merged_params if p.get("name", "") not in op_param_names]
        merged_params.extend(op_params)

        # Request body — Swagger 2.0 uses `parameters` with `in: body`
        request_body: Optional[dict[str, Any]] = None
        for p in merged_params[:]:
            if p.get("in") == "body":
                request_body = {
                    "required": p.get("required", False),
                    "description": p.get("description", ""),
                    "schema": p.get("schema", {}),
                }
                merged_params.remove(p)
                break

        # Responses
        responses: dict[str, Any] = {}
        for sc_str, resp_obj in operation.get("responses", {}).items():
            if isinstance(resp_obj, dict):
                responses[sc_str] = {
                    "description": resp_obj.get("description", ""),
                    "schema": resp_obj.get("schema"),
                }
            else:
                responses[sc_str] = {"description": str(resp_obj), "schema": None}

        return ApiEndpoint(
            path=path,
            method=method.upper(),
            summary=operation.get("summary", ""),
            description=operation.get("description", ""),
            operation_id=operation.get("operationId", ""),
            parameters=merged_params,
            request_body=request_body,
            responses=responses,
            tags=operation.get("tags", []),
            security=[],
        )

    # ------------------------------------------------------------------
    # Internal — parameter normalisation
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_param(param: dict[str, Any], spec_version: str) -> dict[str, Any]:
        """Normalise a parameter dict to a consistent shape.

        Both OpenAPI 3.x and Swagger 2.0 parameters are mapped to the
        same structure with keys: ``name``, ``in``, ``required``,
        ``description``, ``type``, ``schema``, ``example``.
        """
        normalized: dict[str, Any] = {
            "name": param.get("name", ""),
            "in": param.get("in", "query"),
            "required": param.get("required", False),
            "description": param.get("description", ""),
            "type": "string",
            "schema": None,
            "example": None,
        }

        if spec_version.startswith("3"):
            schema = param.get("schema", {}) or {}
            normalized["type"] = schema.get("type", "string")
            normalized["schema"] = schema
            normalized["example"] = param.get("example") or schema.get("example")
            # For ``in: header``, check for ``in: header``
        else:  # Swagger 2.0
            normalized["type"] = param.get("type", "string")
            normalized["schema"] = param.get("items")
            normalized["example"] = param.get("x-example")

        # Ensure boolean required
        if isinstance(normalized["required"], bool):
            pass
        elif isinstance(normalized["required"], str):
            normalized["required"] = normalized["required"].lower() == "true"
        else:
            normalized["required"] = False

        return normalized

    # ------------------------------------------------------------------
    # Internal — helpers for scenario generation
    # ------------------------------------------------------------------

    @staticmethod
    def _pick_base_url(spec: ApiSpec) -> str:
        """Return the first available server URL, or a placeholder."""
        if spec.servers:
            url = spec.servers[0]
            # Remove trailing variables like {basePath}
            url = re.sub(r"\{[^}]+\}", "", url).rstrip("/")
            return url
        return "https://api.example.com"

    @staticmethod
    def _resolve_path_params(
        path: str, parameters: list[dict[str, Any]]
    ) -> str:
        """Replace path parameters (``{id}``, ``{slug}``) with dummy values."""
        resolved = path
        for p in parameters:
            if p.get("in") != "path":
                continue
            name = p.get("name", "")
            placeholder = "{" + name + "}"
            if placeholder not in resolved:
                continue

            # Pick a dummy value based on the parameter name or type
            ptype = p.get("type", "string")
            pname_lower = name.lower()

            if "email" in pname_lower:
                dummy = DUMMY_VALUES["email"]
            elif "uuid" in pname_lower or "uid" in pname_lower or "guid" in pname_lower:
                dummy = DUMMY_VALUES["uuid"]
            elif "slug" in pname_lower:
                dummy = DUMMY_VALUES["slug"]
            elif "id" in pname_lower or "pk" in pname_lower:
                dummy = DUMMY_VALUES["id"]
            elif "date" in pname_lower:
                dummy = DUMMY_VALUES["date"]
            elif "uri" in pname_lower or "url" in pname_lower:
                dummy = DUMMY_VALUES["uri"]
            else:
                dummy = DUMMY_VALUES.get(ptype, "test_value")

            resolved = resolved.replace(placeholder, dummy, 1)

        # Replace any remaining unhandled path params with a generic value
        resolved = re.sub(r"\{[^}]+\}", "test_value", resolved)
        return resolved

    @staticmethod
    def _build_query_string(parameters: list[dict[str, Any]]) -> str:
        """Build a query string from query parameters.

        Only includes **required** parameters. Optional parameters are
        omitted by default to keep scenarios clean.
        """
        query_parts: list[str] = []
        for p in parameters:
            if p.get("in") != "query":
                continue
            if not p.get("required", False):
                continue
            name = p.get("name", "")
            ptype = p.get("type", "string")
            pname_lower = name.lower()

            if "email" in pname_lower:
                val = DUMMY_VALUES["email"]
            elif "uuid" in pname_lower or "uid" in pname_lower:
                val = DUMMY_VALUES["uuid"]
            elif "date" in pname_lower:
                val = DUMMY_VALUES["date"]
            elif "page" in pname_lower:
                val = "1"
            elif "limit" in pname_lower or "per_page" in pname_lower:
                val = "20"
            else:
                val = DUMMY_VALUES.get(ptype, "test_value")

            query_parts.append(f"{name}={val}")

        if query_parts:
            return "?" + "&".join(query_parts)
        return ""

    @staticmethod
    def _build_headers(
        endpoint: ApiEndpoint, spec: ApiSpec
    ) -> dict[str, str]:
        """Build request headers from security requirements and header params.

        Detects API key, Bearer token, and Basic auth patterns from the
        security definitions and the endpoint's security requirements.
        """
        headers: dict[str, str] = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        # Collect security schemes this endpoint needs
        needed_schemes: list[dict[str, Any]] = endpoint.security or spec.security

        for req in needed_schemes:
            if not isinstance(req, dict):
                continue
            for scheme_name in req:
                sec_def = spec.security_definitions.get(scheme_name, {})
                sec_type = sec_def.get("type", "").lower()
                sec_in = sec_def.get("in", "header").lower()
                sec_name = sec_def.get("name", "Authorization")

                if sec_type == "apiKey":
                    if sec_in == "header":
                        headers[sec_name] = f"test_{scheme_name}_key"
                    elif sec_in == "query":
                        pass  # handled in query string if needed
                elif sec_type in ("http",):
                    scheme = sec_def.get("scheme", "bearer").lower()
                    if scheme == "bearer":
                        headers["Authorization"] = "Bearer test_token_123"
                    elif scheme == "basic":
                        headers["Authorization"] = "Basic dGVzdDp0ZXN0"
                elif sec_type == "oauth2":
                    headers["Authorization"] = "Bearer test_oauth_token"
                elif sec_type == "openIdConnect":
                    headers["Authorization"] = "Bearer test_oidc_token"

        # Also add header parameters from the endpoint
        for p in endpoint.parameters:
            if p.get("in") == "header":
                name = p.get("name", "")
                val = DUMMY_VALUES.get(p.get("type", "string"), "test_value")
                if name.lower() not in (h.lower() for h in headers):
                    headers[name] = val

        return headers

    @staticmethod
    def _build_request_body(request_body: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
        """Generate an example request body from a schema.

        Produces a simple dict with example values based on the schema
        properties.
        """
        if request_body is None:
            return None

        schema = request_body.get("schema", {})
        if not schema:
            return None

        return OpenApiParser._schema_to_example(schema)

    @staticmethod
    def _schema_to_example(schema: dict[str, Any]) -> Optional[Any]:
        """Convert a JSON schema to an example value.

        Handles ``type``, ``properties``, ``items``, ``enum``,
        ``example``, and ``default`` fields.
        """
        # Direct example
        if "example" in schema:
            return schema["example"]

        # Enum — pick first value
        enum_vals = schema.get("enum")
        if enum_vals:
            return enum_vals[0]

        # Default
        if "default" in schema:
            return schema["default"]

        schema_type = schema.get("type", "object")

        if schema_type == "object":
            props = schema.get("properties", {})
            required_set = set(schema.get("required", []))
            result: dict[str, Any] = {}
            for prop_name, prop_schema in props.items():
                if isinstance(prop_schema, dict):
                    result[prop_name] = OpenApiParser._schema_to_example(prop_schema)
                else:
                    result[prop_name] = "test_value"

            # Also include required properties that might not be in props
            for req_name in required_set:
                if req_name not in result:
                    result[req_name] = "test_value"

            return result if result else {"example_key": "example_value"}

        elif schema_type == "array":
            items_schema = schema.get("items", {})
            if isinstance(items_schema, dict):
                item_example = OpenApiParser._schema_to_example(items_schema)
                return [item_example] if item_example else []
            return []

        elif schema_type == "string":
            fmt = schema.get("format", "")
            return DUMMY_VALUES.get(fmt, "test_string")

        elif schema_type == "integer":
            return 1
        elif schema_type == "number":
            return 1.5
        elif schema_type == "boolean":
            return True
        else:
            return None

    @staticmethod
    def _parse_status_code(status_code_str: str) -> Optional[list[int]]:
        """Parse a status code string to a list of ints.

        Handles concrete codes (``"200"``), wildcards (``"2XX"``),
        and named ranges (``"default"``).
        """
        sc = status_code_str.strip()

        if sc == "default":
            return [200]  # sensible default

        # Wildcard: "2XX" -> [200, 201, 202, ...]
        wildcard_match = re.match(r"^(\d)XX$", sc, re.IGNORECASE)
        if wildcard_match:
            digit = int(wildcard_match.group(1))
            return [digit * 100 + i for i in range(0, 100)]

        # Named category
        if sc.lower() in STATUS_CATEGORIES:
            return STATUS_CATEGORIES[sc.lower()]

        # Concrete code
        try:
            code = int(sc)
            return [code]
        except ValueError:
            return None

    # ------------------------------------------------------------------
    # Internal — config generation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_auth_config(spec: ApiSpec) -> dict[str, Any]:
        """Build an ``auth`` config section from security definitions."""
        if not spec.security_definitions:
            return {}

        auth_config: dict[str, Any] = {
            "login_endpoint": "/auth/login",
            "credentials": {},
        }

        for scheme_name, sec_def in spec.security_definitions.items():
            if isinstance(sec_def, dict):
                sec_type = sec_def.get("type", "").lower()
                if sec_type == "http":
                    scheme = sec_def.get("scheme", "bearer").lower()
                    if scheme == "basic":
                        auth_config["credentials"][scheme_name] = {
                            "username": f"test_{scheme_name}_user",
                            "password": "${TEST_PASSWORD}",
                        }
                elif sec_type == "oauth2":
                    auth_config["credentials"][scheme_name] = {
                        "username": f"test_{scheme_name}_user",
                        "password": "${TEST_PASSWORD}",
                    }
                elif sec_type == "apiKey":
                    # apiKey is typically not for login, but we note it
                    pass

        return auth_config

    @staticmethod
    def _build_security_config(spec: ApiSpec) -> dict[str, Any]:
        """Build a ``security`` config section."""
        return {
            "test_headers": True,
            "test_disclosure": True,
            "test_redirects": True,
            "test_cors": True,
            "test_directory_listing": False,
        }

    @staticmethod
    def _build_cors_config(spec: ApiSpec) -> dict[str, Any]:
        """Build a ``cors`` config section."""
        return {
            "allowed_origins": ["*"],
            "allowed_methods": ["GET", "POST", "PUT", "DELETE", "PATCH"],
            "allowed_headers": ["Content-Type", "Authorization"],
        }
