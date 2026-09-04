"""Tests for the Postiz integration layer.

These tests mock the Postiz API calls (we don't need a running Postiz
instance to test our client + API endpoints).
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from app.scheduling.postiz_client import PostizClient


class TestPostizClient:
    """Test the PostizClient class with mocked HTTP calls."""

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Health check returns True when Postiz is reachable."""
        client = PostizClient(base_url="http://test:4007")

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            result = await client.health_check()
            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        """Health check returns False when Postiz is unreachable."""
        client = PostizClient(base_url="http://test:4007")

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=Exception("connection refused"))
            mock_client_cls.return_value = mock_client

            result = await client.health_check()
            assert result is False

    @pytest.mark.asyncio
    async def test_login_success(self):
        """Login stores the JWT token from the auth header."""
        client = PostizClient(base_url="http://test:4007")

        with patch.object(client, "_get_client") as mock_get:
            mock_http = AsyncMock()
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.headers = {"auth": "test-jwt-token-123"}
            mock_resp.json = MagicMock(return_value={"login": True})
            mock_http.post = AsyncMock(return_value=mock_resp)
            mock_get.return_value = mock_http

            result = await client.login("test@example.com", "password")
            assert result is True
            assert client._token == "test-jwt-token-123"

    @pytest.mark.asyncio
    async def test_login_failure(self):
        """Login returns False on auth failure."""
        client = PostizClient(base_url="http://test:4007")

        with patch.object(client, "_get_client") as mock_get:
            mock_http = AsyncMock()
            mock_resp = MagicMock()
            mock_resp.status_code = 401
            mock_resp.text = "Unauthorized"
            mock_resp.headers = {}
            mock_http.post = AsyncMock(return_value=mock_resp)
            mock_get.return_value = mock_http

            result = await client.login("bad@example.com", "wrong")
            assert result is False
            assert client._token is None

    @pytest.mark.asyncio
    async def test_list_integrations(self):
        """List integrations returns the integrations array."""
        client = PostizClient(base_url="http://test:4007")
        client._token = "test-token"

        mock_integrations = [
            {"id": "1", "identifier": "My FB Page", "name": "facebook", "provider": "facebook"},
            {"id": "2", "identifier": "My IG Account", "name": "instagram", "provider": "instagram"},
        ]

        with patch.object(client, "_get_client") as mock_get:
            mock_http = AsyncMock()
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json = MagicMock(return_value={"integrations": mock_integrations})
            mock_http.get = AsyncMock(return_value=mock_resp)
            mock_get.return_value = mock_http

            result = await client.list_integrations()
            assert len(result) == 2
            assert result[0]["provider"] == "facebook"
            assert result[1]["provider"] == "instagram"

    @pytest.mark.asyncio
    async def test_create_post(self):
        """Create post returns the created post object."""
        client = PostizClient(base_url="http://test:4007")
        client._token = "test-token"

        mock_response = {"id": "post-123", "status": "scheduled"}

        with patch.object(client, "_get_client") as mock_get:
            mock_http = AsyncMock()
            mock_resp = MagicMock()
            mock_resp.status_code = 201
            mock_resp.json = MagicMock(return_value=mock_response)
            mock_http.post = AsyncMock(return_value=mock_resp)
            mock_get.return_value = mock_http

            result = await client.create_post(
                posts=[{
                    "integrationId": "1",
                    "content": "Test caption",
                    "mediaUrls": [],
                }],
                schedule_at="2026-01-01T10:00:00Z",
            )
            assert result == mock_response
            assert result["id"] == "post-123"

    @pytest.mark.asyncio
    async def test_delete_post(self):
        """Delete post returns True on success."""
        client = PostizClient(base_url="http://test:4007")
        client._token = "test-token"

        with patch.object(client, "_get_client") as mock_get:
            mock_http = AsyncMock()
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_http.delete = AsyncMock(return_value=mock_resp)
            mock_get.return_value = mock_http

            result = await client.delete_post("group-123")
            assert result is True

    @pytest.mark.asyncio
    async def test_get_post_statistics(self):
        """Get post statistics returns metrics."""
        client = PostizClient(base_url="http://test:4007")
        client._token = "test-token"

        mock_stats = {
            "impressions": 1234,
            "reach": 567,
            "engagement": 89,
            "likes": 45,
            "comments": 12,
        }

        with patch.object(client, "_get_client") as mock_get:
            mock_http = AsyncMock()
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json = MagicMock(return_value=mock_stats)
            mock_http.get = AsyncMock(return_value=mock_resp)
            mock_get.return_value = mock_http

            result = await client.get_post_statistics("post-123")
            assert result["impressions"] == 1234
            assert result["reach"] == 567

    @pytest.mark.asyncio
    async def test_find_free_slot(self):
        """Find free slot returns a datetime string."""
        client = PostizClient(base_url="http://test:4007")
        client._token = "test-token"

        with patch.object(client, "_get_client") as mock_get:
            mock_http = AsyncMock()
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json = MagicMock(return_value={"date": "2026-01-15T14:00:00.000Z"})
            mock_http.get = AsyncMock(return_value=mock_resp)
            mock_get.return_value = mock_http

            result = await client.find_free_slot()
            assert result == "2026-01-15T14:00:00.000Z"

    @pytest.mark.asyncio
    async def test_get_connect_url(self):
        """Get connect URL returns the OAuth URL."""
        client = PostizClient(base_url="http://test:4007")
        client._token = "test-token"

        with patch.object(client, "_get_client") as mock_get:
            mock_http = AsyncMock()
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json = MagicMock(return_value={"url": "https://facebook.com/oauth/..."})
            mock_http.post = AsyncMock(return_value=mock_resp)
            mock_get.return_value = mock_http

            result = await client.get_connect_url("facebook")
            assert result is not None
            assert "oauth" in result


