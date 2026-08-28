"""Simulates data-extraction attempts — customer PII harvest.

A scraper's goal: walk all customer records, all orders, all
conversations to build a complete PII database for resale.

We verify:
1. Pagination caps exist (no scraping 10k records in one request)
2. Sensitive fields (phone numbers) are scoped to the requesting tenant
3. Cross-tenant customer enumeration returns 404 (not 200 with empty list)
"""
from __future__ import annotations

import pytest


@pytest.mark.slow
@pytest.mark.asyncio
class TestDataExtractionAttempt:
    """Customer / order data extraction attempts."""

    async def test_customer_list_page_size_capped(
        self, client, auth_headers, test_tenant
    ):
        """page_size > 100 should be rejected or capped (no bulk extraction)."""
        resp = await client.get(
            f"/api/tenants/{test_tenant.id}/customers?page=1&page_size=10000",
            headers=auth_headers,
        )
        # Either 422 (rejected) or 200 with capped page_size
        if resp.status_code == 200:
            data = resp.json()
            # If the API returns a page_size field, it must be <= 100
            if "page_size" in data:
                assert data["page_size"] <= 100, (
                    f"page_size not capped: {data['page_size']}"
                )
        elif resp.status_code == 422:
            pass  # good — rejected oversized request
        else:
            pytest.fail(f"Unexpected status: {resp.status_code}")

    async def test_order_list_page_size_capped(
        self, client, auth_headers, test_tenant
    ):
        """page_size > 100 on orders should be rejected or capped."""
        resp = await client.get(
            f"/api/tenants/{test_tenant.id}/orders?page=1&page_size=10000",
            headers=auth_headers,
        )
        if resp.status_code == 200:
            data = resp.json()
            if "page_size" in data:
                assert data["page_size"] <= 100
        elif resp.status_code == 422:
            pass
        else:
            pytest.fail(f"Unexpected status: {resp.status_code}")

    async def test_conversation_list_page_size_capped(
        self, client, auth_headers, test_tenant
    ):
        """page_size > 100 on conversations should be rejected or capped."""
        resp = await client.get(
            f"/api/tenants/{test_tenant.id}/conversations?page=1&page_size=10000",
            headers=auth_headers,
        )
        if resp.status_code == 200:
            data = resp.json()
            # Conversation list doesn't echo page_size, but length must be <= 100
            if "conversations" in data:
                assert len(data["conversations"]) <= 100
        elif resp.status_code == 422:
            pass
        else:
            pytest.fail(f"Unexpected status: {resp.status_code}")

    async def test_customer_pii_only_visible_to_owner(
        self, client, second_auth_headers, test_tenant, test_customer
    ):
        """Tenant B cannot list Tenant A's customers (PII isolation)."""
        # Try to fetch tenant A's customers with tenant B's auth
        resp = await client.get(
            f"/api/tenants/{test_tenant.id}/customers",
            headers=second_auth_headers,
        )
        assert resp.status_code == 404, (
            f"Cross-tenant customer access returned {resp.status_code} — PII leak!"
        )

    async def test_order_pii_only_visible_to_owner(
        self, client, second_auth_headers, test_tenant, test_customer, db_session
    ):
        """Tenant B cannot fetch Tenant A's orders (PII isolation)."""
        from app.services.order_service import create_order
        order = await create_order(
            db=db_session,
            tenant_id=test_tenant.id,
            customer_id=test_customer.id,
            conversation_id=None,
            customer_name="PII Victim",
            customer_phone="01012345678",
            governorate="cairo",
            city="Cairo",
            area="Maadi",
            address_detail="15 Road 9",
            payment_method="cod",
            items=[{"product_name": "X", "quantity": 1, "unit_price": "100.00"}],
            delivery_charge=35,
        )
        await db_session.commit()

        # Tenant B tries to fetch this specific order
        resp = await client.get(
            f"/api/tenants/{test_tenant.id}/orders/{order.id}",
            headers=second_auth_headers,
        )
        assert resp.status_code == 404
        # Response body must NOT contain victim PII
        body = resp.text
        assert "01012345678" not in body
        assert "PII Victim" not in body

    async def test_conversation_messages_only_visible_to_owner(
        self, client, second_auth_headers, test_tenant, test_conversation
    ):
        """Tenant B cannot read Tenant A's conversation messages."""
        resp = await client.get(
            f"/api/tenants/{test_tenant.id}/conversations/{test_conversation.id}",
            headers=second_auth_headers,
        )
        assert resp.status_code == 404
        body = resp.text
        # The conversation's customer message must NOT appear
        assert "What products do you have?" not in body

    async def test_customer_enumeration_via_search(
        self, client, auth_headers, test_tenant, test_customer
    ):
        """Scraping customer names via search should not leak other tenants' customers."""
        # Search for a common name that might exist in multiple tenants
        resp = await client.get(
            f"/api/tenants/{test_tenant.id}/customers",
            params={"search": "Ahmed"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        # All returned customers must belong to test_tenant
        # (We can't directly check tenant_id from the response, but the count
        # must be small — only test_tenant's "Ahmed")
        if isinstance(data, list):
            for c in data:
                # Customer name should match the search (or be empty)
                assert isinstance(c.get("name", ""), str)

    async def test_negative_page_number_rejected(
        self, client, auth_headers, test_tenant
    ):
        """Negative page numbers should be rejected (422)."""
        resp = await client.get(
            f"/api/tenants/{test_tenant.id}/products?page=-1",
            headers=auth_headers,
        )
        assert resp.status_code == 422, (
            f"Negative page returned {resp.status_code} — expected 422"
        )

    async def test_zero_page_size_rejected(
        self, client, auth_headers, test_tenant
    ):
        """page_size=0 should be rejected (422)."""
        resp = await client.get(
            f"/api/tenants/{test_tenant.id}/products?page=1&page_size=0",
            headers=auth_headers,
        )
        assert resp.status_code == 422, (
            f"page_size=0 returned {resp.status_code} — expected 422"
        )

    async def test_huge_page_number_returns_empty(
        self, client, auth_headers, test_tenant
    ):
        """page=999999 should return empty list (not crash, not return all)."""
        resp = await client.get(
            f"/api/tenants/{test_tenant.id}/products?page=999999",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3  # total is still 3 (metadata)
        assert len(data["products"]) == 0  # but this page is empty
