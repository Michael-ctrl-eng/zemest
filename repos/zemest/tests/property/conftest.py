"""Shared fixtures for property-based tests.

Most property tests are pure (no DB, no HTTP) — they call validation
functions directly. We override the root ``setup_db`` autouse fixture
with a no-op so property tests don't pay the DB setup cost (and don't
hit the pre-existing table-creation flakiness).
"""
import os
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


@pytest.fixture(autouse=True)
def setup_db():
    """Override the root setup_db fixture — property tests don't need a DB."""
    yield
