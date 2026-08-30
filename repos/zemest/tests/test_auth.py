"""Tests for authentication endpoints."""
import pytest
import pytest_asyncio


@pytest.mark.asyncio
class TestAuth:
    """Test auth registration, login, and JWT flow."""

    async def test_register_new_user(self, client):
        resp = await client.post("/api/auth/register", json={
            "name": "Rahim Miah",
            "email": "rahim@example.com",
            "password": "securepass123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_register_duplicate_email(self, client, test_user):
        resp = await client.post("/api/auth/register", json={
            "name": "Another User",
            "email": "test@example.com",  # Same as test_user
            "password": "pass123",
        })
        assert resp.status_code == 400
        assert "already registered" in resp.json()["detail"]

    async def test_register_invalid_email(self, client):
        resp = await client.post("/api/auth/register", json={
            "name": "Bad Email",
            "email": "not-an-email",
            "password": "pass123",
        })
        assert resp.status_code == 422

    async def test_login_valid_credentials(self, client, test_user):
        resp = await client.post("/api/auth/login", json={
            "email": "test@example.com",
            "password": "testpass123",
        })
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    async def test_login_wrong_password(self, client, test_user):
        resp = await client.post("/api/auth/login", json={
            "email": "test@example.com",
            "password": "wrongpassword",
        })
        assert resp.status_code == 401

    async def test_login_nonexistent_user(self, client):
        resp = await client.post("/api/auth/login", json={
            "email": "nobody@example.com",
            "password": "pass123",
        })
        assert resp.status_code == 401

    async def test_get_me_authenticated(self, client, test_user, auth_headers):
        resp = await client.get("/api/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Test User"
        assert data["email"] == "test@example.com"

    async def test_get_me_no_token(self, client):
        resp = await client.get("/api/auth/me")
        assert resp.status_code == 401

    async def test_get_me_invalid_token(self, client):
        resp = await client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer invalid_token_here"},
        )
        assert resp.status_code == 401
