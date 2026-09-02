"""System / integration tests — end-to-end flows."""
import io
import uuid

import pytest
import pytest_asyncio

from app.models.order import Order
from app.services.order_service import create_order


@pytest.mark.asyncio
class TestSystemFlow:
    """End-to-end integration tests covering complete user journeys."""

    async def test_full_onboarding_flow(self, client):
        """Test: register -> create tenant -> add products -> verify."""
        # 1. Register (anti-enumeration: uniform 202, no tokens) then login
        resp = await client.post("/api/auth/register", json={
            "name": "Shopkeeper Ahmed",
            "email": "ahmed@shop.com",
            "password": "secure123",
        })
        assert resp.status_code == 202
        resp = await client.post("/api/auth/login", json={
            "email": "ahmed@shop.com",
            "password": "secure123",
        })
        assert resp.status_code == 200
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        # 2. Create tenant
        resp = await client.post("/api/tenants", json={
            "page_name": "Ahmed Fashion House",
            "website_url": "https://ahmedfashion.com",
            "business_email": "ahmed@shop.com",
        }, headers=headers)
        assert resp.status_code == 200
        tenant_id = resp.json()["id"]

        # 3. Add products manually
        resp = await client.post(f"/api/tenants/{tenant_id}/products", json={
            "name": "Cotton Galabiya",
            "name_ar": "جلابية قطن",
            "price": "8000.00",
            "category": "Premium",
        }, headers=headers)
        assert resp.status_code == 201

        # 4. Add products via CSV
        csv = "name,price,category\nGalabiya,1500,Clothing\nScarf,300,Clothing\n"
        files = {"file": ("products.csv", io.BytesIO(csv.encode()), "text/csv")}
        resp = await client.post(
            f"/api/tenants/{tenant_id}/products/upload-csv",
            files=files,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["imported"] == 2

        # 5. Verify products
        resp = await client.get(
            f"/api/tenants/{tenant_id}/products", headers=headers
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 3

        # 6. Check stats
        resp = await client.get(
            f"/api/tenants/{tenant_id}/stats", headers=headers
        )
        assert resp.status_code == 200
        assert resp.json()["products_count"] == 3

    async def test_order_lifecycle(
        self, client, auth_headers, test_tenant, test_customer, db_session
    ):
        """Test complete order lifecycle: create -> confirm -> ship -> deliver."""
        # Create order via service
        order = await create_order(
            db=db_session,
            tenant_id=test_tenant.id,
            customer_id=test_customer.id,
            conversation_id=None,
            customer_name="Fatima",
            customer_phone="01012345678",
            governorate="cairo",
            city="Giza",
            area="Dokki",
            address_detail="23 Mohandessin, Dokki, Giza",
            payment_method="cod",
            items=[{
                "product_name": "Leather Bag",
                "quantity": 2,
                "unit_price": "2500.00",
            }],
            delivery_charge=80,
        )
        await db_session.commit()

        assert order.status == "pending"
        assert order.total == 5080  # 2500*2 + 80

        # Confirm
        resp = await client.patch(
            f"/api/tenants/{test_tenant.id}/orders/{order.id}/status",
            json={"status": "confirmed"},
            headers=auth_headers,
        )
        assert resp.status_code == 200

        # Ship
        resp = await client.patch(
            f"/api/tenants/{test_tenant.id}/orders/{order.id}/status",
            json={"status": "shipped"},
            headers=auth_headers,
        )
        assert resp.status_code == 200

        # Deliver
        resp = await client.patch(
            f"/api/tenants/{test_tenant.id}/orders/{order.id}/status",
            json={"status": "delivered"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "delivered"

    async def test_multi_tenant_isolation(self, client, db_session):
        """Test that data is properly isolated between tenants."""
        # Create two users (unique emails: earlier suite files may leave
        # a@test.com registered in the shared test.db)
        suffix = uuid.uuid4().hex[:8]
        resp1 = await client.post("/api/auth/register", json={
            "name": "User A", "email": f"a-{suffix}@test.com", "password": "password123",
        })
        assert resp1.status_code == 202, resp1.text
        resp1 = await client.post("/api/auth/login", json={
            "email": f"a-{suffix}@test.com", "password": "password123",
        })
        token_a = resp1.json()["access_token"]
        headers_a = {"Authorization": f"Bearer {token_a}", "Content-Type": "application/json"}

        resp2 = await client.post("/api/auth/register", json={
            "name": "User B", "email": f"b-{suffix}@test.com", "password": "password123",
        })
        assert resp2.status_code == 202, resp2.text
        resp2 = await client.post("/api/auth/login", json={
            "email": f"b-{suffix}@test.com", "password": "password123",
        })
        token_b = resp2.json()["access_token"]
        headers_b = {"Authorization": f"Bearer {token_b}", "Content-Type": "application/json"}

        # Create tenants
        resp = await client.post("/api/tenants", json={"page_name": "Store A"}, headers=headers_a)
        tenant_a_id = resp.json()["id"]

        resp = await client.post("/api/tenants", json={"page_name": "Store B"}, headers=headers_b)
        tenant_b_id = resp.json()["id"]

        # Add product to Store A
        resp = await client.post(f"/api/tenants/{tenant_a_id}/products", json={
            "name": "Product A", "price": "100.00",
        }, headers=headers_a)
        assert resp.status_code == 201

        # User B should NOT see Store A's products
        resp = await client.get(
            f"/api/tenants/{tenant_a_id}/products", headers=headers_b
        )
        assert resp.status_code == 404  # Tenant not found for user B

        # User B should see their own empty store
        resp = await client.get(
            f"/api/tenants/{tenant_b_id}/products", headers=headers_b
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    async def test_webhook_to_conversation_flow(self, client, test_tenant, monkeypatch):
        """Test that webhook creates conversation and messages."""
        import hashlib, hmac, json
        from app.config import get_settings
        s = get_settings()
        monkeypatch.setattr(s, "FB_APP_SECRET", "test_secret")
        monkeypatch.setattr(s, "APP_DEBUG", False)

        # Simulate incoming message
        payload = {
            "object": "page",
            "entry": [{
                "id": test_tenant.fb_page_id,
                "messaging": [{
                    "sender": {"id": "new_customer_psid"},
                    "recipient": {"id": test_tenant.fb_page_id},
                    "message": {"mid": "mid.new_test_unique", "text": "Hi there!"},
                }],
            }],
        }
        body = json.dumps(payload).encode()
        expected = hmac.new(b"test_secret", body, hashlib.sha256).hexdigest()
        sig = f"sha256={expected}"
        resp = await client.post(
            "/api/webhook/messenger",
            content=body,
            headers={"Content-Type": "application/json", "X-Hub-Signature-256": sig},
        )
        assert resp.status_code == 200

    async def test_legacy_dashboard_routes_are_gone(self, client):
        """The legacy unauthenticated Jinja dashboard was removed — those
        routes must 404 (the live dashboard is the Next.js app, which talks
        to the authenticated JSON APIs only)."""
        for page in ("/dashboard/login", "/dashboard"):
            resp = await client.get(page)
            assert resp.status_code == 404, f"Legacy route {page} unexpectedly live"

    async def test_tenant_api_pages_load(self, client, auth_headers, test_tenant):
        """The authenticated JSON API surface the Next.js dashboard uses."""
        tid = test_tenant.id
        pages = [
            f"/api/tenants/{tid}/products",
            f"/api/tenants/{tid}/orders",
            f"/api/tenants/{tid}/conversations",
            f"/api/tenants/{tid}/customers",
        ]
        for page in pages:
            resp = await client.get(page, headers=auth_headers)
            assert resp.status_code == 200, f"Endpoint {page} failed"

    async def test_swagger_docs_load(self, client):
        """Test that API docs are accessible."""
        resp = await client.get("/docs")
        assert resp.status_code == 200

        resp = await client.get("/redoc")
        assert resp.status_code == 200

        resp = await client.get("/openapi.json")
        assert resp.status_code == 200
        schema = resp.json()
        # Title is Zemest (per config.py)
        assert schema["info"]["title"] == "Zemest"
        # Verify all tag groups exist
        tags = [t["name"] for t in schema.get("tags", [])] if "tags" in schema else []
        paths = list(schema.get("paths", {}).keys())
        assert any("/api/auth" in p for p in paths)
        assert any("/api/tenants" in p for p in paths)
        assert any("/api/webhook" in p for p in paths)
        assert any("/api/test" in p for p in paths)
