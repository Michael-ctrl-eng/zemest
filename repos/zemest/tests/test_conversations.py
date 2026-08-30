"""Tests for conversation endpoints."""
import pytest


@pytest.mark.asyncio
class TestConversations:

    async def test_list_conversations(
        self, client, auth_headers, test_tenant, test_conversation
    ):
        resp = await client.get(
            f"/api/tenants/{test_tenant.id}/conversations",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    async def test_get_conversation_with_messages(
        self, client, auth_headers, test_tenant, test_conversation
    ):
        resp = await client.get(
            f"/api/tenants/{test_tenant.id}/conversations/{test_conversation.id}",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "active"
        assert len(data["messages"]) == 2
        assert data["messages"][0]["role"] == "customer"
        assert "products" in data["messages"][0]["content"].lower()

    async def test_conversation_not_found(self, client, auth_headers, test_tenant):
        import uuid
        resp = await client.get(
            f"/api/tenants/{test_tenant.id}/conversations/{uuid.uuid4()}",
            headers=auth_headers,
        )
        assert resp.status_code == 404
