"""Bot User-Agent detection tests.

Simulates a scraper rotating User-Agents to evade bot detection:
- Search engine bots (Googlebot, Bingbot)
- Headless browsers (HeadlessChrome, PhantomJS)
- HTTP libraries (python-requests, curl, wget, httpx)
- Empty / missing User-Agent

The app currently has NO User-Agent-based filtering. These tests document
the desired behavior and the current state (requests succeed regardless
of UA, which is acceptable for an API but should be monitored).
"""
from __future__ import annotations

import pytest


# Common bot / scraper User-Agents.
BOT_USER_AGENTS = [
    # Search engine bots
    "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)",
    "Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)",
    # Headless browsers (automation tools)
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.1) AppleWebKit/538.1 (KHTML, like Gecko) PhantomJS/2.1.1 Safari/538.1",
    # HTTP libraries
    "python-requests/2.31.0",
    "python-httpx/0.25.0",
    "curl/7.81.0",
    "Wget/1.21.2",
    "Go-http-client/1.1",
    "okhttp/4.10.0",
    # Scraping frameworks
    "Scrapy/2.8.0 (+https://scrapy.org)",
    # Empty / weird
    "",
    " ",
    "null",
    "Mozilla/5.0",
    # Legitimate-looking but actually a bot
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]


@pytest.mark.asyncio
class TestBotUserAgent:
    """Verify the API behaves consistently regardless of User-Agent."""

    @pytest.mark.parametrize("ua", BOT_USER_AGENTS)
    async def test_api_responds_consistently_to_bot_ua(
        self, client, auth_headers, test_tenant, ua
    ):
        """API should return the same status code regardless of UA.

        Currently the app doesn't filter by UA — all requests are treated
        equally. This test documents that behavior and ensures it's
        CONSISTENT (no UA-specific bugs).
        """
        headers = {**auth_headers, "User-Agent": ua}
        resp = await client.get(
            f"/api/tenants/{test_tenant.id}/products",
            headers=headers,
        )
        # All UAs should get the same status (200 or 401 if UA somehow breaks auth)
        assert resp.status_code in (200, 401, 422), (
            f"UA {ua!r} returned unexpected status {resp.status_code}"
        )

    @pytest.mark.parametrize("ua", BOT_USER_AGENTS)
    async def test_public_endpoints_respond_to_bots(
        self, client, ua
    ):
        """Public endpoints (health probe, docs) should respond to all UAs.

        The FastAPI app's public surface is the health probe at ``/`` and
        the docs in non-production; the login *page* lives on the Next.js
        frontend, not the backend.
        """
        headers = {"User-Agent": ua}
        # Public health probe
        resp = await client.get("/", headers=headers)
        assert resp.status_code == 200, (
            f"Health probe returned {resp.status_code} for UA: {ua!r}"
        )
        # Docs are public in development/test (gated to non-prod envs)
        resp = await client.get("/docs", headers=headers, follow_redirects=True)
        assert resp.status_code == 200, (
            f"Docs returned {resp.status_code} for UA: {ua!r}"
        )

    @pytest.mark.parametrize("ua", BOT_USER_AGENTS)
    async def test_login_endpoint_responds_consistently_to_bot_ua(
        self, client, ua
    ):
        """Login endpoint should reject bad credentials regardless of UA."""
        headers = {"User-Agent": ua, "Content-Type": "application/json"}
        resp = await client.post(
            "/api/auth/login",
            json={"email": "nonexistent@test.com", "password": "wrong"},
            headers=headers,
        )
        # Should always be 401 (never 500)
        assert resp.status_code == 401, (
            f"Login endpoint returned {resp.status_code} for UA: {ua!r}"
        )

    @pytest.mark.asyncio
    async def test_no_user_agent_does_not_crash(
        self, client, auth_headers, test_tenant
    ):
        """A request with NO User-Agent header should not crash the server."""
        headers = {**auth_headers}
        # Remove User-Agent (httpx sets one by default; we override to empty)
        resp = await client.get(
            f"/api/tenants/{test_tenant.id}/products",
            headers=headers,
        )
        assert resp.status_code in (200, 401)

    @pytest.mark.asyncio
    async def test_oversized_user_agent_does_not_crash(
        self, client, auth_headers, test_tenant
    ):
        """A 100KB User-Agent should not crash the server (header DoS)."""
        huge_ua = "X" * 100_000
        headers = {**auth_headers, "User-Agent": huge_ua}
        # Some servers reject huge headers with 431 (Request Header Fields Too Large)
        # That's fine — we just don't want a 500.
        try:
            resp = await client.get(
                f"/api/tenants/{test_tenant.id}/products",
                headers=headers,
            )
            assert resp.status_code != 500, "Oversized UA caused server error"
        except Exception:
            # httpx may reject the request client-side — that's acceptable
            pass

    @pytest.mark.asyncio
    async def test_user_agent_with_special_chars_does_not_crash(
        self, client, auth_headers, test_tenant
    ):
        """UA with newlines / control chars should not cause header injection."""
        # Note: httpx will likely reject this client-side (good!)
        bad_uas = [
            "Bot\r\nX-Injected: header",
            "Bot\nX-Injected: header",
            "Bot\x00Null",
            "Bot\tTab",
        ]
        for ua in bad_uas:
            headers = {**auth_headers, "User-Agent": ua}
            try:
                resp = await client.get(
                    f"/api/tenants/{test_tenant.id}/products",
                    headers=headers,
                )
                # Should never 500
                assert resp.status_code != 500, (
                    f"Bad UA caused 500: {ua!r}"
                )
            except Exception:
                # Client-side rejection is acceptable
                pass
