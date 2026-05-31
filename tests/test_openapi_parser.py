"""Tests for OpenApiParser."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from generate.openapi_parser import OpenApiParser, ApiSpec


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

OPENAPI_30_SPEC = {
    "openapi": "3.0.3",
    "info": {
        "title": "Test API",
        "version": "1.0.0",
        "description": "A test OpenAPI 3.0 spec",
    },
    "servers": [{"url": "https://api.test.com"}],
    "paths": {
        "/items": {
            "get": {
                "summary": "List items",
                "operationId": "listItems",
                "tags": ["items"],
                "responses": {
                    "200": {"description": "OK"},
                },
            },
            "post": {
                "summary": "Create item",
                "operationId": "createItem",
                "tags": ["items"],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["name"],
                                "properties": {
                                    "name": {"type": "string"},
                                },
                            }
                        }
                    },
                },
                "responses": {
                    "201": {"description": "Created"},
                    "400": {"description": "Bad request"},
                },
            },
        },
        "/items/{itemId}": {
            "get": {
                "summary": "Get item by ID",
                "operationId": "getItem",
                "tags": ["items"],
                "parameters": [
                    {
                        "name": "itemId",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer"},
                    }
                ],
                "responses": {
                    "200": {"description": "OK"},
                    "404": {"description": "Not found"},
                },
            }
        },
    },
}

SWAGGER_20_SPEC = {
    "swagger": "2.0",
    "info": {"title": "Swagger Test", "version": "2.0.0"},
    "host": "api.test.com",
    "basePath": "/v1",
    "schemes": ["https"],
    "paths": {
        "/pets": {
            "get": {
                "summary": "List pets",
                "operationId": "listPets",
                "parameters": [
                    {"name": "limit", "in": "query", "type": "integer", "required": False},
                ],
                "responses": {
                    "200": {"description": "OK"},
                },
            }
        }
    },
}


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


class TestOpenApiParser:
    """Test suite for OpenApiParser."""

    def setup_method(self) -> None:
        self.parser = OpenApiParser()

    # --- parse_file ---

    def test_parse_file_json(self) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(OPENAPI_30_SPEC, f)
            tmp_path = f.name

        try:
            spec = self.parser.parse_file(tmp_path)
            assert isinstance(spec, ApiSpec)
            assert spec.title == "Test API"
            assert spec.openapi_version == "3.0.3"
            assert len(spec.endpoints) == 3
        finally:
            os.unlink(tmp_path)

    def test_parse_file_yaml(self) -> None:
        import yaml

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(OPENAPI_30_SPEC, f)
            tmp_path = f.name

        try:
            spec = self.parser.parse_file(tmp_path)
            assert isinstance(spec, ApiSpec)
            assert spec.title == "Test API"
            assert len(spec.endpoints) == 3
        finally:
            os.unlink(tmp_path)

    def test_parse_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            self.parser.parse_file("/nonexistent/spec.json")

    def test_parse_file_bad_extension(self) -> None:
        # FileNotFoundError is raised first (file doesn't exist),
        # so we need an existing file with a bad extension to test
        # the extension validation.
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".xml", delete=False
        ) as f:
            f.write("{}")
            tmp_path = f.name

        try:
            with pytest.raises(ValueError, match="Unsupported file extension"):
                self.parser.parse_file(tmp_path)
        finally:
            os.unlink(tmp_path)

    # --- parse_url ---

    def test_parse_url_http_error(self) -> None:
        with pytest.raises(RuntimeError, match="Failed to fetch|HTTP|URL error"):
            self.parser.parse_url("https://nonexistent-domain-xyz-12345.com/swagger.json")

    # --- OpenAPI 3.0 ---

    def test_openapi_v3_parsing(self) -> None:
        spec = self.parser._parse_dict(OPENAPI_30_SPEC)
        assert spec.openapi_version == "3.0.3"
        assert len(spec.endpoints) == 3

        methods = {(ep.method, ep.path) for ep in spec.endpoints}
        assert ("GET", "/items") in methods
        assert ("POST", "/items") in methods
        assert ("GET", "/items/{itemId}") in methods

    def test_openapi_v3_params(self) -> None:
        spec = self.parser._parse_dict(OPENAPI_30_SPEC)
        get_item = [ep for ep in spec.endpoints if ep.operation_id == "getItem"][0]
        assert len(get_item.parameters) == 1
        assert get_item.parameters[0]["name"] == "itemId"
        assert get_item.parameters[0]["in"] == "path"
        assert get_item.parameters[0]["required"] is True

    def test_openapi_v3_request_body(self) -> None:
        spec = self.parser._parse_dict(OPENAPI_30_SPEC)
        create = [ep for ep in spec.endpoints if ep.operation_id == "createItem"][0]
        assert create.request_body is not None
        assert create.request_body["required"] is True
        schema = create.request_body["schema"]
        assert schema["type"] == "object"
        assert "name" in schema.get("properties", {})

    def test_openapi_v3_responses(self) -> None:
        spec = self.parser._parse_dict(OPENAPI_30_SPEC)
        create = [ep for ep in spec.endpoints if ep.operation_id == "createItem"][0]
        assert "201" in create.responses
        assert "400" in create.responses

    def test_openapi_v3_security(self) -> None:
        spec_with_auth = dict(OPENAPI_30_SPEC)
        spec_with_auth["components"] = {
            "securitySchemes": {
                "bearerAuth": {"type": "http", "scheme": "bearer"},
            }
        }
        spec_with_auth["security"] = [{"bearerAuth": []}]
        spec = self.parser._parse_dict(spec_with_auth)
        assert "bearerAuth" in spec.security_definitions
        assert len(spec.security) == 1

    # --- Swagger 2.0 ---

    def test_swagger_v2_parsing(self) -> None:
        spec = self.parser._parse_dict(SWAGGER_20_SPEC)
        assert spec.openapi_version == "2.0"
        assert len(spec.endpoints) == 1
        assert spec.base_path == "/v1"

    def test_swagger_v2_endpoint(self) -> None:
        spec = self.parser._parse_dict(SWAGGER_20_SPEC)
        ep = spec.endpoints[0]
        assert ep.method == "GET"
        assert ep.path == "/pets"
        assert ep.operation_id == "listPets"

    # --- to_scenarios ---

    def test_to_scenarios_count(self) -> None:
        spec = self.parser._parse_dict(OPENAPI_30_SPEC)
        scenarios = self.parser.to_scenarios(spec)
        # 1 (GET /items) + 2 (POST /items: 201, 400) + 2 (GET /items/{itemId}: 200, 404) = 5
        assert len(scenarios) == 5

    def test_to_scenarios_structure(self) -> None:
        spec = self.parser._parse_dict(OPENAPI_30_SPEC)
        scenarios = self.parser.to_scenarios(spec)
        for s in scenarios:
            assert "uid" in s
            assert "method" in s
            assert "endpoint" in s
            assert "expected_status" in s
            assert "headers" in s
            assert "metadata" in s

    def test_to_scenarios_path_params_resolved(self) -> None:
        spec = self.parser._parse_dict(OPENAPI_30_SPEC)
        scenarios = self.parser.to_scenarios(spec)
        for s in scenarios:
            if "itemId" in s["endpoint"]:
                # itemId should be replaced with a dummy value
                assert "{itemId}" not in s["endpoint"]
                assert "123" in s["endpoint"]

    def test_to_scenarios_request_body(self) -> None:
        spec = self.parser._parse_dict(OPENAPI_30_SPEC)
        scenarios = self.parser.to_scenarios(spec)
        create_scenarios = [s for s in scenarios if s["method"] == "POST"]
        for s in create_scenarios:
            assert s["body"] is not None
            assert "name" in s["body"]

    # --- to_config_yaml ---

    def test_to_config_yaml(self) -> None:
        import yaml

        spec = self.parser._parse_dict(OPENAPI_30_SPEC)
        yaml_str = self.parser.to_config_yaml(spec)

        config = yaml.safe_load(yaml_str)
        assert "system" in config
        assert config["system"]["name"] == "test_api"
        assert config["system"]["base_url"] == "https://api.test.com"
        assert "endpoints" in config
        assert "items" in config["endpoints"]

    # --- spec auto-detection ---

    def test_unknown_spec_format(self) -> None:
        with pytest.raises(ValueError, match="missing 'openapi' or 'swagger'"):
            self.parser._parse_dict({"info": {"title": "No version"}})

    # --- wildcard status codes ---

    def test_wildcard_status_2xx(self) -> None:
        result = self.parser._parse_status_code("2XX")
        assert result is not None
        assert 200 in result
        assert 299 in result

    def test_wildcard_status_4xx(self) -> None:
        result = self.parser._parse_status_code("4XX")
        assert result is not None
        assert 400 in result
        assert 499 in result

    # --- edge cases ---

    def test_empty_spec(self) -> None:
        spec = self.parser._parse_dict({"openapi": "3.0.0", "info": {}, "paths": {}})
        assert len(spec.endpoints) == 0
        scenarios = self.parser.to_scenarios(spec)
        assert len(scenarios) == 0

    def test_no_servers(self) -> None:
        spec_dict = dict(OPENAPI_30_SPEC)
        spec_dict["servers"] = []
        spec = self.parser._parse_dict(spec_dict)
        base = self.parser._pick_base_url(spec)
        assert base == "https://api.example.com"

    def test_no_security(self) -> None:
        spec = self.parser._parse_dict(OPENAPI_30_SPEC)
        headers = self.parser._build_headers(spec.endpoints[0], spec)
        assert "Authorization" not in headers
        assert "Accept" in headers
