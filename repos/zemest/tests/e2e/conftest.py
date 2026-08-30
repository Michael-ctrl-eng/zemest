"""Fixtures for Playwright e2e tests.

Provides:
- ``browser`` — a launched chromium instance (skipped if Playwright isn't installed)
- ``base_url`` — the server URL (override via env var E2E_BASE_URL)
- ``e2e_user`` / ``e2e_tenant`` — created via direct API calls so the
  browser flow has data to work with
"""
from __future__ import annotations

import os
import sys
import uuid

import pytest
import pytest_asyncio

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def pytest_collection_modifyitems(config, items):
    """Auto-mark all tests in this directory with @pytest.mark.e2e."""
    for item in items:
        if "tests/e2e/" in str(item.fspath):
            item.add_marker(pytest.mark.e2e)


@pytest.fixture(scope="session")
def base_url() -> str:
    """Server URL — defaults to localhost:8000, override with E2E_BASE_URL."""
    return os.getenv("E2E_BASE_URL", "http://localhost:8000")


@pytest.fixture(scope="session")
def browser():
    """Launch a Playwright chromium instance.

    Skips the test session if Playwright is not installed.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        pytest.skip("Playwright is not installed. Run: pip install pytest-playwright && playwright install chromium")

    # We use sync_playwright for simplicity; pytest-playwright handles event loop.
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        pytest.skip("playwright.sync_api not available")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture
def context(browser):
    """Fresh browser context (cookies, storage) per test."""
    ctx = browser.new_context()
    yield ctx
    ctx.close()


@pytest.fixture
def page(context):
    """A fresh page per test."""
    p = context.new_page()
    yield p
    p.close()


@pytest_asyncio.fixture
async def e2e_user_and_tenant(client):
    """Create a user + tenant via the API so the browser flow has data."""
    email = f"e2e_{uuid.uuid4().hex[:8]}@test.com"
    password = "TestPass123!"

    # Register
    resp = await client.post("/api/auth/register", json={
        "name": "E2E Merchant",
        "email": email,
        "password": password,
    })
    assert resp.status_code == 200, f"Failed to register e2e user: {resp.text}"
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # Create tenant
    resp = await client.post("/api/tenants", json={
        "page_name": "E2E Fashion Store",
        "website_url": "https://e2e-test-store.com",
        "business_email": email,
    }, headers=headers)
    assert resp.status_code == 200
    tenant_id = resp.json()["id"]

    return {
        "email": email,
        "password": password,
        "token": token,
        "headers": headers,
        "tenant_id": tenant_id,
    }
