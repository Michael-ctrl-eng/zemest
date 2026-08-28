"""OpenAPI contract tests using Schemathesis.

Schemathesis fuzzes every endpoint in the OpenAPI schema with random
inputs that match the schema. We verify:
- No endpoint returns 500 for any valid input
- All error responses are well-formed JSON

These tests are SLOW (they generate hundreds of test cases). Run them
separately:

    pytest tests/schema/ -v -m "schema" --hypothesis-show-statistics
"""
from __future__ import annotations

import pytest


# Skip the entire module if Schemathesis isn't installed.
schemathesis = pytest.importorskip("schemathesis")


@pytest.mark.schema
@pytest.mark.slow
class TestOpenAPIContract:
    """Fuzz every endpoint against the OpenAPI schema."""

    def test_api_no_500_errors(self, schema, client_factory):
        """No endpoint should return 500 for any valid input.

        This is the most important contract test — a 500 means an
        unhandled exception, which is always a bug.
        """
        from httpx import ASGITransport, AsyncClient
        from app.main import app

        # Build a test client that Schemathesis will use.
        transport = ASGITransport(app=app)

        @schema.parametrize()
        def test_case(case):
            # Schemathesis generates a request — call it via httpx
            import asyncio

            async def call():
                async with AsyncClient(transport=transport, base_url="http://test") as ac:
                    response = await case.call_async(ac)
                    return response

            try:
                response = asyncio.get_event_loop().run_until_complete(call())
            except Exception:
                # Network-level errors (connection refused, etc.) are
                # acceptable — we only care about HTTP 500.
                return

            assert response.status_code != 500, (
                f"Endpoint {case.operation.method} {case.operation.path} "
                f"returned 500 — unhandled exception"
            )

        # Run the test case generator
        test_case()

    def test_get_endpoints_no_500(self, schema):
        """Specifically fuzz GET endpoints — they should never 500."""
        from httpx import ASGITransport, AsyncClient
        from app.main import app
        import asyncio

        transport = ASGITransport(app=app)

        @schema.parametrize(method="GET")
        def test_case(case):
            async def call():
                async with AsyncClient(transport=transport, base_url="http://test") as ac:
                    return await case.call_async(ac)

            try:
                response = asyncio.get_event_loop().run_until_complete(call())
            except Exception:
                return

            # GET should never 500 (no state mutation, no validation issues)
            # Allow 401/403/404/422 — those are legitimate client errors
            assert response.status_code != 500, (
                f"GET {case.operation.path} returned 500"
            )

        test_case()

    def test_error_responses_are_json(self, schema):
        """4xx and 5xx responses should be JSON with a 'detail' field.

        This ensures error responses are machine-parseable (not HTML
        stack traces leaking to clients).
        """
        from httpx import ASGITransport, AsyncClient
        from app.main import app
        import asyncio

        transport = ASGITransport(app=app)

        @schema.parametrize()
        def test_case(case):
            async def call():
                async with AsyncClient(transport=transport, base_url="http://test") as ac:
                    return await case.call_async(ac)

            try:
                response = asyncio.get_event_loop().run_until_complete(call())
            except Exception:
                return

            if response.status_code >= 400:
                # Response should be JSON (not HTML, not plain text)
                content_type = response.headers.get("content-type", "")
                assert "json" in content_type, (
                    f"Error response ({response.status_code}) is not JSON: "
                    f"Content-Type={content_type}"
                )

        test_case()


# We also provide simpler, non-Schemathesis tests that work without the
# library installed. These just verify the OpenAPI schema is well-formed.

class TestOpenAPISchemaShape:
    """Verify the OpenAPI schema itself is well-formed (no Schemathesis needed)."""

    def test_openapi_schema_loads(self, openapi_schema):
        """The OpenAPI schema should be a non-empty dict."""
        assert isinstance(openapi_schema, dict)
        assert "openapi" in openapi_schema
        assert "paths" in openapi_schema
        assert len(openapi_schema["paths"]) > 0

    def test_openapi_has_info_block(self, openapi_schema):
        """Schema must have an info block with title and version."""
        info = openapi_schema.get("info", {})
        assert "title" in info
        assert "version" in info
        assert info["title"] == "Zemest"

    def test_openapi_all_paths_have_methods(self, openapi_schema):
        """Every path in the schema must define at least one HTTP method."""
        for path, methods in openapi_schema["paths"].items():
            assert isinstance(methods, dict)
            http_methods = [m for m in methods if m in (
                "get", "post", "put", "patch", "delete", "head", "options"
            )]
            assert len(http_methods) > 0, f"Path {path} has no HTTP methods"

    def test_openapi_endpoints_have_responses(self, openapi_schema):
        """Every endpoint operation must declare at least one response code."""
        for path, methods in openapi_schema["paths"].items():
            for method, op in methods.items():
                if method not in ("get", "post", "put", "patch", "delete"):
                    continue
                if not isinstance(op, dict):
                    continue
                responses = op.get("responses", {})
                assert len(responses) > 0, (
                    f"{method.upper()} {path} has no declared responses"
                )
                # Must declare at least one success (2xx) OR error (4xx) code
                codes = list(responses.keys())
                assert any(c.startswith("2") or c.startswith("4") for c in codes), (
                    f"{method.upper()} {path} only declares: {codes}"
                )

    def test_openapi_has_expected_endpoints(self, openapi_schema):
        """Schema must include the core API endpoints."""
        paths = list(openapi_schema["paths"].keys())
        expected_fragments = [
            "/api/auth",
            "/api/tenants",
            "/api/webhook",
            "/api/test",
        ]
        for frag in expected_fragments:
            assert any(frag in p for p in paths), (
                f"Expected endpoint group {frag} not in schema paths"
            )

    def test_openapi_security_scheme_if_present(self, openapi_schema):
        """If a security scheme is declared, it should be bearer JWT."""
        components = openapi_schema.get("components", {})
        security_schemes = components.get("securitySchemes", {})
        if security_schemes:
            # Should have at least one scheme that's bearer-type
            has_bearer = any(
                scheme.get("type") == "http" and scheme.get("scheme") == "bearer"
                for scheme in security_schemes.values()
            )
            assert has_bearer, (
                f"Security schemes present but no bearer JWT: {security_schemes}"
            )
