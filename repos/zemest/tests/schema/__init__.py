"""API contract tests using Schemathesis.

These tests fuzz every endpoint in the OpenAPI schema with random inputs
and verify:
- No endpoint returns 500 (server crash)
- All 4xx errors are well-formed (JSON with `detail` field)
- Response schemas match the OpenAPI spec

Schemathesis is heavy — these tests are SLOW. Run them separately:

    pytest tests/schema/ -v -m "schema"
"""
