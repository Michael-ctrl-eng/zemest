"""Tests for tenant CRUD and stats endpoints."""
import pytest


@pytest.mark.asyncio
class TestTenants:

    async def test_create_tenant(self, client, auth_headers):
        resp = await client.post("/api/tenants", json={
            "page_name": "My New Store",
            "website_url": "https://newstore.com",
            "business_email": "new@store.com",
            "business_phone": "01712345678",
        }, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["page_name"] == "My New Store"
        assert data["is_active"] is True

    async def test_create_tenant_minimal(self, client, auth_headers):
        resp = await client.post("/api/tenants", json={
            "page_name": "Minimal Store",
        }, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["page_name"] == "Minimal Store"

    async def test_create_tenant_unauthenticated(self, client):
        resp = await client.post("/api/tenants", json={
            "page_name": "No Auth Store",
        })
        assert resp.status_code == 401

    async def test_list_tenants(self, client, auth_headers, test_tenant):
        resp = await client.get("/api/tenants", headers=auth_headers)
        assert resp.status_code == 200
        tenants = resp.json()
        assert len(tenants) >= 1
        assert any(t["page_name"] == "Test Fashion Store" for t in tenants)

    async def test_get_tenant_detail(self, client, auth_headers, test_tenant):
        resp = await client.get(
            f"/api/tenants/{test_tenant.id}", headers=auth_headers
        )
        assert resp.status_code == 200
        assert resp.json()["page_name"] == "Test Fashion Store"

    async def test_get_tenant_not_found(self, client, auth_headers):
        import uuid
        resp = await client.get(
            f"/api/tenants/{uuid.uuid4()}", headers=auth_headers
        )
        assert resp.status_code == 404

    async def test_update_tenant(self, client, auth_headers, test_tenant):
        resp = await client.patch(
            f"/api/tenants/{test_tenant.id}",
            json={"page_name": "Updated Store Name"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["page_name"] == "Updated Store Name"

    async def test_get_stats(self, client, auth_headers, test_tenant):
        resp = await client.get(
            f"/api/tenants/{test_tenant.id}/stats", headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "products_count" in data
        assert "orders_count" in data
        assert "total_revenue" in data

    async def test_tenant_isolation(self, client, db_session, auth_headers):
        """Test that users can only see their own tenants."""
        from app.models.user import User
        from app.models.tenant import Tenant
        from app.utils.security import hash_password, create_access_token
        import uuid

        other_user = User(
            id=uuid.uuid4(), name="Other User",
            email="other@example.com", hashed_password=hash_password("pass"),
        )
        db_session.add(other_user)
        other_tenant = Tenant(
            id=uuid.uuid4(), owner_id=other_user.id,
            page_name="Other User Store",
        )
        db_session.add(other_tenant)
        await db_session.commit()

        # Original user should not see other's tenant
        resp = await client.get(
            f"/api/tenants/{other_tenant.id}", headers=auth_headers
        )
        assert resp.status_code == 404
