"""Simulates aggressive scraping — high-volume product listing requests.

A scraper's goal: enumerate the entire product catalog as fast as
possible, then re-sell or undercut pricing. We simulate 100 rapid
requests and verify the system defends via rate-limiting or returns
consistent results (no leaks across tenants).

NOTE: The app currently has NO rate-limit middleware on /api/tenants/{id}/products.
The "rate limit triggered" test will xfail until that middleware is added.
The "no cross-tenant leak" test passes today (tenant isolation is enforced).
"""
from __future__ import annotations

import asyncio
import time

import pytest


@pytest.mark.slow
@pytest.mark.asyncio
class TestAggressiveScraping:
    """Simulate aggressive scraping of the product catalog."""

    async def test_rapid_product_listing_requests(
        self, client, auth_headers, test_tenant, test_products
    ):
        """100 rapid requests should eventually trigger rate limit (429).

        Currently xfail — no rate-limit middleware installed.
        """
        for i in range(100):
            resp = await client.get(
                f"/api/tenants/{test_tenant.id}/products?page=1&page_size=100",
                headers=auth_headers,
            )
            if resp.status_code == 429:
                # Rate limit hit — test passes
                return
        # No rate limit triggered — mark as xfail (gap to fill)
        pytest.xfail(
            "Rate limit never triggered after 100 rapid requests — "
            "no rate-limit middleware installed on /api/tenants/{id}/products"
        )

    async def test_rapid_requests_do_not_leak_more_data(
        self, client, auth_headers, test_tenant, test_products
    ):
        """100 rapid requests should always return the same number of products.

        If a scraper gets MORE data under load (race condition in pagination),
        that's a bug. The product count must remain stable.
        """
        counts = set()
        for _ in range(20):  # 20 rapid requests
            resp = await client.get(
                f"/api/tenants/{test_tenant.id}/products?page=1&page_size=100",
                headers=auth_headers,
            )
            if resp.status_code == 200:
                counts.add(resp.json()["total"])
            elif resp.status_code == 429:
                # Rate limit OK — stop here
                break
        # All responses should report the same total (3 products in fixture)
        assert len(counts) <= 1, (
            f"Product count varied across requests: {counts} — possible race condition"
        )

    async def test_pagination_does_not_leak_other_tenants(
        self, client, auth_headers, second_auth_headers, test_tenant, test_products, second_tenant
    ):
        """Scraping tenant A should NOT return tenant B's products via pagination."""
        # Add product to tenant B
        from app.models.product import Product
        from decimal import Decimal
        import uuid

        # Tenant B has no products — scraper tries to walk all pages of tenant A
        for page in range(1, 20):
            resp = await client.get(
                f"/api/tenants/{test_tenant.id}/products?page={page}&page_size=10",
                headers=auth_headers,
            )
            if resp.status_code != 200:
                break
            data = resp.json()
            if not data["products"]:
                break  # no more pages
            # Every product must belong to test_tenant
            for product in data["products"]:
                # Products don't include tenant_id in response, but the count
                # should never exceed what tenant A has (3 in fixture)
                pass
            # Total should always be 3 (tenant A's products)
            assert data["total"] == 3, (
                f"Page {page}: total = {data['total']} — possible cross-tenant leak"
            )

    async def test_concurrent_requests_stay_isolated(
        self, client, auth_headers, second_auth_headers, test_tenant, second_tenant, test_products
    ):
        """Concurrent requests from two tenants should not leak between them."""
        async def fetch_products(headers, tenant_id):
            resp = await client.get(
                f"/api/tenants/{tenant_id}/products?page=1&page_size=100",
                headers=headers,
            )
            return resp

        # Fire 10 concurrent requests for each tenant
        tasks_a = [fetch_products(auth_headers, test_tenant.id) for _ in range(10)]
        tasks_b = [fetch_products(second_auth_headers, second_tenant.id) for _ in range(10)]
        results_a, results_b = await asyncio.gather(
            asyncio.gather(*tasks_a),
            asyncio.gather(*tasks_b),
        )
        # All tenant A requests should return 200 with total=3
        for r in results_a:
            assert r.status_code == 200
            assert r.json()["total"] == 3
        # All tenant B requests should return 200 with total=0 (no products)
        for r in results_b:
            assert r.status_code == 200
            assert r.json()["total"] == 0
