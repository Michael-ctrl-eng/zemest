"""Fixtures for Schemathesis tests.

Loads the OpenAPI schema from the running app (no need to start a server).
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def pytest_collection_modifyitems(config, items):
    """Auto-mark all tests in this directory with @pytest.mark.schema."""
    for item in items:
        if "tests/schema/" in str(item.fspath):
            item.add_marker(pytest.mark.schema)
            item.add_marker(pytest.mark.slow)


@pytest.fixture(scope="session")
def openapi_schema():
    """Return the OpenAPI schema dict directly from the app.

    Avoids the need for a running server. Schemathesis can load from a dict.
    """
    try:
        import schemathesis
    except ImportError:
        pytest.skip("Schemathesis not installed. Run: pip install schemathesis")

    from app.main import app
    schema_dict = app.openapi()
    return schema_dict


@pytest.fixture(scope="session")
def schema(openapi_schema):
    """Build a Schemathesis schema object from the app's OpenAPI dict."""
    import schemathesis
    return schemathesis.from_dict(openapi_schema)
