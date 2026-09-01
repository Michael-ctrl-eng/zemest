"""SQL injection tests.

Simulates a hacker sending classic SQL-injection payloads via query
parameters and JSON bodies. The defense under test is SQLAlchemy's
parameterized queries — inputs are never concatenated into SQL strings.

We assert:
- No endpoint returns 500 (server crash from bad SQL = unacceptable)
- No injected payload leaks data from OTHER tenants
- DROP/UNION payloads don't actually alter the schema
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import inspect, text

from app.models.product import Product


# Classic SQL injection payloads — covers UNION, DROP, OR 1=1, stacked queries.
SQL_INJECTION_PAYLOADS = [
    "' OR '1'='1",
    "' OR '1'='1' --",
    "'; DROP TABLE products; --",
    "' UNION SELECT * FROM users --",
    "1'; EXEC xp_cmdshell('dir') --",
    "' OR 1=1 #",
    "admin'--",
    "' OR ''='",
    "1; SELECT * FROM tenants; --",
    "%27%20OR%20%271%27%3D%271",  # URL-encoded ' OR '1'='1
    "\\x00' OR 1=1 --",  # null byte + injection
    "' OR SLEEP(5) --",  # time-based blind
    "1' AND 1=CONVERT(int, (SELECT TOP 1 name FROM sys.tables)) --",
]


@pytest.mark.asyncio
class TestSQLInjection:
    """SQL injection must not crash the API or leak data."""

    async def test_sql_injection_in_product_search(
        self, client, auth_headers, test_tenant, test_products
    ):
        """Search field should not allow SQL injection — never 500, no leak."""
        for payload in SQL_INJECTION_PAYLOADS:
            resp = await client.get(
                f"/api/tenants/{test_tenant.id}/products",
                params={"search": payload},
                headers=auth_headers,
            )
            assert resp.status_code in (200, 422), (
                f"Payload {payload!r} returned {resp.status_code} — "
                f"possible SQL injection vulnerability"
            )
            # Verify only this tenant's products were returned (3 in fixture)
            if resp.status_code == 200:
                data = resp.json()
                assert data["total"] <= 3, (
                    f"Payload {payload!r} leaked more rows than expected"
                )

    async def test_sql_injection_in_product_name(
        self, client, auth_headers, test_tenant, db_session
    ):
        """Product name with SQL injection should be stored safely (escaped)."""
        for payload in SQL_INJECTION_PAYLOADS:
            resp = await client.post(
                f"/api/tenants/{test_tenant.id}/products",
                json={"name": payload, "price": "100.00"},
                headers=auth_headers,
            )
            # 201 (created) or 409 (duplicate) — never 500
            assert resp.status_code in (201, 409), (
                f"Payload {payload!r} returned {resp.status_code}"
            )
            # Clean up so subsequent payloads don't conflict on duplicate name
            if resp.status_code == 201:
                product_id = resp.json()["id"]
                await client.delete(
                    f"/api/tenants/{test_tenant.id}/products/{product_id}",
                    headers=auth_headers,
                )

    async def test_sql_injection_in_order_customer_name(
        self, client, auth_headers, test_tenant
    ):
        """Customer name with injection should be stored safely."""
        for payload in SQL_INJECTION_PAYLOADS:
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
            assert resp.status_code in (201, 422), (
                f"Payload {payload!r} returned {resp.status_code}"
            )

    async def test_sql_injection_does_not_drop_tables(
        self, client, auth_headers, test_tenant, db_session
    ):
        """'; DROP TABLE products; -- must NOT actually drop the table."""
        # Send the DROP payload
        resp = await client.get(
            f"/api/tenants/{test_tenant.id}/products",
            params={"search": "'; DROP TABLE products; --"},
            headers=auth_headers,
        )
        assert resp.status_code in (200, 422)

        # Verify the products table still exists (async engines don't
        # support inspect() — the SELECT itself is the existence check)
        result = await db_session.execute(text("SELECT COUNT(*) FROM products"))
        count = result.scalar()
        assert count is not None, "products table was dropped by injection!"

    async def test_sql_injection_in_pagination_params(
        self, client, auth_headers, test_tenant
    ):
        """Page / page_size with injection must be rejected (422) or coerced."""
        bad_params = [
            ("page", "1; DROP TABLE users; --"),
            ("page_size", "100; SELECT * FROM tenants"),
            ("page", "' OR 1=1"),
            ("page_size", "0x00"),
        ]
        for param, value in bad_params:
            resp = await client.get(
                f"/api/tenants/{test_tenant.id}/products",
                params={param: value},
                headers=auth_headers,
            )
            # Pydantic should reject non-int with 422, never 500
            assert resp.status_code in (200, 422), (
                f"Param {param}={value!r} returned {resp.status_code}"
            )

    async def test_no_data_leak_across_tenants_via_injection(
        self, client, second_auth_headers, test_tenant, test_products
    ):
        """SQL injection should NOT leak products from another tenant."""
        # Try a UNION attack via search
        union_payloads = [
            "' UNION SELECT id, name, price, tenant_id FROM products WHERE tenant_id != '{}' --".format(test_tenant.id),
            "' UNION SELECT * FROM products --",
        ]
        for payload in union_payloads:
            resp = await client.get(
                f"/api/tenants/{test_tenant.id}/products",
                params={"search": payload},
                headers=second_auth_headers,  # attacker's token
            )
            # Attacker should get 404 — they don't own this tenant
            assert resp.status_code == 404, (
                f"Attacker accessed victim tenant with payload {payload!r}"
            )

    async def test_time_based_injection_does_not_delay(
        self, client, auth_headers, test_tenant, test_products
    ):
        """SLEEP-based injection should not cause noticeable delay."""
        import time
        start = time.monotonic()
        resp = await client.get(
            f"/api/tenants/{test_tenant.id}/products",
            params={"search": "' OR SLEEP(5) --"},
            headers=auth_headers,
        )
        elapsed = time.monotonic() - start
        assert resp.status_code in (200, 422)
        # If SLEEP(5) had executed, this would be > 5 seconds.
        assert elapsed < 3.0, (
            f"Time-based SQL injection caused {elapsed:.2f}s delay — "
            f"possible vulnerability"
        )
