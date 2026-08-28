"""IDOR (Insecure Direct Object Reference) tests.

Simulates a hacker who has a valid account trying to read/modify
another tenant's data by guessing or enumerating tenant_id / order_id.

The defense under test is in `app/dependencies.get_tenant`: it queries
`Tenant.id == tenant_id AND Tenant.owner_id == user.id` and returns 404
when the row is missing. This means an attacker gets 404 (NOT 403) —
which hides the existence of the resource.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.models.order import Order
from app.models.product import Product
from app.services.order_service import create_order


@pytest.mark.asyncio
class TestIDOR:
    """Cross-tenant access attempts must be denied."""

    async def test_user_cannot_access_other_tenant_orders_list(
        self, client, second_auth_headers, test_tenant
    ):
        """User B should NOT see User A's orders list."""
        resp = await client.get(
            f"/api/tenants/{test_tenant.id}/orders",
            headers=second_auth_headers,
        )
        # 404 (not 403) — hides resource existence
        assert resp.status_code == 404, (
            f"IDOR: attacker got {resp.status_code} on victim's orders list"
        )

    async def test_user_cannot_access_other_tenant_specific_order(
        self, client, second_auth_headers, test_tenant, test_customer, db_session
    ):
        """User B should NOT fetch a specific order in User A's tenant."""
        order = await create_order(
            db=db_session,
            tenant_id=test_tenant.id,
            customer_id=test_customer.id,
            conversation_id=None,
            customer_name="Victim Customer",
            customer_phone="01012345678",
            governorate="cairo",
            city="Cairo",
            area="Maadi",
            address_detail="15 Road 9",
            payment_method="cod",
            items=[{"product_name": "Stolen Item", "quantity": 1, "unit_price": "500.00"}],
            delivery_charge=35,
        )
        await db_session.commit()

        resp = await client.get(
            f"/api/tenants/{test_tenant.id}/orders/{order.id}",
            headers=second_auth_headers,
        )
        assert resp.status_code == 404

    async def test_user_cannot_access_other_tenant_products(
        self, client, second_auth_headers, test_tenant
    ):
        """User B should NOT list User A's products."""
        resp = await client.get(
            f"/api/tenants/{test_tenant.id}/products",
            headers=second_auth_headers,
        )
        assert resp.status_code == 404

    async def test_user_cannot_modify_other_tenant_product(
        self, client, second_auth_headers, test_tenant, test_products
    ):
        """User B should NOT be able to PATCH User A's product."""
        victim_product = test_products[0]
        resp = await client.patch(
            f"/api/tenants/{test_tenant.id}/products/{victim_product.id}",
            json={"name": "Hacked by Attacker"},
            headers=second_auth_headers,
        )
        assert resp.status_code == 404

    async def test_user_cannot_delete_other_tenant_product(
        self, client, second_auth_headers, test_tenant, test_products
    ):
        """User B should NOT be able to DELETE User A's product."""
        victim_product = test_products[0]
        resp = await client.delete(
            f"/api/tenants/{test_tenant.id}/products/{victim_product.id}",
            headers=second_auth_headers,
        )
        assert resp.status_code == 404

    async def test_user_cannot_access_other_tenant_stats(
        self, client, second_auth_headers, test_tenant
    ):
        """User B should NOT see User A's tenant stats."""
        resp = await client.get(
            f"/api/tenants/{test_tenant.id}/stats",
            headers=second_auth_headers,
        )
        assert resp.status_code == 404

    async def test_user_cannot_access_other_tenant_conversations(
        self, client, second_auth_headers, test_tenant
    ):
        """User B should NOT list User A's conversations."""
        resp = await client.get(
            f"/api/tenants/{test_tenant.id}/conversations",
            headers=second_auth_headers,
        )
        assert resp.status_code == 404

    async def test_user_cannot_modify_other_tenant_settings(
        self, client, second_auth_headers, test_tenant
    ):
        """User B should NOT PATCH User A's tenant settings."""
        resp = await client.patch(
            f"/api/tenants/{test_tenant.id}",
            json={"page_name": "Hacked Store"},
            headers=second_auth_headers,
        )
        assert resp.status_code == 404

    async def test_user_cannot_modify_other_tenant_order_status(
        self, client, second_auth_headers, test_tenant, test_customer, db_session
    ):
        """User B should NOT change User A's order status (e.g., to cancel it)."""
        order = await create_order(
            db=db_session,
            tenant_id=test_tenant.id,
            customer_id=test_customer.id,
            conversation_id=None,
            customer_name="Victim",
            customer_phone="01012345678",
            governorate="cairo",
            city="Cairo",
            area="Maadi",
            address_detail="15 Road 9",
            payment_method="cod",
            items=[{"product_name": "Bag", "quantity": 1, "unit_price": "1000.00"}],
            delivery_charge=35,
        )
        await db_session.commit()

        resp = await client.patch(
            f"/api/tenants/{test_tenant.id}/orders/{order.id}/status",
            json={"status": "cancelled"},
            headers=second_auth_headers,
        )
        assert resp.status_code == 404

    async def test_user_cannot_access_other_tenant_with_random_uuid(
        self, client, second_auth_headers
    ):
        """Even with a totally random UUID, attacker should get 404."""
        random_uuid = uuid.uuid4()
        resp = await client.get(
            f"/api/tenants/{random_uuid}/products",
            headers=second_auth_headers,
        )
        assert resp.status_code == 404

    async def test_user_cannot_access_other_tenant_with_malformed_uuid(
        self, client, second_auth_headers
    ):
        """Malformed tenant_id should be rejected (422 or 404, never 500)."""
        resp = await client.get(
            "/api/tenants/not-a-uuid/products",
            headers=second_auth_headers,
        )
        assert resp.status_code in (404, 422), (
            f"Malformed UUID returned {resp.status_code} — expected 404/422"
        )

    async def test_user_a_can_access_own_tenant(
        self, client, auth_headers, test_tenant
    ):
        """Sanity check: User A CAN access their own tenant."""
        resp = await client.get(
            f"/api/tenants/{test_tenant.id}/products",
            headers=auth_headers,
        )
        assert resp.status_code == 200

    async def test_idor_does_not_leak_tenant_existence(
        self, client, second_auth_headers, test_tenant
    ):
        """The 404 response body should NOT confirm the tenant exists."""
        resp = await client.get(
            f"/api/tenants/{test_tenant.id}/products",
            headers=second_auth_headers,
        )
        assert resp.status_code == 404
        body_text = resp.text.lower()
        # Should not say "you don't have permission" — that confirms existence.
        assert "permission" not in body_text
        assert "forbidden" not in body_text or "not found" in body_text
