"""Tests for order management endpoints."""
import uuid
from decimal import Decimal

import pytest
import pytest_asyncio

from app.models.order import Order, OrderItem


@pytest_asyncio.fixture
async def test_order(db_session, test_tenant, test_customer):
    """Create a test order."""
    order = Order(
        id=uuid.uuid4(),
        tenant_id=test_tenant.id,
        customer_id=test_customer.id,
        order_number="ORD-260317-001",
        customer_name="Ahmed",
        customer_phone="01012345678",
        governorate="cairo",
        city="Cairo",
        area="Maadi",
        address_detail="15 Road 9, Maadi, Cairo",
        payment_method="cod",
        subtotal=Decimal("1200.00"),
        delivery_charge=Decimal("60.00"),
        total=Decimal("1260.00"),
        status="pending",
    )
    db_session.add(order)
    await db_session.flush()

    item = OrderItem(
        id=uuid.uuid4(),
        order_id=order.id,
        product_name="Cotton Galabiya",
        quantity=1,
        unit_price=Decimal("1200.00"),
        total_price=Decimal("1200.00"),
    )
    db_session.add(item)
    await db_session.commit()
    return order


@pytest.mark.asyncio
class TestOrders:

    async def test_list_orders(self, client, auth_headers, test_tenant, test_order):
        resp = await client.get(
            f"/api/tenants/{test_tenant.id}/orders",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert any(o["order_number"] == "ORD-260317-001" for o in data["orders"])

    async def test_list_orders_filter_by_status(self, client, auth_headers, test_tenant, test_order):
        resp = await client.get(
            f"/api/tenants/{test_tenant.id}/orders?status=pending",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert all(o["status"] == "pending" for o in resp.json()["orders"])

    async def test_get_order_detail(self, client, auth_headers, test_tenant, test_order):
        resp = await client.get(
            f"/api/tenants/{test_tenant.id}/orders/{test_order.id}",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["order_number"] == "ORD-260317-001"
        assert data["customer_name"] == "Ahmed"
        assert data["governorate"] == "cairo"
        assert len(data["items"]) == 1
        assert data["items"][0]["product_name"] == "Cotton Galabiya"

    async def test_update_order_status_pending_to_confirmed(
        self, client, auth_headers, test_tenant, test_order
    ):
        resp = await client.patch(
            f"/api/tenants/{test_tenant.id}/orders/{test_order.id}/status",
            json={"status": "confirmed"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "confirmed"

    async def test_update_order_status_invalid_transition(
        self, client, auth_headers, test_tenant, test_order
    ):
        # Cannot go from pending directly to delivered
        resp = await client.patch(
            f"/api/tenants/{test_tenant.id}/orders/{test_order.id}/status",
            json={"status": "delivered"},
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert "Cannot transition" in resp.json()["detail"]

    async def test_update_order_status_full_lifecycle(
        self, client, auth_headers, test_tenant, test_order
    ):
        # pending -> confirmed -> shipped -> delivered
        for status in ["confirmed", "shipped", "delivered"]:
            resp = await client.patch(
                f"/api/tenants/{test_tenant.id}/orders/{test_order.id}/status",
                json={"status": status},
                headers=auth_headers,
            )
            assert resp.status_code == 200
            assert resp.json()["status"] == status

    async def test_cancel_pending_order(self, client, auth_headers, test_tenant, test_order):
        resp = await client.patch(
            f"/api/tenants/{test_tenant.id}/orders/{test_order.id}/status",
            json={"status": "cancelled"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

    async def test_cannot_modify_delivered_order(
        self, client, auth_headers, test_tenant, test_order, db_session
    ):
        test_order.status = "delivered"
        await db_session.commit()

        resp = await client.patch(
            f"/api/tenants/{test_tenant.id}/orders/{test_order.id}/status",
            json={"status": "cancelled"},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    async def test_order_not_found(self, client, auth_headers, test_tenant):
        resp = await client.get(
            f"/api/tenants/{test_tenant.id}/orders/{uuid.uuid4()}",
            headers=auth_headers,
        )
        assert resp.status_code == 404
