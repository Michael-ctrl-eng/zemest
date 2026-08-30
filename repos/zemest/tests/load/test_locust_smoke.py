"""Smoke test for the locustfile — verifies it imports cleanly.

This is a pytest-runnable test that does NOT actually run a load test.
It just imports the locustfile module and verifies the User classes
have the expected task methods. Useful for CI validation before
running real load tests.

Run:
    pytest tests/load/test_locust_smoke.py -v -m "load"
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest


LOCUSTFILE = Path(__file__).parent / "locustfile.py"


def _load_locustfile_module():
    """Dynamically import locustfile.py as a module (since its filename
    isn't a valid Python identifier for `import`)."""
    spec = importlib.util.spec_from_file_location("locustfile_under_test", LOCUSTFILE)
    if spec is None or spec.loader is None:
        pytest.skip("Could not load locustfile.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.load
class TestLocustfileSmoke:
    """Verify the locustfile is structurally valid."""

    def test_locustfile_exists(self):
        assert LOCUSTFILE.exists(), "locustfile.py not found"

    def test_locustfile_imports_cleanly(self):
        """The locustfile should import without raising (even without locust installed)."""
        module = _load_locustfile_module()
        assert module is not None

    def test_merchant_user_class_exists(self):
        module = _load_locustfile_module()
        assert hasattr(module, "MerchantUser"), "MerchantUser class missing"

    def test_anonymous_user_class_exists(self):
        module = _load_locustfile_module()
        assert hasattr(module, "AnonymousUser"), "AnonymousUser class missing"

    def test_merchant_user_has_tasks(self):
        """MerchantUser must define the core task methods."""
        module = _load_locustfile_module()
        cls = module.MerchantUser
        # Methods that should exist (whether or not they're decorated)
        for method_name in [
            "on_start",
            "view_products",
            "view_orders",
            "view_conversations",
            "view_stats",
            "test_chat",
            "list_tenants",
            "view_me",
        ]:
            assert hasattr(cls, method_name), f"Missing method: {method_name}"

    def test_anonymous_user_has_tasks(self):
        """AnonymousUser must define anon-task methods."""
        module = _load_locustfile_module()
        cls = module.AnonymousUser
        for method_name in ["view_login_page", "view_docs", "view_openapi", "failed_login_attempt"]:
            assert hasattr(cls, method_name), f"Missing method: {method_name}"

    def test_chat_messages_non_empty(self):
        """The chat message pool must be non-empty."""
        module = _load_locustfile_module()
        assert hasattr(module, "CHAT_MESSAGES")
        assert len(module.CHAT_MESSAGES) > 0
        # All messages must be non-empty strings
        for msg in module.CHAT_MESSAGES:
            assert isinstance(msg, str)
            assert len(msg) > 0