@pytest.mark.asyncio
class TestPostizAPI:
    """Test the Postiz API endpoints (with mocked PostizClient)."""

    async def test_health_endpoint(self, client, auth_headers, test_tenant):
        """Test the Postiz health check endpoint."""
        with patch("app.api.postiz.get_postiz_client") as mock_get:
            mock_postiz = AsyncMock()
            mock_postiz.health_check = AsyncMock(return_value=True)
            mock_postiz.base_url = "http://test:4007/api"
            mock_get.return_value = mock_postiz

            resp = await client.get(
                f"/api/tenants/{test_tenant.id}/postiz/health",
                headers=auth_headers,
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["healthy"] is True

    async def test_list_integrations_endpoint(self, client, db_session, auth_headers, test_tenant):
        """Test the list integrations endpoint (per-tenant session)."""
        test_tenant.postiz_token = "tenant-postiz-jwt"
        await db_session.commit()
        with patch("app.api.postiz.get_postiz_client_for_tenant") as mock_get:
            mock_postiz = AsyncMock()
            mock_postiz.list_integrations = AsyncMock(return_value=[
                {"id": "1", "identifier": "My Page", "provider": "facebook"},
            ])
            mock_get.return_value = mock_postiz

            resp = await client.get(
                f"/api/tenants/{test_tenant.id}/postiz/integrations",
                headers=auth_headers,
            )
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["integrations"]) == 1

    async def test_integrations_require_login(self, client, auth_headers, test_tenant):
        """No stored Postiz session → 401, never the old shared session."""
        assert not test_tenant.postiz_token
        resp = await client.get(
            f"/api/tenants/{test_tenant.id}/postiz/integrations",
            headers=auth_headers,
        )
        assert resp.status_code == 401

    async def test_create_post_endpoint(self, client, db_session, auth_headers, test_tenant):
        """Test creating a post via Postiz."""
        test_tenant.postiz_token = "tenant-postiz-jwt"
        await db_session.commit()
        with patch("app.api.postiz.get_postiz_client_for_tenant") as mock_get:
            mock_postiz = AsyncMock()
            mock_postiz.create_post = AsyncMock(return_value={
                "id": "post-123",
                "status": "scheduled",
            })
            mock_get.return_value = mock_postiz

            resp = await client.post(
                f"/api/tenants/{test_tenant.id}/postiz/posts",
                json={
                    "integration_id": "1",
                    "caption": "Test post via Postiz!",
                    "media_urls": [],
                    "schedule_at": "2026-01-01T10:00:00Z",
                },
                headers=auth_headers,
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "created"
            assert data["postiz_result"]["id"] == "post-123"

    async def test_get_connect_url_endpoint(self, client, db_session, auth_headers, test_tenant):
        """Test getting the OAuth connect URL."""
        test_tenant.postiz_token = "tenant-postiz-jwt"
        await db_session.commit()
        with patch("app.api.postiz.get_postiz_client_for_tenant") as mock_get:
            mock_postiz = AsyncMock()
            mock_postiz.get_connect_url = AsyncMock(return_value="https://facebook.com/oauth/authorize?...")
            mock_get.return_value = mock_postiz

            resp = await client.post(
                f"/api/tenants/{test_tenant.id}/postiz/connect/facebook",
                headers=auth_headers,
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "oauth" in data["url"]
            assert data["provider"] == "facebook"

    async def test_delete_post_endpoint(self, client, db_session, auth_headers, test_tenant):
        """Test deleting a post via Postiz."""
        test_tenant.postiz_token = "tenant-postiz-jwt"
        await db_session.commit()
        with patch("app.api.postiz.get_postiz_client_for_tenant") as mock_get:
            mock_postiz = AsyncMock()
            mock_postiz.delete_post = AsyncMock(return_value=True)
            mock_get.return_value = mock_postiz

            resp = await client.delete(
                f"/api/tenants/{test_tenant.id}/postiz/posts/group-123",
                headers=auth_headers,
            )
            assert resp.status_code == 200
            assert resp.json()["status"] == "deleted"

    async def test_best_time_endpoint(self, client, db_session, auth_headers, test_tenant):
        """Test the best-time (find free slot) endpoint."""
        test_tenant.postiz_token = "tenant-postiz-jwt"
        await db_session.commit()
        with patch("app.api.postiz.get_postiz_client_for_tenant") as mock_get:
            mock_postiz = AsyncMock()
            mock_postiz.find_free_slot = AsyncMock(return_value="2026-01-15T14:00:00Z")
            mock_get.return_value = mock_postiz

            resp = await client.get(
                f"/api/tenants/{test_tenant.id}/postiz/best-time",
                headers=auth_headers,
            )
            assert resp.status_code == 200
            assert "next_free_slot" in resp.json()
